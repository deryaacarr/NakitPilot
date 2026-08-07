# Runbook — Ödeme sağlayıcısı çalışmıyor

## Belirti
- Alarm `billing.provider_down`
- Checkout / webhook başarısız

## Muhtemel neden
- Mock/provider outage
- Webhook secret uyumsuzluğu

## Kontrol edilecek metrik
- Billing payment attempts failed
- Status component (API)

## Çözüm adımları
1. Provider status sayfasını kontrol et
2. Webhook imza doğrulamasını test et
3. Dunning / grace period’u izle

## Rollback adımı
- Önceki provider config’e dön; yeni checkout’u durdur

## İletişim kişisi
- Billing on-call
