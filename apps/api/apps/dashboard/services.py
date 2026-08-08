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


def _change_pct(current: Decimal, previous: Decimal) -> float | None:
    if previous == ZERO:
        return None if current == ZERO else 100.0
    return float(
        ((current - previous) / previous * Decimal("100")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    )


def _receivables_totals(
    organization_id: int, *, as_of: date, currency: str
) -> tuple[Decimal, Decimal, int, int]:
    """Open + overdue totals and invoice counts as of a date (current remaining)."""
    open_total = ZERO
    overdue_total = ZERO
    open_count = 0
    overdue_count = 0
    for inv in _open_invoices(organization_id).filter(currency=currency):
        rem = inv.remaining_amount()
        if rem <= ZERO:
            continue
        # Invoice not yet issued relative to as_of
        if inv.invoice_date and inv.invoice_date > as_of:
            continue
        open_total += rem
        open_count += 1
        if invoice_overdue_days(inv, as_of=as_of) > 0:
            overdue_total += rem
            overdue_count += 1
    return open_total, overdue_total, open_count, overdue_count


PRIORITY_REASON_LABELS = {
    "promise_broken": "Bozulan ödeme sözü",
    "promise_today": "Bugün ödeme sözü var",
    "overdue_amount_high": "Yüksek gecikmiş bakiye",
    "overdue_days_gt_30": "30+ gün gecikme",
    "high_risk": "Yüksek risk skoru",
    "no_contact_7d": "7 gündür görüşülmedi",
}


def _priority_reason(details: dict[str, Any]) -> str:
    if not details:
        return "Açık bakiye / tahsilat önceliği"
    # Highest weight first
    ordered = sorted(details.items(), key=lambda item: (-item[1], item[0]))
    parts = [PRIORITY_REASON_LABELS.get(key, key) for key, _ in ordered[:2]]
    return " · ".join(parts)


def _suggested_action(
    *,
    promise_today: bool,
    promise_broken: bool,
    oldest_overdue_days: int | None,
    last_contact_at,
) -> str:
    if promise_broken:
        return "Bozulan sözü takip et"
    if promise_today:
        return "Sözü teyit et / ara"
    if oldest_overdue_days is not None and oldest_overdue_days > 30:
        return "Acil ara"
    if last_contact_at is None:
        return "İlk teması kur"
    return "Ara ve durum al"


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

    open_total, overdue_total, open_invoice_count, overdue_invoice_count = _receivables_totals(
        organization_id, as_of=today, currency=currency
    )
    prev_as_of = today - timedelta(days=30)
    prev_open, prev_overdue, _, _ = _receivables_totals(
        organization_id, as_of=prev_as_of, currency=currency
    )

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
    today_tasks = CollectionTask.objects.filter(
        organization_id=organization_id,
        status__in=OPEN_TASK_STATUSES,
        due_date=today,
    ).count()
    customer_count = Customer.objects.filter(
        organization_id=organization_id, is_active=True
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
            "today_tasks": today_tasks,
        },
        "comparisons": {
            "open_receivables": {
                "previous": _money(prev_open),
                "change_pct": _change_pct(open_total, prev_open),
                "direction_good_when": "down",
                "label": "Geçen aya göre",
            },
            "overdue_receivables": {
                "previous": _money(prev_overdue),
                "change_pct": _change_pct(overdue_total, prev_overdue),
                "direction_good_when": "down",
                "label": "Geçen aya göre",
            },
            "expected_this_week": {
                "previous": None,
                "change_pct": None,
                "direction_good_when": "up",
                "label": "Dönem beklentisi",
            },
            "promises_broken": {
                "previous": None,
                "change_pct": None,
                "direction_good_when": "down",
                "label": "Dönem içi",
            },
            "critical_customers": {
                "previous": None,
                "change_pct": None,
                "direction_good_when": "down",
                "label": "Anlık",
            },
            "overdue_tasks": {
                "previous": None,
                "change_pct": None,
                "direction_good_when": "down",
                "label": "Anlık",
            },
        },
        "meta": {
            "customer_count": customer_count,
            "open_invoice_count": open_invoice_count,
            "overdue_invoice_count": overdue_invoice_count,
            "is_empty": customer_count == 0,
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
    """NP-122 / NP-393: top N customers by priority score with action context."""
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
    pending_promises = {}
    for p in (
        PaymentPromise.objects.filter(
            organization_id=organization_id,
            status=PaymentPromiseStatus.PENDING,
        )
        .order_by("promised_date", "id")
    ):
        pending_promises.setdefault(p.customer_id, p)

    open_tasks = {}
    for task in (
        CollectionTask.objects.filter(
            organization_id=organization_id,
            status__in=OPEN_TASK_STATUSES,
        )
        .order_by("due_date", "id")
        .only("id", "customer_id", "due_date", "title")
    ):
        open_tasks.setdefault(task.customer_id, task)

    scored: list[dict[str, Any]] = []
    for customer in customers:
        metrics = customer_financial_metrics(customer)
        overdue = Decimal(str(metrics.get("overdue_balance") or ZERO))
        open_bal = Decimal(str(metrics.get("open_balance") or ZERO))
        if open_bal <= ZERO and customer.id not in promise_today_ids:
            continue

        score, level, details = compute_priority_score(
            customer,
            as_of=today,
            promise_today=customer.id in promise_today_ids,
            promise_broken=customer.id in broken_ids,
        )
        promise = pending_promises.get(customer.id)
        task = open_tasks.get(customer.id)
        oldest = metrics.get("oldest_overdue_days")
        scored.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "customer_code": customer.code or "",
                "customer_phone": customer.phone or "",
                "overdue_balance": _money(overdue),
                "oldest_overdue_days": oldest,
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
                "open_task_id": task.id if task else None,
                "priority_score": score,
                "priority": level,
                "priority_reason": _priority_reason(details),
                "suggested_action": _suggested_action(
                    promise_today=customer.id in promise_today_ids,
                    promise_broken=customer.id in broken_ids,
                    oldest_overdue_days=oldest,
                    last_contact_at=customer.last_contact_at,
                ),
            }
        )

    scored.sort(
        key=lambda row: (-row["priority_score"], -Decimal(row["overdue_balance"]), row["customer_id"])
    )
    return {
        "as_of": today.isoformat(),
        "results": scored[:limit],
    }


