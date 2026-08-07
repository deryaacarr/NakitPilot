"""NP-183 — Sentry bootstrap with PII scrubbing."""

from __future__ import annotations

import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from apps.security.masking import SENSITIVE_KEYS, mask_email, mask_string

_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+=/]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def _scrub_string(value: str) -> str:
    value = _BEARER_RE.sub("Bearer ***", value)
    value = _JWT_RE.sub("***jwt***", value)
    value = _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), value)
    return mask_string(value)


def _scrub_obj(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "***"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                out[key] = "***"
            else:
                out[key] = _scrub_obj(item, depth + 1)
        return out
    if isinstance(value, list):
        return [_scrub_obj(item, depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return _scrub_string(value)
    return value


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Strip secrets / PII before events leave the process."""
    del hint  # unused; kept for Sentry signature
    if "request" in event:
        req = event["request"]
        headers = req.get("headers") or {}
        for h in list(headers):
            if h.lower() in {"authorization", "cookie", "x-api-key", "set-cookie"}:
                headers[h] = "***"
        req["headers"] = headers
        if "data" in req:
            req["data"] = _scrub_obj(req["data"])
        if "cookies" in req:
            req["cookies"] = "***"
        if "query_string" in req and isinstance(req["query_string"], str):
            req["query_string"] = _scrub_string(req["query_string"])
        event["request"] = req

    if "extra" in event:
        event["extra"] = _scrub_obj(event["extra"])
    if "contexts" in event:
        event["contexts"] = _scrub_obj(event["contexts"])

    # Never send user email/phone as identifiable PII — IDs only.
    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {
            "id": user.get("id"),
        }

    if "message" in event and isinstance(event["message"], str):
        event["message"] = _scrub_string(event["message"])

    return event


def traces_sampler(sampling_context: dict[str, Any]) -> float:
    # Drop health probes from performance budget.
    tx = sampling_context.get("transaction_context") or {}
    name = str(tx.get("name") or "")
    if "/health" in name or name.endswith("health-live") or name.endswith("health-ready"):
        return 0.0
    return float(sampling_context.get("parent_sampling_decision") or 0.1)


def init_sentry(*, dsn: str, release: str, environment: str, traces_sample_rate: float = 0.1) -> None:
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        release=release or None,
        environment=environment,
        integrations=[
            DjangoIntegration(transaction_style="url"),
            CeleryIntegration(monitor_beat_tasks=True, propagate_traces=True),
            RedisIntegration(),
        ],
        send_default_pii=False,
        before_send=before_send,
        traces_sampler=traces_sampler if traces_sample_rate else None,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=0.0,
    )


def set_request_sentry_scope(request) -> None:
    """Attach user id + organization id (no email / phone)."""
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        sentry_sdk.set_user({"id": str(user.pk)})
    else:
        sentry_sdk.set_user(None)

    org = getattr(request, "organization", None)
    if org is not None:
        sentry_sdk.set_tag("organization_id", str(org.pk))
    else:
        claimed = getattr(request, "organization_id_claimed", None)
        if claimed is not None:
            sentry_sdk.set_tag("organization_id", str(claimed))
