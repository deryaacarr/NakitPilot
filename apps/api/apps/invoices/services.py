"""Invoice status calculation (NP-051).

Kurallar (DRAFT / CANCELLED hariç):
- kalan = 0                         → PAID
- 0 < kalan < toplam                → PARTIALLY_PAID
- kalan > 0 ve vade geçti           → OVERDUE
- kalan > 0 ve vade geçmedi         → OPEN
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceStatus

ZERO = Decimal("0.00")


def compute_invoice_status(
    *,
    total_amount: Decimal,
    remaining_amount: Decimal,
    due_date: date,
    as_of: date | None = None,
) -> str:
    """Pure status derivation from remaining amount + due date."""
    today = as_of or timezone.localdate()
    remaining = remaining_amount if remaining_amount > ZERO else ZERO

    if remaining == ZERO:
        return InvoiceStatus.PAID

    if ZERO < remaining < total_amount:
        return InvoiceStatus.PARTIALLY_PAID

    # remaining > 0 and remaining >= total_amount (typically unpaid in full)
    if due_date < today:
        return InvoiceStatus.OVERDUE
    return InvoiceStatus.OPEN


def recalculate_invoice_status(
    invoice: Invoice,
    *,
    as_of: date | None = None,
    save: bool = True,
) -> str | None:
    """
    Recalculate a single invoice status.

    Returns the new status, or None if DRAFT/CANCELLED (skipped).
    """
    if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}:
        return None

    new_status = compute_invoice_status(
        total_amount=invoice.total_amount,
        remaining_amount=invoice.remaining_amount(),
        due_date=invoice.due_date,
        as_of=as_of,
    )

    if new_status != invoice.status:
        update_fields = ["status", "updated_at"]
        today = as_of or timezone.localdate()
        if new_status == InvoiceStatus.PAID and invoice.payment_completion_date is None:
            invoice.payment_completion_date = today
            update_fields.append("payment_completion_date")
        elif new_status != InvoiceStatus.PAID and invoice.payment_completion_date is not None:
            invoice.payment_completion_date = None
            update_fields.append("payment_completion_date")
        invoice.status = new_status
        if save:
            invoice.save(update_fields=update_fields)

    # NP-520: status ↔ remaining invariants after every recalculation path.
    from apps.payments.invariants import enforce_invoice_financial_invariants

    enforce_invoice_financial_invariants(invoice)
    return new_status


def recalculate_invoices_after_payment(
    invoice_ids: list[int] | tuple[int, ...],
    *,
    as_of: date | None = None,
) -> dict[str, int]:
    """
    Ödeme / allocation sonrası ilgili faturaları yeniden hesapla.

    Payments modülü allocation kaydından sonra bunu (veya Celery task'ı) çağırır.
    """
    if not invoice_ids:
        return {"checked": 0, "updated": 0}

    updated = 0
    with transaction.atomic():
        invoices = (
            Invoice.objects.select_for_update()
            .filter(id__in=invoice_ids)
            .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED])
        )
        for invoice in invoices:
            previous = invoice.status
            result = recalculate_invoice_status(invoice, as_of=as_of, save=True)
            if result is not None and result != previous:
                updated += 1

    return {"checked": len(invoice_ids), "updated": updated}


def recalculate_all_invoice_statuses(
    *, as_of: date | None = None, organization=None
) -> dict[str, int]:
    """Bulk recalculation for the daily Celery job."""
    today = as_of or timezone.localdate()
    qs = Invoice.objects.exclude(
        status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]
    )
    if organization is not None:
        qs = qs.filter(organization=organization)

    checked = 0
    updated = 0
    for invoice in qs.iterator(chunk_size=500):
        checked += 1
        previous = invoice.status
        result = recalculate_invoice_status(invoice, as_of=today, save=True)
        if result is not None and result != previous:
            updated += 1

    return {"checked": checked, "updated": updated}
