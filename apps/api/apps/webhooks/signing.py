"""Webhook request signing — HMAC SHA-256 (NP-204)."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

HEADER_EVENT = "X-NakitPilot-Event"
HEADER_TIMESTAMP = "X-NakitPilot-Timestamp"
HEADER_SIGNATURE = "X-NakitPilot-Signature"
HEADER_DELIVERY_ID = "X-NakitPilot-Delivery-Id"

SIGNATURE_PREFIX = "sha256="

# Receivers should reject timestamps older than this (seconds).
DEFAULT_TOLERANCE_SECONDS = 5 * 60


def canonical_signing_string(
    *,
    timestamp: int | str,
    delivery_id: str | int,
    event_type: str,
    body: str | bytes,
) -> bytes:
    """
    Material signed with HMAC-SHA256:

        {timestamp}.{delivery_id}.{event_type}.{raw_body}
    """
    if isinstance(body, bytes):
        body_bytes = body
    else:
        body_bytes = body.encode("utf-8")
    prefix = f"{timestamp}.{delivery_id}.{event_type}.".encode("utf-8")
    return prefix + body_bytes


def compute_signature(*, secret: str, signing_string: bytes) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_string,
        hashlib.sha256,
    ).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def sign_payload(
    *,
    secret: str,
    timestamp: int | str,
    delivery_id: str | int,
    event_type: str,
    body: str | bytes,
) -> str:
    return compute_signature(
        secret=secret,
        signing_string=canonical_signing_string(
            timestamp=timestamp,
            delivery_id=delivery_id,
            event_type=event_type,
            body=body,
        ),
    )


def build_signed_headers(
    *,
    secret: str,
    event_type: str,
    delivery_id: str | int,
    body: str | bytes,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Return the four required NakitPilot webhook headers."""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    signature = sign_payload(
        secret=secret,
        timestamp=ts,
        delivery_id=delivery_id,
        event_type=event_type,
        body=body,
    )
    return {
        HEADER_EVENT: str(event_type),
        HEADER_TIMESTAMP: str(ts),
        HEADER_SIGNATURE: signature,
        HEADER_DELIVERY_ID: str(delivery_id),
    }


def parse_signature_header(value: str) -> str:
    """Return hex digest from `sha256=<hex>` or bare hex."""
    raw = (value or "").strip()
    if raw.lower().startswith(SIGNATURE_PREFIX):
        return raw[len(SIGNATURE_PREFIX) :]
    return raw


def verify_signature(
    *,
    secret: str,
    headers: dict[str, str],
    body: str | bytes,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> bool:
    """
    Verify HMAC signature and optional timestamp skew.

    Header lookup is case-insensitive.
    """
    normalized = {str(k).lower(): str(v) for k, v in headers.items()}
    event_type = normalized.get(HEADER_EVENT.lower())
    timestamp_raw = normalized.get(HEADER_TIMESTAMP.lower())
    signature_raw = normalized.get(HEADER_SIGNATURE.lower())
    delivery_id = normalized.get(HEADER_DELIVERY_ID.lower())

    if not event_type or not timestamp_raw or not signature_raw or not delivery_id:
        return False

    try:
        timestamp = int(timestamp_raw)
    except (TypeError, ValueError):
        return False

    current = int(time.time()) if now is None else int(now)
    if tolerance_seconds >= 0 and abs(current - timestamp) > tolerance_seconds:
        return False

    expected = sign_payload(
        secret=secret,
        timestamp=timestamp,
        delivery_id=delivery_id,
        event_type=event_type,
        body=body,
    )
    provided = f"{SIGNATURE_PREFIX}{parse_signature_header(signature_raw)}"
    return hmac.compare_digest(expected, provided)


def prepare_outbound_request(
    *,
    secret: str,
    event_type: str,
    delivery_id: str | int,
    body: str | bytes,
    content_type: str = "application/json",
    timestamp: int | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build headers + body for an outbound webhook HTTP POST.

    Returns::

        {"headers": {...}, "body": bytes, "timestamp": int}
    """
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = body

    headers = {
        "Content-Type": content_type,
        "User-Agent": "NakitPilot-Webhooks/1.0",
        **build_signed_headers(
            secret=secret,
            event_type=event_type,
            delivery_id=delivery_id,
            body=body_bytes,
            timestamp=timestamp,
        ),
    }
    if extra_headers:
        headers.update(extra_headers)
    return {
        "headers": headers,
        "body": body_bytes,
        "timestamp": int(headers[HEADER_TIMESTAMP]),
    }
