"""NP-111 rule-based collection probability (no ML).

Baz olasılık (gecikme gününe göre):
  Vadesi gelmemiş          %90
  1–15 gün gecikmiş        %80
  16–30 gün gecikmiş       %65
  31–60 gün gecikmiş       %45
  61–90 gün gecikmiş       %25
  90+ gün gecikmiş         %10

Düzeltmeler:
  Bozulan ödeme sözü       −%20
  Yeni (aktif) ödeme sözü  +%15

beklenen_tutar = açık_tutar × tahsilat_olasılığı
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.invoices.models import Invoice
from apps.invoices.overdue import invoice_overdue_days
from apps.payments.models import ZERO

QUANTIZE = Decimal("0.01")

# (max_overdue_inclusive_or_None_for_open_ended, probability)
# overdue == 0 → not overdue
BASE_PROBABILITY_BY_OVERDUE: list[tuple[int | None, Decimal]] = [
    (0, Decimal("0.90")),
    (15, Decimal("0.80")),
    (30, Decimal("0.65")),
    (60, Decimal("0.45")),
    (90, Decimal("0.25")),
    (None, Decimal("0.10")),
]

BROKEN_PROMISE_DELTA = Decimal("-0.20")
NEW_PROMISE_DELTA = Decimal("0.15")

ACTIVE_PROMISE_STATUSES = {
    PaymentPromiseStatus.PENDING,
    PaymentPromiseStatus.PARTIALLY_FULFILLED,
}


def base_probability_for_overdue_days(overdue_days: int) -> Decimal:
    days = max(0, int(overdue_days))
    for upper, prob in BASE_PROBABILITY_BY_OVERDUE:
        if upper is None or days <= upper:
            return prob
    return Decimal("0.10")


def clamp_probability(value: Decimal) -> Decimal:
    if value < ZERO:
        return ZERO
    if value > Decimal("1"):
        return Decimal("1")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def invoice_has_broken_promise(invoice: Invoice) -> bool:
    """Broken promise on this invoice, else any broken promise on the customer."""
    qs = PaymentPromise.objects.filter(
        customer_id=invoice.customer_id,
        status=PaymentPromiseStatus.BROKEN,
    )
    if qs.filter(invoice_id=invoice.id).exists():
        return True
    return qs.exists()


def invoice_has_new_promise(invoice: Invoice) -> bool:
    """Active (new) promise linked to invoice, else any active customer promise."""
    qs = PaymentPromise.objects.filter(
        customer_id=invoice.customer_id,
        status__in=ACTIVE_PROMISE_STATUSES,
    )
    if qs.filter(invoice_id=invoice.id).exists():
        return True
    return qs.exists()


def calculate_collection_probability(
    invoice: Invoice,
    *,
    as_of: date | None = None,
    open_amount: Decimal | None = None,
    has_broken_promise: bool | None = None,
    has_new_promise: bool | None = None,
) -> dict[str, Any]:
    """NP-111: probability + expected amount for one invoice.

    Returns::

        {
          "invoice_id": 1,
          "open_amount": Decimal("1000.00"),
          "overdue_days": 20,
          "base_probability": Decimal("0.65"),
          "adjustments": [{"code": "...", "label": "...", "delta": Decimal("-0.20")}],
          "probability": Decimal("0.45"),
          "expected_amount": Decimal("450.00"),
        }
    """
    today = as_of or timezone.localdate()
    overdue = invoice_overdue_days(invoice, as_of=today)
    base = base_probability_for_overdue_days(overdue)
    remaining = open_amount if open_amount is not None else invoice.remaining_amount()
    remaining = Decimal(str(remaining)).quantize(QUANTIZE)

    broken = (
        has_broken_promise
        if has_broken_promise is not None
        else invoice_has_broken_promise(invoice)
    )
    new_promise = (
        has_new_promise
        if has_new_promise is not None
        else invoice_has_new_promise(invoice)
    )

    adjustments: list[dict[str, Any]] = []
    probability = base
    if broken:
        probability += BROKEN_PROMISE_DELTA
        adjustments.append(
            {
                "code": "BROKEN_PROMISE",
                "label": "Bozulan ödeme sözü",
                "delta": BROKEN_PROMISE_DELTA,
            }
        )
    if new_promise:
        probability += NEW_PROMISE_DELTA
        adjustments.append(
            {
                "code": "NEW_PROMISE",
                "label": "Yeni ödeme sözü",
                "delta": NEW_PROMISE_DELTA,
            }
        )

    probability = clamp_probability(probability)
    expected = (remaining * probability).quantize(QUANTIZE, rounding=ROUND_HALF_UP)

    return {
        "invoice_id": invoice.id,
        "customer_id": invoice.customer_id,
        "open_amount": remaining,
        "overdue_days": overdue,
        "base_probability": base,
        "adjustments": adjustments,
        "probability": probability,
        "expected_amount": expected,
    }


# Horizon multipliers for cumulative collection probability (NP-225)
_HORIZON_FACTORS = {
    7: Decimal("0.45"),
    30: Decimal("0.85"),
    60: Decimal("1.05"),
}


def _expected_days_until_collection(
    overdue_days: int,
    probability_30d: Decimal,
    *,
    has_new_promise: bool,
) -> int:
    """Heuristic expected collection delay from as_of (days)."""
    if has_new_promise:
        base_days = 5
    elif overdue_days <= 0:
        base_days = 7
    elif overdue_days <= 15:
        base_days = 12
    elif overdue_days <= 30:
        base_days = 20
    elif overdue_days <= 60:
        base_days = 35
    elif overdue_days <= 90:
        base_days = 50
    else:
        base_days = 70

    # Higher 30d probability → sooner
    if probability_30d >= Decimal("0.70"):
        base_days = max(3, int(base_days * 0.7))
    elif probability_30d <= Decimal("0.25"):
        base_days = int(base_days * 1.25)
    return max(1, min(90, base_days))


def calculate_collection_horizons(
    invoice: Invoice,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    NP-225: per-invoice collection probabilities at 7 / 30 / 60 days
    plus expected collection date.
    """
    from datetime import timedelta

    today = as_of or timezone.localdate()
    base_result = calculate_collection_probability(invoice, as_of=today)
    remaining = base_result["open_amount"]

    # Fully paid / cancelled → certain / N/A
    if remaining <= ZERO:
        return {
            "invoice_id": invoice.id,
            "customer_id": invoice.customer_id,
            "open_amount": remaining,
            "overdue_days": base_result["overdue_days"],
            "probability_7d": Decimal("1.00"),
            "probability_30d": Decimal("1.00"),
            "probability_60d": Decimal("1.00"),
            "expected_collection_date": None,
            "expected_amount_7d": remaining,
            "expected_amount_30d": remaining,
            "expected_amount_60d": remaining,
            "adjustments": base_result["adjustments"],
            "base_probability": base_result["base_probability"],
        }

    p = Decimal(str(base_result["probability"]))
    p7 = clamp_probability(p * _HORIZON_FACTORS[7])
    p30 = clamp_probability(p * _HORIZON_FACTORS[30])
    p60 = clamp_probability(p * _HORIZON_FACTORS[60])
    # Ensure monotonic cumulative horizons
    if p30 < p7:
        p30 = p7
    if p60 < p30:
        p60 = p30

    has_new = any(a.get("code") == "NEW_PROMISE" for a in base_result["adjustments"])
    days = _expected_days_until_collection(
        int(base_result["overdue_days"]),
        p30,
        has_new_promise=has_new,
    )
    expected_date = today + timedelta(days=days)

    return {
        "invoice_id": invoice.id,
        "customer_id": invoice.customer_id,
        "open_amount": remaining,
        "overdue_days": base_result["overdue_days"],
        "probability_7d": p7,
        "probability_30d": p30,
        "probability_60d": p60,
        "expected_collection_date": expected_date.isoformat(),
        "expected_amount_7d": (remaining * p7).quantize(QUANTIZE, rounding=ROUND_HALF_UP),
        "expected_amount_30d": (remaining * p30).quantize(
            QUANTIZE, rounding=ROUND_HALF_UP
        ),
        "expected_amount_60d": (remaining * p60).quantize(
            QUANTIZE, rounding=ROUND_HALF_UP
        ),
        "adjustments": base_result["adjustments"],
        "base_probability": base_result["base_probability"],
        "probability": p30,  # default horizon for cash-flow compatibility
        "expected_amount": (remaining * p30).quantize(QUANTIZE, rounding=ROUND_HALF_UP),
    }
