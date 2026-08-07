"""Customer feature extraction for hybrid risk models (NP-220)."""

from __future__ import annotations

import statistics
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from apps.collections.models import (
    CallOutcome,
    CollectionActivity,
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.metrics import OPEN_STATUSES, customer_financial_metrics
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_actual_delay_days, invoice_overdue_days
from apps.payments.models import Payment

ZERO = Decimal("0.00")

FEATURE_NAMES = (
    "average_payment_delay",
    "median_payment_delay",
    "on_time_payment_ratio",
    "broken_promise_count",
    "fulfilled_promise_ratio",
    "open_invoice_count",
    "overdue_invoice_count",
    "overdue_balance",
    "maximum_overdue_days",
    "last_payment_days_ago",
    "contact_success_ratio",
    "average_days_between_contacts",
    "credit_utilization_ratio",
    "invoice_amount_variance",
    "payment_frequency",
)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _variance(values: list[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    return float(statistics.pvariance(values))


def extract_customer_features(customer, *, as_of=None) -> dict[str, Any]:
    """
    Compute NP-220 feature vector for a customer.

    Returns dict with all FEATURE_NAMES plus metadata.
    """
    as_of = as_of or timezone.localdate()
    metrics = customer_financial_metrics(customer)

    invoices = list(
        Invoice.objects.filter(customer=customer).exclude(
            status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]
        )
    )

    delays: list[float] = []
    on_time = 0
    paid_count = 0
    open_count = 0
    overdue_count = 0
    amounts: list[float] = []

    for inv in invoices:
        amounts.append(float(inv.total_amount or 0))
        remaining = inv.remaining_amount()
        if inv.status in OPEN_STATUSES and remaining > ZERO:
            open_count += 1
            if invoice_overdue_days(inv, as_of=as_of) > 0:
                overdue_count += 1
        actual = invoice_actual_delay_days(inv)
        if actual is not None:
            delays.append(float(actual))
            paid_count += 1
            if actual <= 0:
                on_time += 1

    promises = PaymentPromise.objects.filter(customer=customer)
    promise_counts = promises.aggregate(
        total=Count("id"),
        broken=Count("id", filter=Q(status=PaymentPromiseStatus.BROKEN)),
        fulfilled=Count(
            "id",
            filter=Q(
                status__in=[
                    PaymentPromiseStatus.FULFILLED,
                    PaymentPromiseStatus.PARTIALLY_FULFILLED,
                ]
            ),
        ),
    )
    total_promises = promise_counts["total"] or 0
    broken_count = promise_counts["broken"] or 0
    fulfilled_count = promise_counts["fulfilled"] or 0

    last_payment = (
        Payment.objects.filter(customer=customer, cancelled_at__isnull=True)
        .order_by("-payment_date", "-id")
        .values_list("payment_date", flat=True)
        .first()
    )
    last_payment_days_ago = (as_of - last_payment).days if last_payment else None

    # Contact success from completed tasks with call outcomes
    task_outcomes = CollectionTask.objects.filter(
        customer=customer,
        status=CollectionTaskStatus.COMPLETED,
        outcome__in=[CallOutcome.REACHED, CallOutcome.NOT_REACHED],
    ).values_list("outcome", flat=True)
    reached = sum(1 for o in task_outcomes if o == CallOutcome.REACHED)
    attempts = len(task_outcomes)
    contact_success_ratio = (reached / attempts) if attempts else None

    # Average days between contacts from activities
    activity_dates = list(
        CollectionActivity.objects.filter(customer=customer)
        .order_by("occurred_at")
        .values_list("occurred_at", flat=True)[:200]
    )
    gaps: list[float] = []
    for i in range(1, len(activity_dates)):
        gaps.append((activity_dates[i] - activity_dates[i - 1]).total_seconds() / 86400.0)
    avg_days_between = _mean(gaps)

    credit_limit = float(customer.credit_limit or 0)
    open_balance = float(metrics["open_balance"] or 0)
    credit_util = (open_balance / credit_limit) if credit_limit > 0 else None

    # Payment frequency: payments per 30 days over last 90 days
    window_start = as_of - timedelta(days=90)
    pay_count_90 = Payment.objects.filter(
        customer=customer,
        cancelled_at__isnull=True,
        payment_date__gte=window_start,
        payment_date__lte=as_of,
    ).count()
    payment_frequency = pay_count_90 / 3.0  # per 30-day period

    overdue_balance = float(metrics["overdue_balance"] or 0)
    max_overdue = metrics["oldest_overdue_days"]

    features = {
        "average_payment_delay": _mean(delays) if delays else metrics.get("avg_delay_days"),
        "median_payment_delay": _median(delays),
        "on_time_payment_ratio": (on_time / paid_count) if paid_count else None,
        "broken_promise_count": broken_count,
        "fulfilled_promise_ratio": (fulfilled_count / total_promises) if total_promises else None,
        "open_invoice_count": open_count,
        "overdue_invoice_count": overdue_count,
        "overdue_balance": overdue_balance,
        "maximum_overdue_days": max_overdue,
        "last_payment_days_ago": last_payment_days_ago,
        "contact_success_ratio": contact_success_ratio,
        "average_days_between_contacts": avg_days_between,
        "credit_utilization_ratio": credit_util,
        "invoice_amount_variance": _variance(amounts),
        "payment_frequency": payment_frequency,
    }

    return {
        "customer_id": customer.id,
        "as_of": as_of.isoformat(),
        "features": features,
        "feature_names": list(FEATURE_NAMES),
    }


def extract_organization_features(organization, *, limit: int = 500, as_of=None) -> list[dict[str, Any]]:
    from apps.customers.models import Customer

    as_of = as_of or timezone.localdate()
    customers = Customer.objects.filter(organization=organization, is_active=True).order_by("id")[
        :limit
    ]
    return [extract_customer_features(c, as_of=as_of) for c in customers]
