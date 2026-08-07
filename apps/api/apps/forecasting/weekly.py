"""NP-112/113/115: weekly organization cash-flow forecast.

Bu hafta + sonraki N-1 hafta (API ``weeks`` parametresi, varsayılan 13).

Her hafta:
  nominal       — açık tutar (vade haftası)
  expected      — ağırlıklı beklenen (açık × olasılık)
  optimistic    — iyimser
  pessimistic   — kötümser
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.forecasting.models import ForecastSnapshot
from apps.forecasting.prediction import (
    customer_avg_delay_days,
    customer_has_broken_promise,
    predict_expected_collection_date,
)
from apps.forecasting.probability import (
    calculate_collection_probability,
    clamp_probability,
)
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization
from apps.payments.models import ZERO

DEFAULT_FORECAST_WEEKS = 13
MAX_FORECAST_WEEKS = 26
# Celery / snapshot runs use this week + next 13
FORECAST_WEEK_COUNT = 14
OPTIMISTIC_PROB_DELTA = Decimal("0.15")
PESSIMISTIC_PROB_DELTA = Decimal("-0.25")
PESSIMISTIC_EXTRA_DAYS = 14
PROMISE_EXPECTED_FACTOR = Decimal("0.85")
PROMISE_PESSIMISTIC_FACTOR = Decimal("0.50")
QUANTIZE = Decimal("0.01")
TOP_INVOICES_LIMIT = 10

OPEN_STATUSES = {
    InvoiceStatus.OPEN,
    InvoiceStatus.OVERDUE,
    InvoiceStatus.PARTIALLY_PAID,
}

ACTIVE_PROMISE_STATUSES = {
    PaymentPromiseStatus.PENDING,
    PaymentPromiseStatus.PARTIALLY_FULFILLED,
}


def iso_week_start(d: date) -> date:
    """Monday of the ISO week containing ``d``."""
    return d - timedelta(days=d.weekday())


def _q(amount: Decimal) -> Decimal:
    return Decimal(str(amount)).quantize(QUANTIZE, rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> str:
    return str(_q(value))


def format_tr_money(amount: Decimal) -> str:
    """327500.00 → '327.500 TL' (kurus gizlenir if .00)."""
    q = _q(amount)
    sign = "-" if q < 0 else ""
    q = abs(q)
    whole_s, frac_s = f"{q:.2f}".split(".")
    groups: list[str] = []
    while whole_s:
        groups.append(whole_s[-3:])
        whole_s = whole_s[:-3]
    whole_fmt = ".".join(reversed(groups))
    if frac_s == "00":
        return f"{sign}{whole_fmt} TL"
    return f"{sign}{whole_fmt},{frac_s} TL"


def build_week_buckets(*, as_of: date, count: int) -> list[date]:
    start = iso_week_start(as_of)
    return [start + timedelta(weeks=i) for i in range(count)]


def _clamp_to_horizon(target: date, *, horizon_start: date, horizon_end: date) -> date:
    ws = iso_week_start(target)
    if ws < horizon_start:
        return horizon_start
    if ws > horizon_end:
        return horizon_end
    return ws


def _empty_weeks(week_starts: list[date], *, currency: str) -> list[dict[str, Any]]:
    return [
        {
            "week_index": i,
            "week_start": ws,
            "week_end": ws + timedelta(days=6),
            "currency": currency,
            "nominal_amount": ZERO,
            "expected_amount": ZERO,
            "optimistic_amount": ZERO,
            "pessimistic_amount": ZERO,
            "open_for_expected": ZERO,
            "invoice_count": 0,
            "promise_count": 0,
        }
        for i, ws in enumerate(week_starts)
    ]


def _add_to_week(
    weeks: dict[date, dict[str, Any]],
    week_start: date,
    *,
    nominal: Decimal = ZERO,
    expected: Decimal = ZERO,
    optimistic: Decimal = ZERO,
    pessimistic: Decimal = ZERO,
    open_for_expected: Decimal = ZERO,
    invoice: bool = False,
    promise: bool = False,
) -> None:
    bucket = weeks[week_start]
    bucket["nominal_amount"] = _q(bucket["nominal_amount"] + nominal)
    bucket["expected_amount"] = _q(bucket["expected_amount"] + expected)
    bucket["optimistic_amount"] = _q(bucket["optimistic_amount"] + optimistic)
    bucket["pessimistic_amount"] = _q(bucket["pessimistic_amount"] + pessimistic)
    bucket["open_for_expected"] = _q(bucket["open_for_expected"] + open_for_expected)
    if invoice:
        bucket["invoice_count"] += 1
    if promise:
        bucket["promise_count"] += 1


def calculate_organization_forecast(
    organization_id: int,
    *,
    as_of: date | None = None,
    persist: bool = True,
    currency: str | None = None,
    weeks: int | None = None,
) -> dict[str, Any]:
    """Compute weekly forecast buckets (+ invoice contributions for NP-114/115)."""
    organization = Organization.objects.get(pk=organization_id)
    today = as_of or timezone.localdate()
    cur = (currency or organization.default_currency or "TRY").upper()
    week_count = weeks if weeks is not None else FORECAST_WEEK_COUNT
    week_count = max(1, min(int(week_count), MAX_FORECAST_WEEKS))
    week_starts = build_week_buckets(as_of=today, count=week_count)
    horizon_start = week_starts[0]
    horizon_end = week_starts[-1]
    weeks_map = {w["week_start"]: w for w in _empty_weeks(week_starts, currency=cur)}
    contributions: list[dict[str, Any]] = []

    invoices = list(
        Invoice.objects.filter(
            organization_id=organization_id,
            status__in=OPEN_STATUSES,
            currency=cur,
        )
        .select_related("customer")
        .order_by("due_date", "id")
    )

    delay_cache: dict[int, int | None] = {}
    broken_cache: dict[int, bool] = {}

    for inv in invoices:
        remaining = inv.remaining_amount()
        if remaining <= ZERO:
            continue

        cid = inv.customer_id
        if cid not in delay_cache:
            delay_cache[cid] = customer_avg_delay_days(inv.customer)
            broken_cache[cid] = customer_has_broken_promise(inv.customer)

        pred = predict_expected_collection_date(
            inv,
            avg_delay_days=delay_cache[cid],
            has_broken_promise=broken_cache[cid],
        )
        prob = calculate_collection_probability(
            inv,
            as_of=today,
            open_amount=remaining,
        )

        open_amt = _q(remaining)
        expected_amt = _q(prob["expected_amount"])
        optimistic_amt = _q(
            open_amt * clamp_probability(prob["probability"] + OPTIMISTIC_PROB_DELTA)
        )
        pessimistic_amt = _q(
            open_amt * clamp_probability(prob["probability"] + PESSIMISTIC_PROB_DELTA)
        )

        expected_date: date = pred["expected_collection_date"]
        due_week = _clamp_to_horizon(
            inv.due_date, horizon_start=horizon_start, horizon_end=horizon_end
        )
        expected_week = _clamp_to_horizon(
            expected_date, horizon_start=horizon_start, horizon_end=horizon_end
        )
        optimistic_week = _clamp_to_horizon(
            min(inv.due_date, expected_date),
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
        pessimistic_week = _clamp_to_horizon(
            expected_date + timedelta(days=PESSIMISTIC_EXTRA_DAYS),
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )

        _add_to_week(weeks_map, due_week, nominal=open_amt, invoice=True)
        _add_to_week(
            weeks_map,
            expected_week,
            expected=expected_amt,
            open_for_expected=open_amt,
        )
        _add_to_week(weeks_map, optimistic_week, optimistic=optimistic_amt)
        _add_to_week(weeks_map, pessimistic_week, pessimistic=pessimistic_amt)

        customer = inv.customer
        contributions.append(
            {
                "invoice_id": inv.id,
                "number": inv.number,
                "customer_id": customer.id,
                "customer_name": customer.name,
                "customer_risk_score": int(customer.risk_score or 0),
                "customer_risk_status": customer.risk_status,
                "open_amount": open_amt,
                "expected_amount": expected_amt,
                "probability": prob["probability"],
                "due_date": inv.due_date,
                "expected_collection_date": expected_date,
                "nominal_week": due_week,
                "expected_week": expected_week,
                "optimistic_week": optimistic_week,
                "pessimistic_week": pessimistic_week,
            }
        )

    promises = PaymentPromise.objects.filter(
        organization_id=organization_id,
        status__in=ACTIVE_PROMISE_STATUSES,
        currency=cur,
        invoice__isnull=True,
    ).order_by("promised_date", "id")
    for promise in promises:
        amt = _q(promise.amount)
        if amt <= ZERO:
            continue
        ws = _clamp_to_horizon(
            promise.promised_date, horizon_start=horizon_start, horizon_end=horizon_end
        )
        expected_p = _q(amt * PROMISE_EXPECTED_FACTOR)
        _add_to_week(
            weeks_map,
            ws,
            nominal=amt,
            expected=expected_p,
            optimistic=amt,
            pessimistic=_q(amt * PROMISE_PESSIMISTIC_FACTOR),
            open_for_expected=amt,
            promise=True,
        )

    weeks = [weeks_map[ws] for ws in week_starts]
    run_id = str(uuid.uuid4())
    result = {
        "organization_id": organization_id,
        "as_of": today,
        "currency": cur,
        "run_id": run_id,
        "week_count": len(weeks),
        "weeks": weeks,
        "contributions": contributions,
    }

    if persist:
        _persist_forecast(organization, result)

    return result


def cash_flow_api_payload(
    organization_id: int,
    *,
    weeks: int = DEFAULT_FORECAST_WEEKS,
    week_start: date | None = None,
    as_of: date | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """NP-113/114/115 response shape for GET /api/forecast/cash-flow."""
    result = calculate_organization_forecast(
        organization_id,
        as_of=as_of,
        persist=persist,
        weeks=weeks,
    )
    payload: dict[str, Any] = {
        "weeks": [
            {
                "week_start": w["week_start"].isoformat(),
                "nominal": _money(w["nominal_amount"]),
                "expected": _money(w["expected_amount"]),
                "optimistic": _money(w["optimistic_amount"]),
                "pessimistic": _money(w["pessimistic_amount"]),
            }
            for w in result["weeks"]
        ],
        "currency": result["currency"],
        "as_of": result["as_of"].isoformat(),
    }
    if week_start is not None:
        payload["detail"] = build_week_detail(result, week_start)
    return payload


def build_week_detail(result: dict[str, Any], week_start: date) -> dict[str, Any] | None:
    """NP-114/115: explanation + top invoices for a week (by expected bucket)."""
    weeks_by_start = {w["week_start"]: w for w in result["weeks"]}
    bucket = weeks_by_start.get(week_start)
    if bucket is None:
        return None

    contribs = [
        c for c in result.get("contributions", []) if c["expected_week"] == week_start
    ]
    contribs_sorted = sorted(contribs, key=lambda c: c["open_amount"], reverse=True)
    top = contribs_sorted[:TOP_INVOICES_LIMIT]

    open_total = _q(bucket.get("open_for_expected") or ZERO)
    expected = _q(bucket["expected_amount"])
    risk_reduction = _q(max(open_total - expected, ZERO))

    highest = None
    if contribs:
        best = max(contribs, key=lambda c: (c["customer_risk_score"], c["open_amount"]))
        highest = {
            "id": best["customer_id"],
            "name": best["customer_name"],
            "risk_score": best["customer_risk_score"],
            "risk_status": best["customer_risk_status"],
        }

    summary = f"Bu hafta {format_tr_money(expected)} bekleniyor."

    return {
        "week_start": week_start.isoformat(),
        "week_end": bucket["week_end"].isoformat(),
        "summary": summary,
        "expected": _money(expected),
        "open_total": _money(open_total),
        "risk_reduction": _money(risk_reduction),
        "highest_risk_customer": highest,
        "top_invoices": [
            {
                "id": c["invoice_id"],
                "number": c["number"],
                "customer_id": c["customer_id"],
                "customer_name": c["customer_name"],
                "open_amount": _money(c["open_amount"]),
                "expected_amount": _money(c["expected_amount"]),
                "due_date": c["due_date"].isoformat(),
                "probability": str(c["probability"]),
            }
            for c in top
        ],
    }


@transaction.atomic
def _persist_forecast(organization: Organization, result: dict[str, Any]) -> list[ForecastSnapshot]:
    run_id = result["run_id"]
    rows: list[ForecastSnapshot] = []
    for week in result["weeks"]:
        details = {
            "invoice_count": week["invoice_count"],
            "promise_count": week["promise_count"],
            "as_of": result["as_of"].isoformat(),
            "week_end": week["week_end"].isoformat(),
            "open_for_expected": _money(week.get("open_for_expected") or ZERO),
            "amounts": {
                "nominal": _money(week["nominal_amount"]),
                "expected": _money(week["expected_amount"]),
                "optimistic": _money(week["optimistic_amount"]),
                "pessimistic": _money(week["pessimistic_amount"]),
            },
        }
        rows.append(
            ForecastSnapshot(
                organization=organization,
                week_start=week["week_start"],
                week_index=week["week_index"],
                currency=week["currency"],
                nominal_amount=week["nominal_amount"],
                expected_amount=week["expected_amount"],
                optimistic_amount=week["optimistic_amount"],
                pessimistic_amount=week["pessimistic_amount"],
                calculation_details=details,
                run_id=run_id,
            )
        )
    return ForecastSnapshot.objects.bulk_create(rows)
