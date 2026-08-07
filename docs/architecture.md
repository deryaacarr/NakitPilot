# NakitPilot — Sistem Mimarisi

**Doküman:** NP-002  
**Öncelik:** P0  
**İlgili:** `docs/product-rules.md`, `docs/database.md`, `docs/api.md`

---

## 1. Genel bakış

NakitPilot, monorepo içinde ayrılmış web ve API servislerinden oluşan çok kiracılı (multi-tenant) bir SaaS uygulamasıdır.

| Katman | Teknoloji |
|--------|-----------|
| Frontend | Next.js, TypeScript, Tailwind CSS, React Hook Form, Zod, TanStack Query, ECharts/Recharts, Zustand (sınırlı) |
| Backend | Django, Django REST Framework, Django Simple JWT |
| Veri | PostgreSQL |
| Kuyruk / cache | Redis, Celery |
| Dosya | S3 uyumlu object storage |
| Altyapı | Docker Compose, Nginx, GitHub Actions, Sentry |

---

## 2. Temel sistem akışı

```text
┌─────────────┐     HTTPS/JSON      ┌──────────────────┐
│  Next.js    │ ◄─────────────────► │  Nginx           │
│  (apps/web) │   Authorization:    │  reverse proxy   │
└─────────────┘   Bearer <JWT>      └────────┬─────────┘
                                             │
                                    ┌────────▼─────────┐
                                    │  Django + DRF    │
                                    │  (apps/api)      │
                                    └────────┬─────────┘
                         ┌───────────────────┼───────────────────┐
                         │                   │                   │
                ┌────────▼────────┐ ┌────────▼────────┐ ┌───────▼────────┐
                │  PostgreSQL     │ │  Redis           │ │  S3 storage    │
                │  (tenant data)  │ │  cache + broker  │ │  (imports)     │
                └─────────────────┘ └────────┬────────┘ └────────────────┘
                                             │
                                    ┌────────▼─────────┐
                                    │  Celery workers  │
                                    │  import / risk / │
                                    │  forecast / jobs │
                                    └──────────────────┘
```

**Akış özeti**

1. Kullanıcı tarayıcıda Next.js uygulamasına girer.
2. Login sonrası access/refresh JWT alınır; API çağrıları `Authorization: Bearer` ile gider.
3. Nginx isteği Django API’ye iletir.
4. Her iş isteğinde organizasyon bağlamı doğrulanır; sorgular `organization_id` ile filtrelenir.
5. Senkron CRUD/okuma PostgreSQL üzerinden yanıtlanır.
6. Excel import, risk ve forecast gibi ağır işler Celery kuyruğuna alınır; sonuçlar DB’ye yazılır.
7. Yüklenen dosyalar S3 uyumlu depolamada tutulur.

---

## 3. Frontend ↔ backend iletişimi

### 3.1 Protokol

- İletişim: HTTPS üzerinden JSON REST API
- Base path (örnek): `/api/v1/`
- İstemci: TanStack Query ile veri çekme, cache ve invalidation
- Formlar: React Hook Form + Zod (istemci doğrulama); sunucu da serializer/Zod eşleniği ile doğrular
- Global UI state: yalnızca gerçekten paylaşılan durum için Zustand (ör. seçili organizasyon, sidebar)

### 3.2 Sorumluluk ayrımı

| Frontend | Backend |
|----------|---------|
| Ekran, form UX, grafik | İş kuralları, yetki, tenant izolasyonu |
| İstemci validasyonu | Kaynak doğrulama, hesaplama, kalıcılık |
| JWT saklama / yenileme | Token üretimi, izin kontrolü |
| Query cache | Canonical veri ve audit |

### 3.3 Hata ve kimlik yenileme

- `401` → refresh token ile yenileme; başarısızsa login’e yönlendirme
- `403` → yetki yok (rol / organization)
- `400` / `422` → alan hataları forma yansıtılır
- Arka plan işleri için `202` + job id; frontend polling veya status endpoint ile takip eder

---

## 4. Kimlik doğrulama yapısı

### 4.1 Bileşenler

- **Django Simple JWT** — access + refresh token
- **User** — e-posta bazlı kimlik
- **Membership** — kullanıcının organizasyondaki rolü

### 4.2 Akış

```text
Login (email/password)
        │
        ▼
  Access JWT + Refresh JWT
        │
        ▼
  Her API isteği: Bearer access token
        │
        ├── token geçersiz/süresi dolmuş → 401 → refresh
        └── geçerli → user çözülür
                │
                ▼
        Organization context
        (header veya membership seçimi)
                │
                ▼
        Role check (OWNER / ADMIN / …)
                │
                ▼
        View / serializer iş kuralı
```

