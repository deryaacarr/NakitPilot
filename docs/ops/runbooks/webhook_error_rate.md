# Runbook — Webhook hata oranı yükseldi

## Belirti
- Alarm `webhook_error_rate`

## Muhtemel neden
- Müşteri endpoint down
- Signature mismatch
- Queue backlog

## Kontrol edilecek metrik
- `webhook_success_rate`
- WebhookDelivery failed count

## Çözüm adımları
1. Son failed delivery body’lerini (maskeli) incele
2. Endpoint health kontrol
3. Retry / disable bozuk subscription

## Rollback adımı
- Webhook gönderimini geçici kapat

## İletişim kişisi
- Developers / Integrations
