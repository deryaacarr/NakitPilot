# NakitPilot — Ürün Kuralları ve MVP Kapsamı

**Doküman:** NP-001  
**Öncelik:** P0  
**Durum:** Onaylı MVP tanımı

---

## 1. Ürün özeti

NakitPilot, KOBİ finans ve tahsilat ekiplerinin açık faturaları, geciken ödemeleri, müşteri riskini ve tahsilat vaatlerini tek ekrandan takip etmesini sağlayan web tabanlı bir tahsilat yönetim ürünüdür.

İlk sürüm, ücretli pilot müşterilere sunulacak; banka entegrasyonu, otomatik mesajlaşma ve gelişmiş muhasebe özellikleri MVP sonrasına bırakılır.

---

## 2. Hedef kullanıcı

### Birincil kullanıcı

| Rol | Açıklama |
|-----|----------|
| **Finans / tahsilat sorumlusu** | Günlük olarak geciken faturaları takip eder, müşteri arar, ödeme sözü alır, tahsilat kaydı girer. |
| **Finans müdürü** | Riskli müşterileri, haftalık tahsilat beklentisini ve ekip aktivitesini izler. |

### İkincil kullanıcı

| Rol | Açıklama |
|-----|----------|
| **Şirket sahibi / yönetici** | Genel tahsilat sağlığına ve nakit akışı beklentisine bakar. |
| **İzleyici (VIEWER)** | Rapor ve listeleri salt okunur görüntüler. |

### Hedef müşteri profili (pilot)

- Türkiye’de faaliyet gösteren KOBİ
- Açık fatura / cari takip ihtiyacı olan işletmeler (ticaret, üretim, hizmet, dağıtım)
- Excel veya muhasebe yazılımından fatura/müşteri listesi dışa aktarabilen ekipler
- 1–10 kişilik finans veya tahsilat ekibi
- Günlük tahsilat araması yapan en az bir sorumlu

### Hedef olmayan kullanıcı (MVP)

- Sadece muhasebe fişi / e-fatura arşivi arayanlar
- Banka mutabakatını otomatik çözmek isteyenler
- Hukuki takip / icra süreçlerini dijitalleştirmek isteyenler

---

## 3. MVP özellikleri (kapsam içi)

İlk sürüm aşağıdaki sorulara cevap vermelidir:

1. Hangi faturaların ödemesi gecikmiş?
2. Bugün hangi müşteriler aranmalı?
3. Hangi müşteriler daha riskli?
4. Müşteri ne zaman ödeme sözü verdi?
5. Bu hafta ve önümüzdeki 13 haftada ne kadar tahsilat bekleniyor?
6. Bir finans çalışanı gün içinde hangi işlemleri yaptı?

### 3.1 Kimlik, yetki ve organizasyon

- Çok kiracılı (multi-tenant) yapı: her şirket kendi verisini görür
- Kullanıcı kaydı / giriş (JWT)
- Organizasyon (şirket) oluşturma ve temel ayarlar
- Üyelik ve roller: `OWNER`, `ADMIN`, `FINANCE_MANAGER`, `COLLECTION_AGENT`, `VIEWER`
- Rol bazlı yetkilendirme (okuma / yazma ayrımı)

### 3.2 Müşteri (cari) yönetimi

- Müşteri CRUD
- Müşteri iletişim kişileri (birden fazla contact)
- Atanan tahsilat sorumlusu
- Ödeme vadesi (gün), kredi limiti, risk durumu alanları
- Müşteri notları

### 3.3 Fatura yönetimi

- Fatura CRUD
- Durumlar: `DRAFT`, `OPEN`, `PARTIALLY_PAID`, `PAID`, `OVERDUE`, `CANCELLED`
- Gecikmiş fatura listesi ve filtreler
- Kalan tutar kuralı: saklanmaz; `remaining_amount = total_amount − payment_allocations.total`
- Excel / CSV ile fatura ve müşteri içe aktarımı (ImportJob + ImportError)

### 3.4 Ödeme ve dağıtım

- Ödeme kaydı oluşturma
- Bir ödemenin birden fazla faturaya dağıtılması (`PaymentAllocation`)
- Parçalı ödeme desteği
- Ödeme yöntemi ve referans numarası

### 3.5 Tahsilat operasyonu

- Tahsilat görevleri (`CollectionTask`): CALL, EMAIL, WHATSAPP, FOLLOW_UP, MEETING, OTHER
- Görev atama, öncelik, durum, vade
- “Bugün aranacaklar” listesi (görev vadesi / takip tarihi bazlı)
- Ödeme sözü (`PaymentPromise`): tarih, tutar, durum (PENDING, FULFILLED, PARTIALLY_FULFILLED, BROKEN, CANCELLED)
- Görüşme / aktivite kaydı (`CollectionActivity`)

