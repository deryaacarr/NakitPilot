"""Celery tasks for outbound email (NP-240)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="messaging.send_outbound_email")
def send_outbound_email_task(email_id: int) -> dict:
    from apps.messaging.email_service import send_outbound_email_now

    email = send_outbound_email_now(email_id)
    return {"id": email.id, "status": email.status}
