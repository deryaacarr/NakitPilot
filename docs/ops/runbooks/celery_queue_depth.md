# Runbook — Celery kuyruk derinliği > 10.000

## Belirti
- Alarm `celery_queue_depth`
- Bildirimler gecikir; import kuyruğu şişer

## Muhtemel neden
- Tek worker tüm kuyrukları tüketemiyor
- Import bombardımanı
- Failed task retry fırtınası

## Kontrol edilecek metrik
- `celery_queues` per-queue depths
- Worker sayısı / `-Q` listesi

## Çözüm adımları
1. Import worker scale-out (`-Q imports`)
2. Notifications worker’ı ayrı tut
3. Başarısız task’ları purge / retry limit

## Rollback adımı
- Geçici olarak non-critical beat job’ları durdur

## İletişim kişisi
- Platform / Celery on-call
