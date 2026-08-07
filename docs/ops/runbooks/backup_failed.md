# Runbook — Backup başarısız

## Belirti
- Alarm `backup_failed`
- `run_backup` exit != 0

## Muhtemel neden
- Disk dolu
- S3 credential
- Postgres dump hatası

## Kontrol edilecek metrik
- `disk.usage_pct`
- Backup script logları (`infrastructure/scripts`)

## Çözüm adımları
1. Disk temizliği / volume büyütme
2. Credential doğrula
3. Manuel `run_backup` çalıştır

## Rollback adımı
- Son başarılı backup’tan restore prosedürü

## İletişim kişisi
- Platform / DBA
