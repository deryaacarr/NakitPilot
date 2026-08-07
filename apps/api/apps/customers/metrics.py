"""Customer balance / delay metrics (derived from invoices + payments + disputes)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.collections.models import DISPUTE_ACTIVE_STATUSES, Dispute
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_actual_delay_days, invoice_overdue_days
from apps.payments.models import Payment

ZERO = Decimal("0.00")

OPEN_STATUSES = {
    InvoiceStatus.OPEN,
    InvoiceStatus.OVERDUE,
    InvoiceStatus.PARTIALLY_PAID,
}


def disputed_invoice_ids_for_customer(customer: Any) -> set[int]:
    """Invoice IDs with an active dispute (NP-252)."""
    return set(
        Dispute.objects.filter(
            organization_id=customer.organization_id,
            customer_id=customer.id,
            status__in=DISPUTE_ACTIVE_STATUSES,
            invoice_id__isnull=False,
        ).values_list("invoice_id", flat=True)
    )


def invoice_has_active_dispute(*, organization_id: int, invoice_id: int | None) -> bool:
    if not invoice_id:
        return False
    return Dispute.objects.filter(
        organization_id=organization_id,
        invoice_id=invoice_id,
        status__in=DISPUTE_ACTIVE_STATUSES,
    ).exists()


def customer_financial_metrics(customer: Any) -> dict[str, Any]:
    """NP-252 — split open balance into normal / overdue / disputed."""
    today = timezone.localdate()
    invoices = Invoice.objects.filter(customer=customer).exclude(
        status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]
    )
    disputed_ids = disputed_invoice_ids_for_customer(customer)

    # Active disputes without invoice still count via dispute.amount
    orphan_disputed = (
        Dispute.objects.filter(
            organization_id=customer.organization_id,
            customer_id=customer.id,
            status__in=DISPUTE_ACTIVE_STATUSES,
            invoice_id__isnull=True,
            amount__isnull=False,
        ).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    open_balance = ZERO
    overdue_balance = ZERO
    disputed_balance = orphan_disputed
    delays: list[int] = []
    oldest_overdue: int | None = None

    for inv in invoices:
        remaining = inv.remaining_amount()
        if inv.status not in OPEN_STATUSES or remaining <= ZERO:
            actual = invoice_actual_delay_days(inv)
            if actual is not None:
                delays.append(actual)
            continue

        if inv.id in disputed_ids:
            disputed_balance += remaining
        else:
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
        "disputed_balance": disputed_balance,
        "unallocated_payment_balance": unallocated,
        "avg_delay_days": avg_delay,
        "oldest_overdue_days": oldest_overdue,
    }