### 4.3 Organizasyon bağlamı

- Kullanıcı birden fazla organizasyona üye olabilir.
- Aktif organizasyon istemcide seçilir; API’ye örn. `X-Organization-Id` header veya path/query ile iletilir.
- Backend, kullanıcının o organizasyonda **aktif Membership** kaydı olduğunu doğrular.
- Rol: `OWNER`, `ADMIN`, `FINANCE_MANAGER`, `COLLECTION_AGENT`, `VIEWER`

### 4.4 Güvenlik notları

- Access token kısa ömürlü; refresh rotasyonu tercih edilir.
- Şifreler Django password hasher ile saklanır.
- Hassas işlemler `AuditLog`’a yazılır.

---

## 5. Organizasyon izolasyonu

Tüm iş modelleri (Customer, Invoice, Payment, Task, Promise, Activity, Import, Risk, Forecast, AuditLog) `organization_id` taşır.

**Kurallar**

1. Liste/detay sorguları daima aktif organizasyon ile filtrelenir.
2. Nesne erişiminde `organization_id` eşleşmezse `404` (bilgi sızdırmamak için).
3. Cross-tenant join / update yasaktır; foreign key’ler aynı tenant içinde doğrulanır (örn. invoice.customer aynı org’da olmalı).
4. Celery görevleri `organization_id` parametresi alır; worker da aynı filtreyi uygular.
5. Dosya path’leri tenant önekli tutulur: `org/{organization_id}/imports/...`

Bu izolasyon MVP’nin güvenlik sınırıdır; satır seviyesi RLS sonradan eklenebilir, ilk sürümde uygulama katmanı yeterlidir.

---

## 6. Dosya yükleme süreci

MVP’de birincil kullanım: müşteri / fatura Excel-CSV import.

```text
Client                API                   S3              Celery            PostgreSQL
  │                    │                     │                 │                   │
  │  POST multipart    │                     │                 │                   │
  │  (file + type)     │                     │                 │                   │
  │───────────────────►│                     │                 │                   │
  │                    │  upload object      │                 │                   │
  │                    │────────────────────►│                 │                   │
  │                    │  create ImportJob   │                 │                   │
  │                    │  (PENDING)          │                 │                   │
  │                    │──────────────────────────────────────────────────────────►│
  │                    │  enqueue parse_job  │                 │                   │
  │                    │─────────────────────────────────────►│                   │
  │  202 + job_id      │                     │                 │                   │
  │◄───────────────────│                     │                 │                   │
  │                    │                     │  download file  │                   │
  │                    │                     │◄────────────────│                   │
  │                    │                     │  parse rows     │                   │
  │                    │                     │  (Pandas/openpyxl)                 │
  │                    │                     │  write rows / ImportError          │
  │                    │                     │───────────────────────────────────►│
  │                    │                     │  job COMPLETED/FAILED              │
  │  GET job status    │                     │                 │                   │
  │───────────────────►│◄──────────────────────────────────────────────────────────│
```

**Adımlar**

1. Yetkili kullanıcı dosyayı yükler (`import_type`: customers / invoices vb.).
2. API dosyayı S3’e yazar, `ImportJob` oluşturur, Celery’ye iş bırakır.
3. Worker dosyayı okur, satır satır doğrular; başarılı satırlar ilgili modellere yazılır.
4. Hatalı satırlar `ImportError` olarak saklanır (`row_number`, `field_name`, `raw_value`, `error_message`).
5. Job sayaçları güncellenir: `total_rows`, `successful_rows`, `failed_rows`.
6. Frontend job durumunu ve hata listesini gösterir.

Kısmi başarı kabul edilir (product rule).

---

## 7. Celery görevleri

Redis broker; worker’lar API ile aynı Docker ağında çalışır.

| Görev | Tetikleyici | Amaç |
|-------|-------------|------|
| `parse_import_job` | Dosya yükleme sonrası | Excel/CSV parse, satır yazma, hata kaydı |
| `recalculate_invoice_statuses` | Ödeme allocation sonrası (veya periyodik) | OVERDUE / PARTIALLY_PAID / PAID güncelleme |
| `calculate_customer_risk` | Manuel, gece job veya önemli olay sonrası | `RiskSnapshot` üretimi |
| `calculate_organization_forecast` | Manuel veya zamanlanmış (günlük) | `ForecastSnapshot` üretimi (bu hafta + 13 hafta) |
| `mark_overdue_tasks_and_promises` | Zamanlanmış (saatlik/günlük) | Task/promise statü güncelleme |
| `cleanup_expired_temp_files` | Zamanlanmış | Geçici import artıkları |

