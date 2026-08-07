"""Overdue / payment delay helpers (NP-055).

Kurallar:
- overdue_days = max(today - due_date, 0)          # açık/gecikmiş faturalar
- actual_delay = payment_completion_date - due_date  # ödenmiş faturalar (risk için)
"""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceStatus


def overdue_days(due_date: date, *, as_of: date | None = None) -> int:
    """Güncel gecikme: max(today - due_date, 0)."""
    today = as_of or timezone.localdate()
    return max((today - due_date).days, 0)


def actual_delay_days(
    due_date: date,
    payment_completion_date: date | None,
) -> int | None:
    """
    Ödenmiş fatura gecikmesi: payment_completion_date - due_date.

    Erken ödeme negatif olabilir. completion yoksa None.
    """
    if payment_completion_date is None:
        return None
    return (payment_completion_date - due_date).days


def invoice_overdue_days(invoice: Invoice, *, as_of: date | None = None) -> int:
    """Açık bakiyesi olan fatura için güncel gecikme; ödenmiş/iptal/draft → 0."""
    if invoice.status in {InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT}:
        return 0
    if invoice.remaining_amount() <= 0:
        return 0
    return overdue_days(invoice.due_date, as_of=as_of)


def invoice_actual_delay_days(invoice: Invoice) -> int | None:
    """Ödenmiş fatura için gerçekleşen gecikme (risk skoruna girdi)."""
    if invoice.status != InvoiceStatus.PAID:
        return None
    return actual_delay_days(invoice.due_date, invoice.payment_completion_date)


def delay_days_for_risk(invoice: Invoice, *, as_of: date | None = None) -> int | None:
    """
    Risk puanı için gecikme günü.

    - PAID → actual_delay (None ise 0 varsayılmaz; completion yoksa None)
    - OPEN / OVERDUE / PARTIALLY_PAID → overdue_days
    - DRAFT / CANCELLED → None
    """
    if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}:
        return None
    if invoice.status == InvoiceStatus.PAID:
        return invoice_actual_delay_days(invoice)
    return invoice_overdue_days(invoice, as_of=as_of)