def _serialize_task(task: CollectionTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "customer_id": task.customer_id,
        "customer_name": getattr(task.customer, "name", "") if task.customer_id else "",
        "priority": task.priority,
        "priority_score": task.priority_score,
    }


def agent_workboard(
    organization_id: int,
    *,
    as_of: date | None = None,
    user_id: int | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """NP-391 — collection agent focused widgets."""
    today = as_of or timezone.localdate()
    tasks = CollectionTask.objects.filter(
        organization_id=organization_id,
        status__in=OPEN_TASK_STATUSES,
    ).select_related("customer")
    if user_id:
        tasks = tasks.filter(assigned_to_id=user_id)

    today_tasks = list(tasks.filter(due_date=today).order_by("-priority_score", "id")[:limit])
    overdue_tasks = list(
        tasks.filter(due_date__lt=today).order_by("due_date", "-priority_score")[:limit]
    )

    promises = PaymentPromise.objects.filter(
        organization_id=organization_id,
        status=PaymentPromiseStatus.PENDING,
        promised_date=today,
    ).select_related("customer")
    if user_id:
        # Prefer promises for customers the agent is working
        agent_customer_ids = CollectionTask.objects.filter(
            organization_id=organization_id,
            assigned_to_id=user_id,
            status__in=OPEN_TASK_STATUSES,
        ).values_list("customer_id", flat=True)
        promises = promises.filter(customer_id__in=agent_customer_ids)

    promise_rows = [
        {
            "id": p.id,
            "customer_id": p.customer_id,
            "customer_name": p.customer.name,
            "amount": _money(p.amount),
            "promised_date": p.promised_date.isoformat(),
            "status": p.status,
        }
        for p in promises.order_by("id")[:limit]
    ]

    from apps.collections.models import CollectionActivity

    activities_qs = CollectionActivity.objects.filter(
        organization_id=organization_id
    ).select_related("customer", "created_by")
    if user_id:
        activities_qs = activities_qs.filter(created_by_id=user_id)
    recent_activities = [
        {
            "id": a.id,
            "customer_id": a.customer_id,
            "customer_name": a.customer.name if a.customer_id else "",
            "activity_type": a.activity_type,
            "summary": a.summary,
            "occurred_at": a.occurred_at.isoformat().replace("+00:00", "Z"),
        }
        for a in activities_qs.order_by("-occurred_at", "-id")[:limit]
    ]

    return {
        "as_of": today.isoformat(),
        "today_tasks": [_serialize_task(t) for t in today_tasks],
        "overdue_tasks": [_serialize_task(t) for t in overdue_tasks],
        "promises_today": promise_rows,
        "recent_activities": recent_activities,
    }


def risk_distribution(organization_id: int) -> dict[str, Any]:
    from django.db.models import Count

    counts: dict[str, int] = {
        RiskStatus.LOW: 0,
        RiskStatus.MEDIUM: 0,
        RiskStatus.HIGH: 0,
        RiskStatus.CRITICAL: 0,
    }
    for row in (
        Customer.objects.filter(organization_id=organization_id, is_active=True)
        .values("risk_status")
        .annotate(count=Count("id"))
    ):
        counts[row["risk_status"]] = row["count"]
    return {
        "groups": [
            {"status": status, "count": counts.get(status, 0)}
            for status in (
                RiskStatus.LOW,
                RiskStatus.MEDIUM,
                RiskStatus.HIGH,
                RiskStatus.CRITICAL,
            )
        ]
    }


def forecast_snippet(organization_id: int, *, as_of: date | None = None) -> dict[str, Any]:
    today = as_of or timezone.localdate()
    currency = "TRY"
    org = Organization.objects.filter(pk=organization_id).first()
    if org is not None:
        currency = (org.default_currency or "TRY").upper()
    forecast = calculate_organization_forecast(
        organization_id,
        as_of=today,
        persist=False,
        weeks=4,
        currency=currency,
    )
    weeks = [
        {
            "week_start": w["week_start"].isoformat()
            if hasattr(w["week_start"], "isoformat")
            else str(w["week_start"]),
            "expected_amount": _money(w["expected_amount"]),
        }
        for w in forecast.get("weeks", [])[:4]
    ]
    total = sum((Decimal(w["expected_amount"]) for w in weeks), ZERO)
    return {"currency": currency, "weeks": weeks, "total_expected": _money(total)}


def dashboard_overview(
    organization_id: int,
    *,
    as_of: date | None = None,
    preset: str = "week",
    date_from: date | None = None,
    date_to: date | None = None,
    user_id: int | None = None,
    include_agent: bool = True,
) -> dict[str, Any]:
    """Combined payload for the dashboard home screen (EPIC 39 / NP-120–124)."""
    from apps.dashboard.performance import performance_report, resolve_date_range

    rng = resolve_date_range(
        preset=preset,
        date_from=date_from,
        date_to=date_to,
        today=as_of,
    )
    end = rng["date_to"]
    start = rng["date_from"]
    payload = {
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
        "risk_distribution": risk_distribution(organization_id),
        "forecast": forecast_snippet(organization_id, as_of=end),
    }
    if include_agent:
        payload["agent"] = agent_workboard(organization_id, as_of=end, user_id=user_id)
    return payload
