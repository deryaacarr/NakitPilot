"""NP-110 rule-based expected collection date (no ML).

Kurallar:
- Geçmiş ortalama gecikme varsa: beklenen_tahsilat = due_date + avg_delay_days
- Veri yoksa: beklenen_tahsilat = due_date
- Bozulan ödeme sözü varsa tahmin güveni düşürülür
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Literal

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer
from apps.invoices.models import Invoice

Confidence = Literal["HIGH", "MEDIUM", "LOW"]


def customer_avg_delay_days(customer: Customer) -> int | None:
    """Average payment delay (days) from paid invoices; None if no history."""
    metrics = customer_financial_metrics(customer)
    avg = metrics.get("avg_delay_days")
    return int(avg) if avg is not None else None


def customer_has_broken_promise(customer: Customer) -> bool:
    return PaymentPromise.objects.filter(
        customer=customer,
        status=PaymentPromiseStatus.BROKEN,
    ).exists()


def prediction_confidence(
    *,
    has_history: bool,
    has_broken_promise: bool,
) -> Confidence:
    """Broken promise lowers confidence one band (or to LOW)."""
    if has_broken_promise:
        return "LOW" if not has_history else "MEDIUM"
    return "HIGH" if has_history else "MEDIUM"


def predict_expected_collection_date(
    invoice: Invoice,
    *,
    avg_delay_days: int | None = None,
    has_broken_promise: bool | None = None,
) -> dict[str, Any]:
    """Predict expected collection date for a single invoice.

    Returns::

        {
          "invoice_id": 1,
          "customer_id": 2,
          "due_date": date(...),
          "expected_collection_date": date(...),
          "avg_delay_days": 12 | None,
          "confidence": "HIGH" | "MEDIUM" | "LOW",
          "has_broken_promise": bool,
          "method": "AVG_DELAY" | "DUE_DATE_FALLBACK",
        }
    """
    customer = invoice.customer
    delay = (
        avg_delay_days
        if avg_delay_days is not None
        else customer_avg_delay_days(customer)
    )
    broken = (
        has_broken_promise
        if has_broken_promise is not None
        else customer_has_broken_promise(customer)
    )
    has_history = delay is not None

    if has_history:
        expected = invoice.due_date + timedelta(days=delay)
        method = "AVG_DELAY"
    else:
        expected = invoice.due_date
        method = "DUE_DATE_FALLBACK"

    return {
        "invoice_id": invoice.id,
        "customer_id": customer.id,
        "due_date": invoice.due_date,
        "expected_collection_date": expected,
        "avg_delay_days": delay,
        "confidence": prediction_confidence(
            has_history=has_history,
            has_broken_promise=broken,
        ),
        "has_broken_promise": broken,
        "method": method,
    }


def predict_open_invoices_for_customer(
    customer: Customer,
) -> list[dict[str, Any]]:
    """Predict collection dates for customer's open invoices (shared delay/broken)."""
    from apps.invoices.models import InvoiceStatus

    delay = customer_avg_delay_days(customer)
    broken = customer_has_broken_promise(customer)
    qs = (
        Invoice.objects.filter(customer=customer)
        .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED, InvoiceStatus.PAID])
        .order_by("due_date", "id")
    )
    return [
        predict_expected_collection_date(
            inv,
            avg_delay_days=delay,
            has_broken_promise=broken,
        )
        for inv in qs
    ]
