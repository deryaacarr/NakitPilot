# NP-321 — Database index denetimi & EXPLAIN ANALYZE

## Öncelikli indexler

| Tablo | Index | Amaç |
|-------|-------|------|
| customers | `(organization, created_at)` | Liste / sıralama |
| customers | `(organization, assigned_user)` | Atama filtreleri |
| customers | `(organization, risk_status)` | Risk dağılımı |
| customers | `(organization, source, external_id)` | Entegrasyon upsert |
| invoices | `(organization, status, due_date)` | Aging / overdue |
| invoices | `(organization, customer, status)` | Müşteri faturaları |
| invoices | `(organization, created_at)` | Import / audit |
| invoices | `(organization, source, external_id)` | Sync eşleştirme |
| collection_activities | `(organization, occurred_at)` | Timeline (activity_at) |
| collection_activities | `(organization, customer, occurred_at)` | Müşteri aktivitesi |

## Örnek EXPLAIN ANALYZE kayıtları

```sql
-- Dashboard overdue invoices
EXPLAIN ANALYZE
SELECT id, customer_id, due_date, status
FROM invoices_invoice
WHERE organization_id = 1
  AND status IN ('OPEN', 'OVERDUE', 'PARTIALLY_PAID')
  AND due_date < CURRENT_DATE
ORDER BY due_date
LIMIT 100;
-- Beklenen: Index Scan using inv_org_status_due_idx

-- Customer list by assignee
EXPLAIN ANALYZE
SELECT id, name FROM customers_customer
WHERE organization_id = 1 AND assigned_user_id = 42 AND is_active
ORDER BY name
LIMIT 50;
-- Beklenen: Index Scan using cust_org_assigned_idx

-- Activity timeline
EXPLAIN ANALYZE
SELECT id, summary, occurred_at
FROM collections_collectionactivity
WHERE organization_id = 1 AND customer_id = 99
ORDER BY occurred_at DESC
LIMIT 50;
-- Beklenen: Index Scan using act_org_cust_occurred_idx
```

Kayıtları CI sonrası `ops.loadtest` small profili ile doğrulayın; full profil production-benzeri staging’de çalıştırılmalıdır.
