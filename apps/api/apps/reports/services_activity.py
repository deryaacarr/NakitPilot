"""NP-161 — tahsilat aktivite raporu (kullanıcı bazında)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from apps.collections.models import (
    CollectionActivity,
    CollectionActivityType,
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.dashboard.performance import DateRangeError, resolve_date_range
from apps.payments.models import Payment

QUANTIZE = Decimal("0.01")
ZERO = Decimal("0.00")
CONTACT_TYPES = {
    CollectionActivityType.CALL,
    CollectionActivityType.EMAIL,
    CollectionActivityType.WHATSAPP,
}


def _money(value: Decimal) -> str:
    return str(Decimal(str(value or ZERO)).quantize(QUANTIZE))


def _aware_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.get_current_timezone())
    if timezone.is_naive(end):
        end = timezone.make_aware(end, timezone.get_current_timezone())
    return start, end


def collection_activity_report(
    organization,
    *,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Filters: preset / date_from / date_to (NP-124 style).
    Columns per user (NP-161).
    """
    f = filters or {}
    preset = str(f.get("preset") or "month").strip().lower()
    date_from = None
    date_to = None
    raw_from = str(f.get("date_from") or "").strip()
    raw_to = str(f.get("date_to") or "").strip()
    if raw_from:
        try:
            date_from = datetime.strptime(raw_from[:10], "%Y-%m-%d").date()
        except ValueError:
            date_from = None
    if raw_to:
        try:
            date_to = datetime.strptime(raw_to[:10], "%Y-%m-%d").date()
        except ValueError:
            date_to = None
    try:
        rng = resolve_date_range(
            preset=preset if preset != "custom" or (date_from and date_to) else (
                "custom" if date_from and date_to else preset
            ),
            date_from=date_from,
            date_to=date_to,
        )
    except DateRangeError:
        today = timezone.localdate()
        rng = {
            "date_from": today - timedelta(days=29),
            "date_to": today,
            "preset": "last_30",
        }

    start_d: date = rng["date_from"]
    end_d: date = rng["date_to"]
    start_dt, end_dt = _aware_bounds(start_d, end_d)

    User = get_user_model()
    # Users who appear in org activity in the window (or membership active)
    from apps.organizations.models import Membership

    member_ids = list(
        Membership.objects.filter(organization=organization, is_active=True).values_list(
            "user_id", flat=True
        )
    )
    users = {
        u.id: u
        for u in User.objects.filter(id__in=member_ids, is_active=True).order_by("email")
    }

    stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "tasks_completed": 0,
            "contacts_made": 0,
            "promises_taken": 0,
            "promises_kept": 0,
            "promises_broken": 0,
            "collected_amount": ZERO,
        }
    )

    completed = (
        CollectionTask.objects.for_organization(organization)
        .filter(
            status=CollectionTaskStatus.COMPLETED,
            completed_at__gte=start_dt,
            completed_at__lte=end_dt,
            assigned_to_id__isnull=False,
        )
        .values("assigned_to_id")
        .annotate(c=Count("id"))
    )
    for row in completed:
        stats[row["assigned_to_id"]]["tasks_completed"] = row["c"]

    contacts = (
        CollectionActivity.objects.for_organization(organization)
        .filter(
            activity_type__in=CONTACT_TYPES,
            created_at__gte=start_dt,
            created_at__lte=end_dt,
            created_by_id__isnull=False,
        )
        .values("created_by_id")
        .annotate(c=Count("id"))
    )
    for row in contacts:
        stats[row["created_by_id"]]["contacts_made"] = row["c"]

    promises_taken = (
        PaymentPromise.objects.for_organization(organization)
        .filter(created_at__gte=start_dt, created_at__lte=end_dt, created_by_id__isnull=False)
        .values("created_by_id")
        .annotate(c=Count("id"))
    )
    for row in promises_taken:
        stats[row["created_by_id"]]["promises_taken"] = row["c"]

    kept = (
        PaymentPromise.objects.for_organization(organization)
        .filter(
            status=PaymentPromiseStatus.FULFILLED,
            updated_at__gte=start_dt,
            updated_at__lte=end_dt,
            created_by_id__isnull=False,
        )
        .values("created_by_id")
        .annotate(c=Count("id"))
    )
    for row in kept:
        stats[row["created_by_id"]]["promises_kept"] = row["c"]

    broken = (
        PaymentPromise.objects.for_organization(organization)
        .filter(
            status=PaymentPromiseStatus.BROKEN,
            updated_at__gte=start_dt,
            updated_at__lte=end_dt,
            created_by_id__isnull=False,
        )
        .values("created_by_id")
        .annotate(c=Count("id"))
    )
    for row in broken:
        stats[row["created_by_id"]]["promises_broken"] = row["c"]

    collected = (
        Payment.objects.for_organization(organization)
        .filter(
            cancelled_at__isnull=True,
            payment_date__gte=start_d,
            payment_date__lte=end_d,
            recorded_by_id__isnull=False,
        )
        .values("recorded_by_id")
        .annotate(total=Sum("amount"))
    )
    for row in collected:
        stats[row["recorded_by_id"]]["collected_amount"] = row["total"] or ZERO

    # Include users with any activity even if not in memberships
    for uid in list(stats.keys()):
        if uid not in users:
            try:
                users[uid] = User.objects.get(pk=uid)
            except User.DoesNotExist:
                continue

    rows: list[dict[str, Any]] = []
    for uid, user in sorted(users.items(), key=lambda x: x[1].email):
        s = stats[uid]
        if (
            s["tasks_completed"]
            or s["contacts_made"]
            or s["promises_taken"]
            or s["promises_kept"]
            or s["promises_broken"]
            or s["collected_amount"]
        ):
            name = f"{user.first_name} {user.last_name}".strip() or user.email
            rows.append(
                {
                    "user_id": uid,
                    "user_email": user.email,
                    "user_name": name,
                    "tasks_completed": s["tasks_completed"],
                    "contacts_made": s["contacts_made"],
                    "promises_taken": s["promises_taken"],
                    "promises_kept": s["promises_kept"],
                    "promises_broken": s["promises_broken"],
                    "collected_amount": _money(s["collected_amount"]),
                    "date_from": start_d.isoformat(),
                    "date_to": end_d.isoformat(),
                }
            )
    return rows
