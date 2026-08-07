"""Customer balance / delay metrics (derived from invoices + payments)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_actual_delay_days, invoice_overdue_days
from apps.payments.models import Payment

ZERO = Decimal("0.00")

OPEN_STATUSES = {
    InvoiceStatus.OPEN,
    InvoiceStatus.OVERDUE,
    InvoiceStatus.PARTIALLY_PAID,
}


def customer_financial_metrics(customer: Any) -> dict[str, Any]:
    today = timezone.localdate()
    invoices = Invoice.objects.filter(customer=customer).exclude(
        status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]
    )

    open_balance = ZERO
    overdue_balance = ZERO
    delays: list[int] = []
    oldest_overdue: int | None = None

    for inv in invoices:
        remaining = inv.remaining_amount()
        if inv.status in OPEN_STATUSES and remaining > ZERO:
            open_balance += remaining
            overdue_days = invoice_overdue_days(inv, as_of=today)
            if overdue_days > 0:
                overdue_balance += remaining
                oldest_overdue = (
                    overdue_days if oldest_overdue is None else max(oldest_overdue, overdue_days)
                )
        actual = invoice_actual_delay_days(inv)
        if actual is not None:
            delays.append(actual)

    unallocated = (
        Payment.objects.filter(customer=customer, cancelled_at__isnull=True).aggregate(
            total=Sum("unallocated_amount")
        )["total"]
        or ZERO
    )

    avg_delay = None
    if delays:
        avg_delay = int(round(sum(delays) / len(delays)))

    return {
        "open_balance": open_balance,
        "overdue_balance": overdue_balance,
        "unallocated_payment_balance": unallocated,
        "avg_delay_days": avg_delay,
        "oldest_overdue_days": oldest_overdue,
    }
