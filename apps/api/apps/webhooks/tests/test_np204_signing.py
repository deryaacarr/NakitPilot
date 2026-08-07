"""NP-204 — Webhook HMAC SHA-256 signing."""

import hashlib
import hmac
import json
import time

import pytest

from apps.webhooks.signing import (
    HEADER_DELIVERY_ID,
    HEADER_EVENT,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    build_signed_headers,
    prepare_outbound_request,
    sign_payload,
    verify_signature,
)


def test_required_headers_present():
    body = json.dumps({"id": 1}, separators=(",", ":"))
    headers = build_signed_headers(
        secret="whsec_test",
        event_type="payment.created",
        delivery_id=1842,
        body=body,
        timestamp=1_700_000_000,
    )
    assert set(headers) == {
        HEADER_EVENT,
        HEADER_TIMESTAMP,
        HEADER_SIGNATURE,
        HEADER_DELIVERY_ID,
    }
    assert headers[HEADER_EVENT] == "payment.created"
    assert headers[HEADER_TIMESTAMP] == "1700000000"
    assert headers[HEADER_DELIVERY_ID] == "1842"
    assert headers[HEADER_SIGNATURE].startswith("sha256=")


def test_signature_matches_hmac_sha256():
    secret = "whsec_abc"
    ts = 1_700_000_100
    delivery_id = "del-9"
    event = "invoice.paid"
    body = b'{"ok":true}'
    material = f"{ts}.{delivery_id}.{event}.".encode("utf-8") + body
    expected_hex = hmac.new(secret.encode(), material, hashlib.sha256).hexdigest()

    signature = sign_payload(
        secret=secret,
        timestamp=ts,
        delivery_id=delivery_id,
        event_type=event,
        body=body,
    )
    assert signature == f"sha256={expected_hex}"


def test_verify_accepts_valid_and_rejects_tamper():
    secret = "whsec_verify"
    body = '{"amount":"10.00"}'
    headers = build_signed_headers(
        secret=secret,
        event_type="payment.created",
        delivery_id="d-1",
        body=body,
        timestamp=int(time.time()),
    )
    assert verify_signature(secret=secret, headers=headers, body=body) is True

    tampered = dict(headers)
    tampered[HEADER_SIGNATURE] = "sha256=" + ("0" * 64)
    assert verify_signature(secret=secret, headers=tampered, body=body) is False

    assert (
        verify_signature(secret=secret, headers=headers, body='{"amount":"11.00"}')
        is False
    )


def test_verify_rejects_stale_timestamp():
    secret = "whsec_stale"
    body = "{}"
    headers = build_signed_headers(
        secret=secret,
        event_type="forecast.updated",
        delivery_id="d-2",
        body=body,
        timestamp=1_000_000_000,
    )
    assert (
        verify_signature(
            secret=secret,
            headers=headers,
            body=body,
            tolerance_seconds=300,
            now=1_000_000_000 + 301,
        )
        is False
    )


def test_prepare_outbound_request_includes_content_type():
    prepared = prepare_outbound_request(
        secret="whsec_out",
        event_type="invoice.created",
        delivery_id=55,
        body='{"n":1}',
        timestamp=1_700_000_200,
    )
    assert prepared["headers"]["Content-Type"] == "application/json"
    assert prepared["headers"][HEADER_EVENT] == "invoice.created"
    assert prepared["body"] == b'{"n":1}'
    assert verify_signature(
        secret="whsec_out",
        headers=prepared["headers"],
        body=prepared["body"],
        now=1_700_000_200,
    )


def test_header_lookup_is_case_insensitive():
    secret = "whsec_case"
    body = "x"
    headers = build_signed_headers(
        secret=secret,
        event_type="collection_task.created",
        delivery_id="c-1",
        body=body,
        timestamp=int(time.time()),
    )
    lower = {k.lower(): v for k, v in headers.items()}
    assert verify_signature(secret=secret, headers=lower, body=body) is True
