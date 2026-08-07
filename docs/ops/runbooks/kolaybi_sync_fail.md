# Runbook — KolayBi senkronizasyonu 3 kez başarısız

## Belirti
- Alarm `kolaybi_sync_fail`
- Connection status = ERROR

## Muhtemel neden
- Geçersiz token / şirket seçimi
- Rate limit (429)
- Distributed lock kaynaklı stuck job

## Kontrol edilecek metrik
- `sync.consecutive_failures` cache
- Son `SyncJob` error_message
- Entegrasyon status component

## Çözüm adımları
1. Bağlantı test endpoint’ini çalıştır
2. Credential yenile
3. Stuck lock varsa Redis `np:lock:integration_sync:*` temizle
4. Manuel sync tetikle

## Rollback adımı
- Önceki connector sürümüne dön; sync frequency’yi hourly’ye düşür

## İletişim kişisi
- Entegrasyonlar on-call
