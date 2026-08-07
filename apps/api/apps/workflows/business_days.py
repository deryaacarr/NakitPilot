"""Business-day scheduling helpers (NP-214)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from django.utils import timezone


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return value


def is_working_day(
    day: date,
    *,
    working_days: Iterable[int] | None = None,
    holidays: Iterable[date] | None = None,
) -> bool:
    """ISO weekday: Monday=1 … Sunday=7."""
    days = list(working_days) if working_days is not None else [1, 2, 3, 4, 5]
    holiday_set = set(holidays or [])
    return day.isoweekday() in days and day not in holiday_set


def add_business_days(
    start: date | datetime,
    amount: int,
    *,
    working_days: Iterable[int] | None = None,
    holidays: Iterable[date] | None = None,
) -> date:
    """
    Advance `amount` working days from start (exclusive of start if amount>0).
    Negative amount walks backward.
    """
    if amount == 0:
        return _as_date(start)

    current = _as_date(start)
    step = 1 if amount > 0 else -1
    remaining = abs(int(amount))
    while remaining > 0:
        current = current + timedelta(days=step)
        if is_working_day(current, working_days=working_days, holidays=holidays):
            remaining -= 1
    return current


def compute_resume_at(
    *,
    amount: int,
    unit: str,
    organization,
    from_dt: datetime | None = None,
) -> datetime:
    """Compute timezone-aware resume datetime for a DELAY step."""
    now = from_dt or timezone.now()
    unit_norm = (unit or "business_days").lower()
    amount = int(amount)

    if unit_norm in {"hours", "hour"}:
        return now + timedelta(hours=amount)

    if unit_norm in {"days", "day", "calendar_days"}:
        return now + timedelta(days=amount)

    # business_days
    holidays = list(
        organization.holidays.values_list("date", flat=True)
    ) if hasattr(organization, "holidays") else []
    working = organization.get_working_days() if hasattr(organization, "get_working_days") else [1, 2, 3, 4, 5]
    target_date = add_business_days(
        now,
        amount,
        working_days=working,
        holidays=holidays,
    )
    # Keep clock time from `now` in org-local interpretation via Django timezone.
    local_now = timezone.localtime(now)
    resume_naive = datetime.combine(target_date, local_now.timetz().replace(tzinfo=None))
    if timezone.is_aware(now):
        return timezone.make_aware(resume_naive, timezone.get_current_timezone())
    return resume_naive
