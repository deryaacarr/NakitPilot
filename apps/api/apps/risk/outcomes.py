"""Outcome label computation for risk predictions (NP-221)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceStatus
from apps.payments.models import Payment
from apps.risk.enums import (
    MAX_OUTCOME_HORIZON_DAYS,
    OUTCOME_HORIZONS,
    OUTCOME_INVOICE_90PLUS,
    OUTCOME_KEYS,
    OUTCOME_PAID_WITHIN_30D,
    OUTCOME_PAID_WITHIN_60D,
)


def outcome_date_for_prediction(prediction_date: date) -> date:
    return prediction_date + timedelta(days=MAX_OUTCOME_HORIZON_DAYS)


def _paid_within(customer, prediction_date: date, *, days: int, as_of: date) -> bool | None:
    """True if any non-cancelled payment landed in [prediction_date, prediction_date+days]."""
    horizon_end = prediction_date + timedelta(days=days)
    if as_of < horizon_end:
        return None
    return Payment.objects.filter(
        customer=customer,
        cancelled_at__isnull=True,
        payment_date__gte=prediction_date,
        payment_date__lte=horizon_end,
    ).exists()


def _invoice_reached_90_plus(customer, prediction_date: date, *, as_of: date) -> bool | None:
    """
    True if any invoice was (or became) 90+ days past due without being fully paid
    before day 90, evaluated once the 90-day horizon has elapsed.
    """
    horizon_end = prediction_date + timedelta(days=OUTCOME_HORIZONS[OUTCOME_INVOICE_90PLUS])
    if as_of < horizon_end:
        return None

    invoices = Invoice.objects.filter(customer=customer).exclude(
        status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]
    )
    for inv in invoices.iterator(chunk_size=200):
        # Only invoices that could be observed around the prediction window
        if inv.due_date > horizon_end:
            continue
        day_90 = inv.due_date + timedelta(days=90)
        if day_90 < prediction_date:
            # Already 90+ before prediction — count if still unpaid at prediction
            paid = inv.payment_completion_date
            if paid is None or paid > prediction_date:
                return True
            continue
        if day_90 > horizon_end:
            continue
        paid = inv.payment_completion_date
        if paid is None or paid > day_90:
            return True
    return False


def compute_actual_outcome(
    customer,
    prediction_date: date,
    *,
    as_of: date | None = None,
) -> dict[str, bool | None]:
    """
    Compute NP-221 outcome labels relative to prediction_date.

    Labels that are not yet knowable (horizon not reached) are ``None``.
    """
    as_of = as_of or timezone.localdate()
    return {
        OUTCOME_PAID_WITHIN_30D: _paid_within(
            customer, prediction_date, days=30, as_of=as_of
        ),
        OUTCOME_PAID_WITHIN_60D: _paid_within(
            customer, prediction_date, days=60, as_of=as_of
        ),
        OUTCOME_INVOICE_90PLUS: _invoice_reached_90_plus(
            customer, prediction_date, as_of=as_of
        ),
    }


def outcomes_fully_resolved(outcome: dict[str, Any] | None) -> bool:
    if not outcome:
        return False
    return all(outcome.get(key) is not None for key in OUTCOME_KEYS)


def risk_label_from_outcome(
    outcome: dict[str, Any],
    *,
    target_label: str = OUTCOME_INVOICE_90PLUS,
) -> int | None:
    """
    Map actual_outcome → binary risk label (1 = adverse / riskier).

    - invoice_90plus_overdue: True → 1
    - paid_within_*: False (did not pay) → 1
    """
    value = outcome.get(target_label)
    if value is None:
        return None
    if target_label in (OUTCOME_PAID_WITHIN_30D, OUTCOME_PAID_WITHIN_60D):
        return 0 if value else 1
    return 1 if value else 0
