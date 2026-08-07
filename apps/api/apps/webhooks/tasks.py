"""Celery tasks for webhook delivery retries (NP-205)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="webhooks.process_delivery")
def process_webhook_delivery(delivery_id: int, force: bool = False) -> dict:
    from apps.webhooks.delivery import process_delivery

    delivery = process_delivery(delivery_id, force=force)
    return {
        "id": delivery.id,
        "public_id": str(delivery.public_id),
        "status": delivery.status,
        "attempt_count": delivery.attempt_count,
    }


@shared_task(name="webhooks.process_due_deliveries")
def process_due_webhook_deliveries(limit: int = 100) -> dict:
    from apps.webhooks.delivery import process_due_deliveries

    result = process_due_deliveries(limit=limit)
    logger.info("webhook due processed=%s", result)
    return result
