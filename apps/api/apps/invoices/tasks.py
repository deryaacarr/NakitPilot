"""Celery tasks for invoice status recalculation (NP-051)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="invoices.recalculate_invoice_statuses")
def recalculate_invoice_statuses() -> dict[str, int]:
    """Daily beat: OPEN / PARTIALLY_PAID / PAID / OVERDUE yeniden hesaplanır."""
    from apps.invoices.services import recalculate_all_invoice_statuses

    result = recalculate_all_invoice_statuses()
    logger.info(
        "recalculate_invoice_statuses finished checked=%s updated=%s",
        result["checked"],
        result["updated"],
    )
    return result


@shared_task(name="invoices.recalculate_invoices_after_payment")
def recalculate_invoices_after_payment_task(invoice_ids: list[int]) -> dict[str, int]:
    """
    Ödeme sonrası async yeniden hesaplama.

    Örnek: recalculate_invoices_after_payment_task.delay([1, 2, 3])
    """
    from apps.invoices.services import recalculate_invoices_after_payment

    result = recalculate_invoices_after_payment(invoice_ids)
    logger.info(
        "recalculate_invoices_after_payment finished ids=%s checked=%s updated=%s",
        invoice_ids,
        result["checked"],
        result["updated"],
    )
    return result