### 3.6 Risk ve tahmin (kural tabanlı)

- Müşteri risk skoru / seviyesi (`RiskSnapshot`) — kural tabanlı, AI değil
- Haftalık tahsilat forecast’i (`ForecastSnapshot`): bu hafta + önümüzdeki 13 hafta
- Beklenen / iyimser / kötümser tutar görünümü

### 3.7 Aktivite ve denetim

- Kullanıcının gün içi işlem özeti
- Kritik değişiklikler için audit log (`AuditLog`)

### 3.8 Raporlama ve arayüz

- Web uygulaması (Next.js)
- Gecikmiş faturalar paneli
- Bugünkü çağrı / takip listesi
- Riskli müşteri listesi
- Ödeme sözü takibi
- 13+1 haftalık tahsilat beklenti grafiği
- Temel dashboard

---

## 4. MVP dışında kalanlar

Aşağıdakiler ilk sürümde **yoktur**; MVP sonrasına bırakılır:

| Alan | Açıklama |
|------|----------|
| Mobil uygulama | Native veya PWA odaklı mobil ürün |
| Banka API entegrasyonu | Otomatik hesap hareketi / mutabakat |
| GİB entegrasyonu | e-Fatura / e-Arşiv çekimi |
| WhatsApp otomatik mesaj | Otomatik hatırlatma gönderimi (manuel kayıt tutulabilir) |
| AI tahsilat tahmini | ML / LLM tabanlı tahmin |
| Sanal POS | Online tahsilat alma |
| Hukuki ihtar | İhtarname / icra süreçleri |
| Logo / Mikro / Paraşüt | Muhasebe yazılımı entegrasyonları |
| Gelişmiş muhasebe | Fiş, mahsup, KDV beyanı vb. |

---

## 5. Temel kullanım senaryoları

### US-01 — Geciken faturaları görme

Finans sorumlusu sabah giriş yapar, gecikmiş faturalar listesini açar; müşteri, tutar, gecikme günü ve atanan kişiye göre filtreler.

### US-02 — Bugün aranacakları yönetme

Sistem veya kullanıcı, vadesi bugün olan takip görevlerini listeler. Sorumlu arama yapar, sonucu aktivite olarak kaydeder, gerekirse yeni görev veya ödeme sözü oluşturur.

### US-03 — Ödeme sözü alma

Müşteri “X tarihte Y TL ödeyeceğim” der. Sorumlu `PaymentPromise` kaydı oluşturur. Söz tarihi gelince listede görünür; ödeme gelirse FULFILLED, gelmezse BROKEN işaretlenir.

### US-04 — Ödeme kaydı ve fatura kapatma

Gelen ödeme sisteme girilir, ilgili faturalara dağıtılır. Fatura durumu `PARTIALLY_PAID` veya `PAID` olur; kalan tutar allocation’lardan hesaplanır.

### US-05 — Riskli müşterileri izleme

Finans müdürü risk seviyesi yüksek müşterileri listeler; gecikme, kırılan sözler ve açık bakiye üzerinden önceliklendirir.

### US-06 — Haftalık tahsilat beklentisi

Yönetici, bu hafta ve sonraki 13 haftanın beklenen tahsilat tutarını görür; nakit planlaması için kullanır.

### US-07 — Excel ile veri yükleme

Pilot müşteri mevcut müşteri/fatura listesini Excel’den yükler. Başarılı/başarısız satırlar raporlanır; hatalı satırlar düzeltilip tekrar denenebilir.

### US-08 — Günlük ekip aktivitesi

Yönetici veya finans müdürü, bir çalışanın gün içinde açtığı görevleri, kayıt ettiği görüşmeleri ve girdiği ödemeleri görür.

### US-09 — Çok kullanıcılı yetki

OWNER/ADMIN kullanıcı davet eder; COLLECTION_AGENT yalnızca kendi atanan işlerini yönetir, VIEWER raporları okur.

---

## 6. Pilot müşteri başarı kriterleri

Pilot başarılı sayılır; aşağıdaki kriterlerin **çoğunluğu** karşılandığında ücretli devam / genişleme değerlendirilir.

### 6.1 Operasyonel kullanım

| Metrik | Hedef |
|--------|-------|
| Aktif kullanıcı | Pilot süresince en az 1 finans sorumlusu haftada ≥3 gün giriş yapar |
| Veri yükleme | En az bir kez müşteri + fatura verisi başarıyla içe aktarılmış olur |
| Günlük kullanım | “Bugün aranacaklar” veya gecikmiş fatura listesi düzenli kullanılır |
| Kayıt disiplini | Ödeme sözü ve/veya görüşme notu pilot süresince sistematik girilir |

### 6.2 İş değeri

