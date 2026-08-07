# Runbook — Disk kullanımı %80+

## Belirti
- Alarm `disk_usage`

## Muhtemel neden
- Import dosyaları / export artıkları
- Postgres WAL büyümesi

## Kontrol edilecek metrik
- `disk.usage_pct`
- Retention / archive dry-run sonuçları

## Çözüm adımları
1. `POST /api/ops/archive/` dry_run ile eski webhook/notification temizliği
2. Export TTL job’ını zorla çalıştır
3. Volume expand

## Rollback adımı
- N/A (kalıcı temizlik)

## İletişim kişisi
- Platform
