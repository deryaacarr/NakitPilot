"""NP-103: risk recalculation triggers.

Yeniden hesaplanır:
- Yeni fatura
- Yeni ödeme
- Ödeme iptali
- Söz verilmesi
- Sözün bozulması
- Görev tamamlanması
- Günlük gece görevi (Celery beat → risk.calculate_customer_risk)
"""

from __future__ import annotations

from typing import Any

from apps.customers.models import Customer
from apps.risk.services import calculate_customer_risk


def bump_customer_risk(customer: Customer | int, *, as_of=None) -> dict[str, Any]:
    """Recalculate and persist risk for one customer (sync)."""
    customer_id = customer if isinstance(customer, int) else customer.pk
    return calculate_customer_risk(customer_id, as_of=as_of)


def bump_customers_risk(customer_ids: set[int] | list[int]) -> int:
    """Recalculate distinct customers; returns count updated."""
    updated = 0
    for cid in set(customer_ids):
        calculate_customer_risk(cid)
        updated += 1
    return updated
