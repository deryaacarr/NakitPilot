# Runbook — API hata oranı %5 üstü

## Belirti
- Status page / alarm: `api_error_rate`
- 5xx oranı teknik metriklerde yükselir

## Muhtemel neden
- Deploy regresyonu
- DB bağlantı havuzu tükenmesi
- Upstream (KolayBi) timeout’larının API’ye yansıması

## Kontrol edilecek metrik
- `GET /api/ops/metrics/technical/` → `api.error_rate`, `api.p95`, `db_connections`
- Sentry error spike
- `X-Request-Id` ile log korelasyonu

## Çözüm adımları
1. Son deploy’u doğrula; gerekirse rollback
2. Postgres connection / slow query kontrolü
3. Rate-limit / 429 kaynaklı zincir reaksiyonları kontrol et

## Rollback adımı
- Önceki container image’a dön (`docker compose` / prod deploy)

## İletişim kişisi
- On-call backend / Platform
