"""Dashboard summary, aging, call list, and overview (NP-120–124)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Prefetch
from django.utils import timezone

from apps.collections.models import (
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.collections.services import compute_priority_score
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer, RiskStatus
from apps.forecasting.weekly import calculate_organization_forecast, iso_week_start
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_overdue_days
from apps.organizations.models import Organization
from apps.payments.models import ZERO, PaymentAllocation

QUANTIZE = Decimal("0.01")
OPEN_INVOICE_STATUSES = {
    InvoiceStatus.OPEN,
    InvoiceStatus.OVERDUE,
    InvoiceStatus.PARTIALLY_PAID,
}
OPEN_TASK_STATUSES = {
    CollectionTaskStatus.OPEN,
    CollectionTaskStatus.IN_PROGRESS,
}

AGING_BUCKETS: list[tuple[str, str, int | None, int | None]] = [
    # code, label, min_days inclusive, max_days inclusive (None = open)
    ("not_due", "Vadesi gelmemiş", None, 0),
    ("d1_15", "1–15 gün", 1, 15),
    ("d16_30", "16–30 gün", 16, 30),
    ("d31_60", "31–60 gün", 31, 60),
    ("d61_90", "61–90 gün", 61, 90),
    ("d90_plus", "90+ gün", 91, None),
]


def _money(value: Decimal) -> str:
    return str(Decimal(str(value)).quantize(QUANTIZE, rounding=ROUND_HALF_UP))


def _bucket_code(overdue_days: int) -> str:
    if overdue_days <= 0:
        return "not_due"
    if overdue_days <= 15:
        return "d1_15"
    if overdue_days <= 30:
        return "d16_30"
    if overdue_days <= 60:
        return "d31_60"
    if overdue_days <= 90:
        return "d61_90"
    return "d90_plus"


def _open_invoices(organization_id: int):
    return (
        Invoice.objects.filter(
            organization_id=organization_id,
            status__in=OPEN_INVOICE_STATUSES,
        )
        .select_related("customer")
        .prefetch_related(
            Prefetch(
                "allocations",
                queryset=PaymentAllocation.objects.filter(
                    payment__cancelled_at__isnull=True
                ).only("amount", "invoice_id", "payment_id"),
            )
        )
        .order_by("due_date", "id")
    )


def dashboard_summary(
    organization_id: int,
    *,
    as_of: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """NP-120 summary cards (point-in-time + period-aware promise/expected)."""
    today = as_of or timezone.localdate()
    period_from = date_from or today
    period_to = date_to or today
    currency = "TRY"
    org = Organization.objects.filter(pk=organization_id).first()
    if org is not None:
        currency = (org.default_currency or "TRY").upper()

    open_total = ZERO
    overdue_total = ZERO
    for inv in _open_invoices(organization_id).filter(currency=currency):
        rem = inv.remaining_amount()
        if rem <= ZERO:
            continue
        open_total += rem
        if invoice_overdue_days(inv, as_of=today) > 0:
            overdue_total += rem

    week_starts = []
    cursor = iso_week_start(period_from)
    last = iso_week_start(period_to)

    while cursor <= last:
        week_starts.append(cursor)
        cursor += timedelta(weeks=1)
    n_weeks = max(len(week_starts), 1)
    forecast = calculate_organization_forecast(
        organization_id,
        as_of=period_from,
        persist=False,
        weeks=n_weeks,
        currency=currency,
    )
    period_expected = ZERO
    for w in forecast["weeks"]:
        if w["week_start"] in week_starts:
            period_expected += w["expected_amount"]

    promises_in_period = PaymentPromise.objects.filter(
        organization_id=organization_id,
        status=PaymentPromiseStatus.PENDING,
        promised_date__gte=period_from,
        promised_date__lte=period_to,
    ).count()
    promises_broken = PaymentPromise.objects.filter(
        organization_id=organization_id,
        status=PaymentPromiseStatus.BROKEN,
        promised_date__gte=period_from,
        promised_date__lte=period_to,
    ).count()
    # If preset collapses to "all broken stock" when no date overlap — still show
    # period-scoped broken; for open critical/tasks use as_of.
    critical_customers = Customer.objects.filter(
        organization_id=organization_id,
        is_active=True,
        risk_status=RiskStatus.CRITICAL,
    ).count()
    overdue_tasks = CollectionTask.objects.filter(
        organization_id=organization_id,
        status__in=OPEN_TASK_STATUSES,
        due_date__lt=today,
    ).count()

    return {
        "as_of": today.isoformat(),
        "currency": currency,
        "cards": {
            "open_receivables": _money(open_total),
            "overdue_receivables": _money(overdue_total),
            "expected_this_week": _money(period_expected),
            "promises_today": promises_in_period,
            "promises_broken": promises_broken,
            "critical_customers": critical_customers,
            "overdue_tasks": overdue_tasks,
        },
        "week_start": iso_week_start(today).isoformat(),
        "date_from": period_from.isoformat(),
        "date_to": period_to.isoformat(),
    }


def aging_report(organization_id: int, *, as_of: date | None = None) -> dict[str, Any]:
    """NP-121 aging buckets for open invoices."""
    today = as_of or timezone.localdate()
    org = Organization.objects.get(pk=organization_id)
    currency = (org.default_currency or "TRY").upper()

    buckets: dict[str, dict[str, Any]] = {
        code: {
            "code": code,
            "label": label,
            "customer_ids": set(),
            "invoice_count": 0,
            "open_amount": ZERO,
        }
        for code, label, _mn, _mx in AGING_BUCKETS
    }

    grand = ZERO
    for inv in _open_invoices(organization_id).filter(currency=currency):
        rem = inv.remaining_amount()
        if rem <= ZERO:
            continue
        days = invoice_overdue_days(inv, as_of=today)
        code = _bucket_code(days)
        bucket = buckets[code]
        bucket["customer_ids"].add(inv.customer_id)
        bucket["invoice_count"] += 1
        bucket["open_amount"] += rem
        grand += rem

    groups = []
    for code, label, _mn, _mx in AGING_BUCKETS:
        b = buckets[code]
        amount = Decimal(str(b["open_amount"])).quantize(QUANTIZE)
        share = (
            (amount / grand).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if grand > ZERO
            else ZERO
        )
        groups.append(
            {
                "code": code,
                "label": label,
                "customer_count": len(b["customer_ids"]),
                "invoice_count": b["invoice_count"],
                "open_amount": _money(amount),
                "share": str(share),
                "share_percent": float(
                    (share * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
            }
        )

    return {
        "as_of": today.isoformat(),
        "currency": currency,
        "total_open_amount": _money(grand),
        "groups": groups,
    }


def today_call_list(
    organization_id: int,
    *,
    as_of: date | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """NP-122: top N customers by priority score."""
    today = as_of or timezone.localdate()
    customers = list(
        Customer.objects.filter(organization_id=organization_id, is_active=True).order_by("id")
    )
    if not customers:
        return {"as_of": today.isoformat(), "results": []}

    promise_today_ids = set(
        PaymentPromise.objects.filter(
            organization_id=organization_id,
            status=PaymentPromiseStatus.PENDING,
            promised_date=today,
        ).values_list("customer_id", flat=True)
    )
    broken_ids = set(
        PaymentPromise.objects.filter(
            organization_id=organization_id,
            status=PaymentPromiseStatus.BROKEN,
        ).values_list("customer_id", flat=True)
    )
    today_promises = {
        p.customer_id: p
        for p in PaymentPromise.objects.filter(
            organization_id=organization_id,
            status=PaymentPromiseStatus.PENDING,
            promised_date=today,
        ).order_by("id")
    }

    scored: list[dict[str, Any]] = []
    for customer in customers:
        metrics = customer_financial_metrics(customer)
        overdue = Decimal(str(metrics.get("overdue_balance") or ZERO))
        open_bal = Decimal(str(metrics.get("open_balance") or ZERO))
        # Focus call list on customers with something to collect
        if open_bal <= ZERO and customer.id not in promise_today_ids:
            continue

        score, level, _ = compute_priority_score(
            customer,
            as_of=today,
            promise_today=customer.id in promise_today_ids,
            promise_broken=customer.id in broken_ids,
        )
        promise = today_promises.get(customer.id)
        scored.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "customer_code": customer.code or "",
                "overdue_balance": _money(overdue),
                "oldest_overdue_days": metrics.get("oldest_overdue_days"),
                "risk_status": customer.risk_status,
                "risk_score": int(customer.risk_score or 0),
                "last_contact_at": (
                    customer.last_contact_at.isoformat().replace("+00:00", "Z")
                    if customer.last_contact_at
                    else None
                ),
                "payment_promise": (
                    {
                        "id": promise.id,
                        "amount": _money(promise.amount),
                        "promised_date": promise.promised_date.isoformat(),
                        "status": promise.status,
                    }
                    if promise
                    else None
                ),
                "priority_score": score,
                "priority": level,
            }
        )

    scored.sort(key=lambda row: (-row["priority_score"], -Decimal(row["overdue_balance"]), row["customer_id"]))
    return {
        "as_of": today.isoformat(),
        "results": scored[:limit],
    }


def dashboard_overview(
    organization_id: int,
    *,
    as_of: date | None = None,
    preset: str = "week",
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """Combined payload for the dashboard home screen (NP-120–124)."""
    from apps.dashboard.performance import performance_report, resolve_date_range

    rng = resolve_date_range(
        preset=preset,
        date_from=date_from,
        date_to=date_to,
        today=as_of,
    )
    end = rng["date_to"]
    start = rng["date_from"]
    return {
        "range": {
            "preset": rng["preset"],
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        },
        "summary": dashboard_summary(
            organization_id,
            as_of=end,
            date_from=start,
            date_to=end,
        ),
        "aging": aging_report(organization_id, as_of=end),
        "call_list": today_call_list(organization_id, as_of=end, limit=10),
        "performance": performance_report(
            organization_id,
            date_from=start,
            date_to=end,
        ),
    }