Senkron tutulacaklar (MVP): basit CRUD, ödeme kaydı sonrası hafif status güncellemesi (gerekirse async’e alınır).

---

## 8. Risk hesaplama süreci

**Amaç:** Hangi müşterilerin daha riskli olduğunu kural tabanlı göstermek (AI yok).

```text
Tetikleyici (manuel / gece job / söz kırılması vb.)
        │
        ▼
Celery: calculate_customer_risk(organization_id, customer_id?)
        │
        ▼
Girdiler (örnek sinyaller)
  • açık / gecikmiş bakiye
  • ortalama gecikme günü
  • kırılmış PaymentPromise sayısı
  • vadesi geçmiş fatura adedi
  • kredi limiti aşımı
        │
        ▼
Ağırlıklı skor (0–100) + risk_level (LOW / MEDIUM / HIGH / CRITICAL)
        │
        ▼
RiskSnapshot kaydı
  score, risk_level, score_details_json, calculated_at
        │
        ▼
API / UI: riskli müşteri listesi ve müşteri detayı
```

`score_details_json` şeffaflık için bileşen kırılımını saklar. İlk sürümde formül sabitlenir; ileride kalibre edilebilir.

---

## 9. Forecast hesaplama süreci

**Amaç:** Bu hafta + önümüzdeki 13 hafta tahsilat beklentisi.

```text
Tetikleyici (günlük schedule / manuel)
        │
        ▼
Celery: calculate_organization_forecast(organization_id)
        │
        ▼
Hafta kovaları (week_start × 14)
        │
        ▼
Kaynaklar (kural tabanlı)
  • OPEN / PARTIALLY_PAID / OVERDUE faturaların due_date veya söz tarihi
  • PENDING PaymentPromise → promised_date + amount
  • Geçmiş ödeme davranışı ile basit düzeltme (opsiyonel, kural)
        │
        ▼
Her hafta için:
  expected_amount
  optimistic_amount
  pessimistic_amount
  calculation_details_json
        │
        ▼
ForecastSnapshot satırları
        │
        ▼
Dashboard grafik (ECharts/Recharts)
```

**MVP kuralı:** Tahmin açıklanabilir ve kural tabanlıdır; ML/LLM kullanılmaz.

---

## 10. Para ve tarih (NP-003)

Ürün kuralları: `docs/product-rules.md` §7.

### 10.1 Para

```text
UI / form ──string "1500.00"──► API ──Decimal──► PostgreSQL Numeric
                                      │
                                      ├── aggregation: aynı currency içinde
                                      └── FX conversion: YOK (MVP)
```

- Alan tipi: `DecimalField` / `decimal.Decimal` — **float yok**
- JSON’da tutar: string (precision kaybını önlemek)
- `Organization.default_currency` varsayılanı: **TRY**
- Kayıt bazında `currency` serbest; raporlarda currency karıştırılmaz

### 10.2 Tarih / saat

```text
Client (org TZ görüntüler)     API / DB (UTC saklar)
        │                              │
        │  ISO-8601 UTC datetime       │
        │─────────────────────────────►│
        │◄─────────────────────────────│
        │  format: Europe/Istanbul vb. │
```

- `USE_TZ = True`; datetime UTC
- “Bugün”, “bu hafta”, görev vadeleri: `Organization.timezone`
- Saf tarih alanları (`due_date` vb.) takvim günü olarak tutulur; gün-sınırı org TZ ile yorumlanır

---

## 11. Ortamlar

| Ortam | Amaç |
|-------|------|
| Development | Docker Compose lokal; hot reload |
| Test | CI (GitHub Actions); izole DB |
| Production | `docker-compose.prod.yml`, Nginx, Sentry, PostgreSQL yedekleme |

---

## 12. Gözlemlenebilirlik

- Uygulama hataları: Sentry (web + API + Celery)
- İş logları: ImportJob / AuditLog
- Altyapı: container healthcheck; DB yedekleme scriptleri (`infrastructure/scripts`)

---

## 13. Mimari karar özeti

| Karar | Gerekçe |
|-------|---------|
| Django yerine Flask değil | Auth, admin, model, kurumsal SaaS hızı |
| JWT | Stateless API; Next.js ile uyum |
| Tenant izolasyonu uygulama katmanında | MVP hızı; sonra RLS eklenebilir |
| Kalan tutar hesaplanır, saklanmaz | Tek kaynak: allocation |
| Ağır işler Celery’de | Import/risk/forecast API latency’sini bozmaz |
| S3 uyumlu storage | Yerel disk bağımlılığı yok; prod’a taşınabilir |
| Decimal + UTC saklama | Para/tarih doğruluğu; UI’da org timezone |
