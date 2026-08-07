"""Celery tasks for outbound email (NP-240) and WhatsApp (NP-242)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="messaging.send_outbound_email")
def send_outbound_email_task(email_id: int) -> dict:
    from apps.messaging.email_service import send_outbound_email_now

    email = send_outbound_email_now(email_id)
    return {"id": email.id, "status": email.status}


@shared_task(name="messaging.send_outbound_whatsapp")
def send_outbound_whatsapp_task(message_id: int) -> dict:
    from apps.messaging.whatsapp_service import send_whatsapp_now

    msg = send_whatsapp_now(message_id)
    return {"id": msg.id, "status": msg.status}
