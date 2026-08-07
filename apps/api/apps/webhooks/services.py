"""Create webhook endpoints and subscriptions (NP-203)."""

from __future__ import annotations

from django.db import transaction

from apps.webhooks.events import ALL_EVENT_TYPES, WebhookEventType
from apps.webhooks.models import WebhookEndpoint, WebhookSubscription
from apps.webhooks.secrets import (
    WebhookSecretError,
    encrypt_webhook_secret,
    generate_webhook_secret,
    secret_hint,
)


class WebhookServiceError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def validate_event_types(event_types: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in event_types:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        if value not in ALL_EVENT_TYPES:
            raise WebhookServiceError(f"Geçersiz event tipi: {value}")
        seen.add(value)
        cleaned.append(value)
    return cleaned


@transaction.atomic
def create_endpoint(
    *,
    organization,
    name: str,
    url: str,
    event_types: list[str] | None = None,
    description: str = "",
    created_by=None,
) -> tuple[WebhookEndpoint, str, list[WebhookSubscription]]:
    """
    Create endpoint + optional subscriptions.

    Returns (endpoint, raw_secret_once, subscriptions).
    """
    name = (name or "").strip()
    url = (url or "").strip()
    if not name:
        raise WebhookServiceError("Endpoint adı gerekli.")
    if not url:
        raise WebhookServiceError("Endpoint URL gerekli.")
    if not (url.startswith("https://") or url.startswith("http://")):
        raise WebhookServiceError("Endpoint URL http(s) olmalıdır.")

    raw_secret = generate_webhook_secret()
    try:
        encrypted = encrypt_webhook_secret(raw_secret)
    except WebhookSecretError as exc:
        raise WebhookServiceError(str(exc)) from exc

    endpoint = WebhookEndpoint.objects.create(
        organization=organization,
        name=name,
        url=url,
        description=(description or "").strip(),
        secret_encrypted=encrypted,
        secret_hint=secret_hint(raw_secret),
        created_by=created_by,
    )

    subscriptions: list[WebhookSubscription] = []
    for event_type in validate_event_types(event_types or []):
        subscriptions.append(
            WebhookSubscription.objects.create(
                organization=organization,
                endpoint=endpoint,
                event_type=event_type,
            )
        )
    return endpoint, raw_secret, subscriptions


def list_event_types() -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in WebhookEventType.choices]
