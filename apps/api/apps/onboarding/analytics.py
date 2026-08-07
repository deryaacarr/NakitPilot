"""NP-294 — product analytics (no PII / no financial values)."""

from __future__ import annotations

from typing import Any

from apps.onboarding.models import ProductAnalyticsEvent

ALLOWED_EVENTS = frozenset(
    {
        "organization_created",
        "integration_connected",
        "invoice_imported",
        "first_task_completed",
        "first_promise_created",
        "workflow_published",
        "report_exported",
        "subscription_started",
        "onboarding_step_completed",
        "sample_data_enabled",
        "wizard_completed",
    }
)

# Reject property keys that look like PII or money
_BLOCKED_KEY_FRAGMENTS = (
    "email",
    "phone",
    "name",
    "tax",
    "iban",
    "amount",
    "balance",
    "price",
    "total",
    "password",
    "token",
    "address",
    "note",
    "message",
    "content",
)


class AnalyticsError(Exception):
    def __init__(self, message: str, code: str = "analytics_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _sanitize_properties(props: dict[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    if not props:
        return clean
    for key, value in props.items():
        k = str(key).lower()
        if any(frag in k for frag in _BLOCKED_KEY_FRAGMENTS):
            continue
        if isinstance(value, (int, float, bool)):
            clean[str(key)[:64]] = value
        elif isinstance(value, str) and len(value) <= 64:
            token = value.replace("-", "").replace("_", "")
            if value.isidentifier() or token.isalnum():
                clean[str(key)[:64]] = value[:64]
        # Drop free-text, money, nested objects
    return clean


def track_event(
    organization,
    event_name: str,
    properties: dict[str, Any] | None = None,
) -> ProductAnalyticsEvent:
    name = (event_name or "").strip()
    if name not in ALLOWED_EVENTS:
        raise AnalyticsError("İzin verilmeyen olay.", code="invalid_event")
    org_id = organization.pk if hasattr(organization, "pk") else organization
    return ProductAnalyticsEvent.objects.create(
        organization_id=org_id,
        event_name=name,
        properties=_sanitize_properties(properties),
    )
