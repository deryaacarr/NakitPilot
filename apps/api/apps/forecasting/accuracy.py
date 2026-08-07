"""NP-275 — forecast accuracy (MAE, MAPE, bias, weekly)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.forecasting.models import ForecastSnapshot
from apps.forecasting.weekly import QUANTIZE, ZERO, calculate_organization_forecast, iso_week_start
from apps.organizations.models import Organization
from apps.payments.models import Payment


def _week_starts(date_from: date, date_to: date) -> list[date]:
    start = iso_week_start(date_from)
    end = iso_week_start(date_to)
    weeks: list[date] = []
    cur = start
    while cur <= end:
        weeks.append(cur)
        cur += timedelta(days=7)
    return weeks


def forecast_accuracy_report(
    organization_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    """
    Her hafta: tahmin edilen vs gerçekleşen tahsilat + MAE/MAPE/Bias.
    """
    org = Organization.objects.get(pk=organization_id)
    cur = (currency or org.default_currency or "TRY").upper()
    today = timezone.localdate()
    date_to = date_to or today
    date_from = date_from or (date_to - timedelta(days=7 * 12))
    weeks = _week_starts(date_from, date_to)

    expected_map: dict[date, Decimal] = {}
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

    missing = [w for w in weeks if w not in expected_map]
    if missing:
        forecast = calculate_organization_forecast(
            organization_id,
            as_of=date_from,
            persist=False,
            weeks=max(len(weeks), 1),
            currency=cur,
        )
        for w in forecast["weeks"]:
            ws = w["week_start"]
            if ws in missing:
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

    weekly: list[dict[str, Any]] = []
    abs_errors: list[Decimal] = []
    pct_errors: list[Decimal] = []
    signed_errors: list[Decimal] = []
    total_actual = ZERO
    total_expected = ZERO

    for ws in weeks:
        expected = Decimal(str(expected_map.get(ws, ZERO))).quantize(QUANTIZE)
        actual = Decimal(str(actual_map.get(ws, ZERO))).quantize(QUANTIZE)
        err = (actual - expected).quantize(QUANTIZE)
        abs_err = abs(err)
        if expected > ZERO:
            pct = (abs_err / expected * Decimal("100")).quantize(Decimal("0.01"))
        elif actual == ZERO:
            pct = Decimal("0.00")
        else:
            pct = Decimal("100.00")
        abs_errors.append(abs_err)
        pct_errors.append(pct)
        signed_errors.append(err)
        total_actual += actual
        total_expected += expected
        weekly.append(
            {
                "week_start": ws.isoformat(),
                "week_end": (ws + timedelta(days=6)).isoformat(),
                "forecast_collection": str(expected),
                "actual_collection": str(actual),
                "absolute_error": str(abs_err),
                "percentage_error": str(pct),
                "signed_error": str(err),
            }
        )

    n = len(weeks) or 1
    mae = (sum(abs_errors, ZERO) / n).quantize(QUANTIZE)
    mape = (sum(pct_errors, ZERO) / n).quantize(Decimal("0.01"))
    bias = (sum(signed_errors, ZERO) / n).quantize(QUANTIZE)
    # Weekly accuracy: share of weeks with |error|/expected <= 20% (or exact if expected 0)
    accurate = 0
    for row in weekly:
        exp = Decimal(row["forecast_collection"])
        pct = Decimal(row["percentage_error"])
        if exp == ZERO and Decimal(row["actual_collection"]) == ZERO:
            accurate += 1
        elif pct <= Decimal("20"):
            accurate += 1
    weekly_accuracy = (Decimal(accurate) / Decimal(n) * Decimal("100")).quantize(
        Decimal("0.01")
    )

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "currency": cur,
        "metrics": {
            "mae": str(mae),
            "mape": str(mape),
            "bias": str(bias),
            "weekly_accuracy_pct": str(weekly_accuracy),
        },
        "totals": {
            "forecast_collection": str(total_expected.quantize(QUANTIZE)),
            "actual_collection": str(total_actual.quantize(QUANTIZE)),
        },
        "weeks": weekly,
    }