| Metrik | Hedef (nitel / nicel) |
|--------|------------------------|
| Görünürlük | Gecikmiş alacaklar tek listede görünür hale gelir (Excel dağınıklığı azalır) |
| Takip | En az bir ödeme sözü → ödeme veya kırılma döngüsü sistemde tamamlanır |
| Planlama | 13+1 haftalık tahsilat beklentisi en az bir yönetim görüşmesinde kullanılır |
| Zaman | Manuel liste hazırlama süresi azalır (pilot sonunda kullanıcı teyidi) |

### 6.3 Ürün kalitesi

| Metrik | Hedef |
|--------|-------|
| Stabilite | Kritik akışlarda (giriş, liste, ödeme, import) pilot süresince bloke edici bug kalmaz |
| Veri doğruluğu | Kalan fatura tutarları allocation kuralına göre tutarlıdır |
| Yetki | Organizasyonlar arası veri sızıntısı olmaz |
| Memnuniyet | Pilot kullanıcı “ücretli devam ederim” veya “şartlı devam” der |

### 6.4 Pilot tanımı (önerilen çerçeve)

- Süre: 4–6 hafta
- Kapsam: 1 organizasyon, gerçek müşteri/fatura verisi
- Çıktı: Kısa pilot raporu (kullanım, bulgular, sonraki özellik önceliği)

---

## 7. Para ve tarih kuralları (NP-003)

Bu kurallar tüm API, veritabanı, import ve UI katmanlarında zorunludur.

### 7.1 Para

| Kural | Karar |
|-------|--------|
| Tip | Para tutarları **Decimal** ile tutulur ve işlenir |
| Yasak | **Float / double kullanılmaz** (JS `number` ile ara hesap da yapılmaz; string veya decimal kütüphanesi) |
| Varsayılan para birimi | İlk sürümde organizasyon `default_currency` = **TRY** |
| Çoklu para birimi | Fatura, ödeme vb. kayıtlarda farklı `currency` saklanabilir |
| Kur dönüşümü | **Yapılmaz** — tutarlar kendi para biriminde kalır; toplamlar aynı currency içinde aggregasyonlanır |
| Karşılaştırma / rapor | Farklı currency’ler tek toplamda birleştirilmez; UI’da currency bazlı gruplanır veya ayrı gösterilir |

**Uygulama notları**

- Backend: Django `DecimalField`; Python `decimal.Decimal`
- API JSON: tutarlar string olarak serileştirilir (örn. `"1500.00"`) — float kaybını önlemek için
- Frontend: Zod/decimal-safe parse; grafik ve özetlerde currency kırılımı korunur
- Allocation ve `remaining_amount` hesapları aynı faturanın currency’si içinde Decimal aritmetiği ile yapılır

### 7.2 Tarih ve saat

| Kural | Karar |
|-------|--------|
| Saklama | Backend tüm datetime değerlerini **UTC** saklar |
| Görüntüleme | Kullanıcı arayüzünde organizasyonun **timezone** alanı kullanılır |
| Tarih-only alanlar | `invoice_date`, `due_date`, `payment_date`, `promised_date`, `forecast_date`, `week_start` takvim tarihi olarak saklanır (timezone kayması için iş kuralı net tutulur) |
| “Bugün” / “bu hafta” | Organizasyon timezone’una göre hesaplanır, sunucu lokal saatine göre değil |
| API | Datetime’lar ISO-8601 UTC (`...Z` veya `+00:00`); istemci org timezone’unda formatlar |

**Uygulama notları**

- Django: `USE_TZ = True`; DB’de timezone-aware UTC
- Organization.timezone (örn. `Europe/Istanbul`) UI ve “bugün aranacaklar” için kaynak
- Celery zamanlanmış işler UTC cron ile çalışır; gün sınırları org timezone ile değerlendirilir

---

## 8. Ürün kuralları (özet)

1. Tüm iş verisi `organization_id` ile izole edilir.
2. Fatura kalan tutarı elle tutulmaz; allocation toplamından hesaplanır.
3. WhatsApp / e-posta kanalları MVP’de yalnızca aktivite/görev tipi olarak kayıt edilir; otomatik gönderim yoktur.
4. Risk ve forecast kural tabanlıdır; yapay zekâ iddiası yapılmaz.
5. Import hataları satır bazında saklanır; kısmi başarı kabul edilir.
6. Kritik create/update/delete işlemleri audit log’a yazılır.
7. Para tutarları Decimal’dir; float yasaktır; varsayılan currency TRY; kur dönüşümü yoktur.
8. Datetime UTC saklanır; UI ve “bugün/bu hafta” org timezone kullanır.

---

## 9. İlgili dokümanlar

- `docs/architecture.md` — teknik mimari (para/tarih uygulama detayı dahil)
- `docs/api.md` — API sözleşmesi
- `docs/database.md` — veri modeli detayı
