"""NP-123/124: date ranges and collection performance."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import ProgrammingError
from django.db.models import Count
from django.utils import timezone

from apps.collections.models import (
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.forecasting.models import ForecastSnapshot
from apps.forecasting.weekly import calculate_organization_forecast, iso_week_start
from apps.organizations.models import Organization
from apps.payments.models import ZERO, Payment

QUANTIZE = Decimal("0.01")

DATE_PRESETS = ("today", "week", "month", "last_30", "custom")


class DateRangeError(ValueError):
    pass


def _money(value: Decimal) -> str:
    return str(Decimal(str(value)).quantize(QUANTIZE))


def resolve_date_range(
    *,
    preset: str = "week",
    date_from: date | None = None,
    date_to: date | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """NP-124: Bugün / Bu hafta / Bu ay / Son 30 gün / Özel aralık."""
    today = today or timezone.localdate()
    key = (preset or "week").strip().lower()
    if key not in DATE_PRESETS:
        raise DateRangeError(f"preset must be one of: {', '.join(DATE_PRESETS)}")

    if key == "today":
        start, end = today, today
    elif key == "week":
        start, end = iso_week_start(today), today
    elif key == "month":
        start, end = today.replace(day=1), today
    elif key == "last_30":
        start, end = today - timedelta(days=29), today
    else:  # custom
        if date_from is None or date_to is None:
            raise DateRangeError("custom range requires date_from and date_to.")
        start, end = date_from, date_to
        if start > end:
            start, end = end, start

    if (end - start).days > 366:
        raise DateRangeError("Date range cannot exceed 366 days.")

    return {
        "preset": key,
        "date_from": start,
        "date_to": end,
        "as_of": end,
    }


def _week_starts(date_from: date, date_to: date) -> list[date]:
    starts: list[date] = []
    cursor = iso_week_start(date_from)
    last = iso_week_start(date_to)
    while cursor <= last:
        starts.append(cursor)
        cursor += timedelta(weeks=1)
    return starts


def _aware_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.get_current_timezone())
    if timezone.is_naive(end):
        end = timezone.make_aware(end, timezone.get_current_timezone())
    return start, end


def performance_report(
    organization_id: int,
    *,
    date_from: date,
    date_to: date,
    currency: str | None = None,
) -> dict[str, Any]:
    """NP-123: weekly actual/expected, tasks by user, kept vs broken promises."""
    org = Organization.objects.get(pk=organization_id)
    cur = (currency or org.default_currency or "TRY").upper()
    weeks = _week_starts(date_from, date_to)
    n_weeks = max(len(weeks), 1)

    # Expected: prefer stored snapshots, else live forecast as of range start
    expected_map: dict[date, Decimal] = {}
    try:
        snaps = (
            ForecastSnapshot.objects.filter(
                organization_id=organization_id,
                currency=cur,
                week_start__in=weeks,
            )
            .order_by("week_start", "-calculated_at", "-id")
        )
        seen: set[date] = set()
        for snap in snaps:
            if snap.week_start in seen:
                continue
            seen.add(snap.week_start)
            expected_map[snap.week_start] = Decimal(str(snap.expected_amount))
    except ProgrammingError:
        # Migration not applied yet — fall through to live forecast
        expected_map = {}

    missing = [w for w in weeks if w not in expected_map]
    if missing:
        forecast = calculate_organization_forecast(
            organization_id,
            as_of=date_from,
            persist=False,
            weeks=n_weeks,
            currency=cur,
        )
        for w in forecast["weeks"]:
            ws = w["week_start"]
            if ws in missing and ws not in expected_map:
                expected_map[ws] = Decimal(str(w["expected_amount"]))

    actual_map: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for payment in Payment.objects.filter(
        organization_id=organization_id,
        currency=cur,
        cancelled_at__isnull=True,
        payment_date__gte=date_from,
        payment_date__lte=date_to,
    ).only("amount", "payment_date"):
        actual_map[iso_week_start(payment.payment_date)] += Decimal(str(payment.amount))

    weekly = []
    total_actual = ZERO
    total_expected = ZERO
    for ws in weeks:
        actual = Decimal(str(actual_map.get(ws, ZERO))).quantize(QUANTIZE)
        expected = Decimal(str(expected_map.get(ws, ZERO))).quantize(QUANTIZE)
        total_actual += actual
        total_expected += expected
        weekly.append(
            {
                "week_start": ws.isoformat(),
                "week_end": (ws + timedelta(days=6)).isoformat(),
                "actual": _money(actual),
                "expected": _money(expected),
            }
        )

    start_dt, end_dt = _aware_bounds(date_from, date_to)
    User = get_user_model()
    task_rows = (
        CollectionTask.objects.filter(
            organization_id=organization_id,
            status=CollectionTaskStatus.COMPLETED,
            completed_at__gte=start_dt,
            completed_at__lte=end_dt,
        )
        .values("assigned_to")
        .annotate(completed_count=Count("id"))
        .order_by("-completed_count")
    )
    user_ids = [r["assigned_to"] for r in task_rows if r["assigned_to"]]
    names = {
        u.id: (u.get_full_name() or u.email or f"User {u.id}")
        for u in User.objects.filter(id__in=user_ids)
    }
    tasks_by_user = [
        {
            "user_id": row["assigned_to"],
            "user_name": (
                names.get(row["assigned_to"], "Atanmamış")
                if row["assigned_to"]
                else "Atanmamış"
            ),
            "completed_count": row["completed_count"],
        }
        for row in task_rows
    ]

    kept = PaymentPromise.objects.filter(
        organization_id=organization_id,
        status__in=[
            PaymentPromiseStatus.FULFILLED,
            PaymentPromiseStatus.PARTIALLY_FULFILLED,
        ],
        promised_date__gte=date_from,
        promised_date__lte=date_to,
    ).count()
    # Also count by fulfilled_at falling in range
    kept_by_fulfillment = (
        PaymentPromise.objects.filter(
            organization_id=organization_id,
            status__in=[
                PaymentPromiseStatus.FULFILLED,
                PaymentPromiseStatus.PARTIALLY_FULFILLED,
            ],
            fulfilled_at__gte=start_dt,
            fulfilled_at__lte=end_dt,
        )
        .exclude(promised_date__gte=date_from, promised_date__lte=date_to)
        .count()
    )
    kept_total = kept + kept_by_fulfillment

    broken = PaymentPromise.objects.filter(
        organization_id=organization_id,
        status=PaymentPromiseStatus.BROKEN,
        promised_date__gte=date_from,
        promised_date__lte=date_to,
    ).count()

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "currency": cur,
        "weekly": weekly,
        "totals": {
            "actual": _money(total_actual),
            "expected": _money(total_expected),
        },
        "tasks_by_user": tasks_by_user,
        "promises": {
            "kept": kept_total,
            "broken": broken,
        },
    }
