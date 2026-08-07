"""Enqueue and process webhook deliveries with retries (NP-205)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.webhooks.models import (
    WebhookAttempt,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookSubscription,
)
from apps.webhooks.retry import DEFAULT_MAX_ATTEMPTS, next_retry_at
from apps.webhooks.secrets import decrypt_webhook_secret
from apps.webhooks.signing import prepare_outbound_request

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 15
RESPONSE_BODY_MAX = 8192
SUCCESS_STATUSES = range(200, 300)


class WebhookDeliveryError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def enqueue_event(
    *,
    organization,
    event_type: str,
    event_id: str,
    payload: dict[str, Any],
    process_async: bool = True,
) -> list[WebhookDelivery]:
    """
    Create one delivery per active subscription for `event_type`.

    Unique on (endpoint, event_type, event_id) — duplicates are skipped.
    """
    now = timezone.now()
    subscriptions = (
        WebhookSubscription.objects.select_related("endpoint")
        .filter(
            organization=organization,
            event_type=event_type,
            is_active=True,
            endpoint__is_active=True,
        )
    )
    created: list[WebhookDelivery] = []
    for sub in subscriptions:
        try:
            with transaction.atomic():
                delivery = WebhookDelivery.objects.create(
                    organization=organization,
                    endpoint=sub.endpoint,
                    subscription=sub,
                    event_type=event_type,
                    event_id=str(event_id),
                    payload=payload or {},
                    status=WebhookDeliveryStatus.PENDING,
                    max_attempts=DEFAULT_MAX_ATTEMPTS,
                    next_attempt_at=now,
                )
        except IntegrityError:
            continue
        created.append(delivery)
        if process_async:
            from apps.webhooks.tasks import process_webhook_delivery

            process_webhook_delivery.delay(delivery.id)
    return created


@transaction.atomic
def process_delivery(delivery_id: int, *, force: bool = False) -> WebhookDelivery:
    delivery = (
        WebhookDelivery.objects.select_for_update()
        .select_related("endpoint")
        .get(pk=delivery_id)
    )
    if delivery.status == WebhookDeliveryStatus.SUCCEEDED:
        return delivery
    if delivery.status == WebhookDeliveryStatus.EXHAUSTED and not force:
        return delivery

    now = timezone.now()
    if (
        not force
        and delivery.next_attempt_at is not None
        and delivery.next_attempt_at > now
    ):
        return delivery

    endpoint = delivery.endpoint
    if not endpoint.is_active:
        delivery.status = WebhookDeliveryStatus.FAILED
        delivery.last_error = "Endpoint pasif."
        delivery.save(update_fields=["status", "last_error", "updated_at"])
        return delivery

    delivery.status = WebhookDeliveryStatus.IN_PROGRESS
    delivery.save(update_fields=["status", "updated_at"])

    attempt_number = delivery.attempt_count + 1
    body = json.dumps(delivery.payload or {}, cls=DjangoJSONEncoder, separators=(",", ":"))
    secret = decrypt_webhook_secret(endpoint.secret_encrypted)
    prepared = prepare_outbound_request(
        secret=secret,
        event_type=delivery.event_type,
        delivery_id=str(delivery.public_id),
        body=body,
    )

    started = time.perf_counter()
    response_status: int | None = None
    response_body = ""
    error_message = ""
    success = False
    try:
        req = urllib.request.Request(
            endpoint.url,
            data=prepared["body"],
            headers=prepared["headers"],
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310
            response_status = getattr(resp, "status", None) or resp.getcode()
            raw = resp.read(RESPONSE_BODY_MAX + 1)
            response_body = raw[:RESPONSE_BODY_MAX].decode("utf-8", errors="replace")
            success = response_status in SUCCESS_STATUSES
            if not success:
                error_message = f"HTTP {response_status}"
    except urllib.error.HTTPError as exc:
        response_status = exc.code
        try:
            response_body = (exc.read(RESPONSE_BODY_MAX) or b"").decode(
                "utf-8", errors="replace"
            )
        except Exception:  # noqa: BLE001
            response_body = ""
        error_message = f"HTTP {exc.code}"
        success = False
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)[:500]
        success = False

    duration_ms = int((time.perf_counter() - started) * 1000)
    WebhookAttempt.objects.create(
        organization=delivery.organization,
        delivery=delivery,
        attempt_number=attempt_number,
        request_url=endpoint.url,
        response_status=response_status,
        response_body=response_body,
        error_message=error_message,
        duration_ms=duration_ms,
        success=success,
    )

    delivery.attempt_count = attempt_number
    if success:
        delivery.status = WebhookDeliveryStatus.SUCCEEDED
        delivery.last_error = ""
        delivery.next_attempt_at = None
        delivery.completed_at = timezone.now()
        endpoint.consecutive_failures = 0
        endpoint.last_success_at = timezone.now()
        endpoint.save(
            update_fields=["consecutive_failures", "last_success_at", "updated_at"]
        )
    else:
        retry_at = next_retry_at(attempt_number)
        endpoint.consecutive_failures = (endpoint.consecutive_failures or 0) + 1
        endpoint.last_failure_at = timezone.now()
        endpoint.save(
            update_fields=["consecutive_failures", "last_failure_at", "updated_at"]
        )
        delivery.last_error = error_message or "Webhook delivery failed"
        if retry_at is None or attempt_number >= delivery.max_attempts:
            delivery.status = WebhookDeliveryStatus.EXHAUSTED
            delivery.next_attempt_at = None
            delivery.completed_at = timezone.now()
        else:
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.next_attempt_at = retry_at
            delivery.completed_at = None

    delivery.save(
        update_fields=[
            "attempt_count",
            "status",
            "last_error",
            "next_attempt_at",
            "completed_at",
            "updated_at",
        ]
    )
    return delivery


def manual_resend(delivery: WebhookDelivery) -> WebhookDelivery:
    """Queue an immediate retry; keeps the same public_id / delivery identity."""
    if delivery.status == WebhookDeliveryStatus.SUCCEEDED:
        raise WebhookDeliveryError("Başarılı teslimat yeniden gönderilemez.")
    delivery.status = WebhookDeliveryStatus.PENDING
    delivery.next_attempt_at = timezone.now()
    delivery.completed_at = None
    if delivery.attempt_count >= delivery.max_attempts:
        delivery.max_attempts = delivery.attempt_count + 1
    delivery.save(
        update_fields=[
            "status",
            "next_attempt_at",
            "completed_at",
            "max_attempts",
            "updated_at",
        ]
    )
    from apps.webhooks.tasks import process_webhook_delivery

    process_webhook_delivery.delay(delivery.id)
    return delivery


def process_due_deliveries(*, limit: int = 100) -> dict[str, int]:
    now = timezone.now()
    ids = list(
        WebhookDelivery.objects.filter(
            status__in=[
                WebhookDeliveryStatus.PENDING,
                WebhookDeliveryStatus.FAILED,
            ],
            next_attempt_at__lte=now,
            endpoint__is_active=True,
        )
        .order_by("next_attempt_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    processed = 0
    for delivery_id in ids:
        try:
            process_delivery(delivery_id)
            processed += 1
        except Exception:  # noqa: BLE001
            logger.exception("webhook delivery failed id=%s", delivery_id)
    return {"due": len(ids), "processed": processed}
