"""NP-351 — eligibility rules for legal handoff (advisory, not a legal decision)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.collections.models import (
    CollectionActivity,
    CollectionActivityType,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer

DEFAULT_MIN_OVERDUE_DAYS = 90
DEFAULT_MIN_BROKEN_PROMISES = 2
DEFAULT_MIN_BALANCE = Decimal("10000.00")
DEFAULT_NO_CONTACT_DAYS = 30


def evaluate_legal_handoff_criteria(
    customer: Customer,
    *,
    organization=None,
    as_of=None,
    min_overdue_days: int = DEFAULT_MIN_OVERDUE_DAYS,
    min_broken_promises: int = DEFAULT_MIN_BROKEN_PROMISES,
    min_balance: Decimal = DEFAULT_MIN_BALANCE,
    no_contact_days: int = DEFAULT_NO_CONTACT_DAYS,
    manager_approved: bool = False,
) -> dict[str, Any]:
    """
    Evaluate handoff *candidates*. Does not transfer or decide legal action.

    Manager approval is required separately before creating/activating a case.
    """
    org = organization or customer.organization
    today = as_of or timezone.localdate()
    metrics = customer_financial_metrics(customer)
    overdue_days = int(metrics.get("oldest_overdue_days") or 0)
    open_balance = Decimal(str(metrics.get("open_balance") or "0"))

    broken_count = PaymentPromise.objects.filter(
        organization=org,
        customer=customer,
        status=PaymentPromiseStatus.BROKEN,
    ).count()

    contact_cutoff = timezone.now() - timedelta(days=no_contact_days)
    recent_contact = (
        CollectionActivity.objects.filter(
            organization=org,
            customer=customer,
            activity_type__in=[
                CollectionActivityType.CALL,
                CollectionActivityType.EMAIL,
                CollectionActivityType.NOTE,
                CollectionActivityType.TASK_COMPLETED,
            ],
            occurred_at__gte=contact_cutoff,
        ).exists()
        or (
            customer.last_contact_at is not None
            and customer.last_contact_at >= contact_cutoff
        )
    )

    rules = [
        {
            "code": "overdue_days_90",
            "label": f"{min_overdue_days}+ gün gecikme",
            "met": overdue_days >= min_overdue_days,
            "value": overdue_days,
            "threshold": min_overdue_days,
        },
        {
            "code": "broken_promises",
            "label": f"En az {min_broken_promises} bozulan ödeme sözü",
            "met": broken_count >= min_broken_promises,
            "value": broken_count,
            "threshold": min_broken_promises,
        },
        {
            "code": "balance_threshold",
            "label": f"Bakiye ≥ {min_balance}",
            "met": open_balance >= min_balance,
            "value": str(open_balance),
            "threshold": str(min_balance),
        },
        {
            "code": "no_contact_30d",
            "label": f"Son {no_contact_days} günde iletişim yok",
            "met": not recent_contact,
            "value": not recent_contact,
            "threshold": no_contact_days,
        },
        {
            "code": "manager_approval",
            "label": "Yönetici onayı",
            "met": bool(manager_approved),
            "value": bool(manager_approved),
            "threshold": True,
        },
    ]

    operational_met = all(r["met"] for r in rules if r["code"] != "manager_approval")
    eligible = operational_met and manager_approved

    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "as_of": today.isoformat(),
        "open_balance": str(open_balance),
        "overdue_days": overdue_days,
        "broken_promises": broken_count,
        "recent_contact": recent_contact,
        "rules": rules,
        "operational_criteria_met": operational_met,
        "eligible_for_handoff": eligible,
        "disclaimer": (
            "Bu değerlendirme yalnızca dosya hazırlık adayıdır; hukuki karar veya "
            "otomatik takip başlatmaz."
        ),
    }
