"""Idempotency-Key handling for public API POST endpoints (NP-202)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from apps.api_keys.models import ApiKey
from apps.public_api.models import IdempotencyRecord

HEADER_NAME = "Idempotency-Key"
MAX_KEY_LENGTH = 255


class IdempotencyError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def extract_idempotency_key(request) -> str | None:
    raw = request.headers.get(HEADER_NAME) or request.META.get("HTTP_IDEMPOTENCY_KEY")
    if raw is None:
        return None
    key = str(raw).strip()
    return key or None


def hash_request_payload(data: Any) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), cls=DjangoJSONEncoder)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_response_data(data: Any) -> Any:
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def require_idempotency_key(request) -> str:
    key = extract_idempotency_key(request)
    if not key:
        raise IdempotencyError(
            f"{HEADER_NAME} header zorunludur.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if len(key) > MAX_KEY_LENGTH:
        raise IdempotencyError(
            f"{HEADER_NAME} en fazla {MAX_KEY_LENGTH} karakter olabilir.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return key


def run_idempotent(
    *,
    request,
    organization,
    endpoint: str,
    payload: Any,
    execute: Callable[[], Response],
    require_key: bool = True,
) -> Response:
    """
    Execute `execute()` once per Idempotency-Key; replay stored response on retries.

    Same key + different body → 409 Conflict.
    Concurrent in-flight same key → 409 Conflict.
    """
    api_key = getattr(request, "auth", None)
    if not isinstance(api_key, ApiKey):
        # Without an API key principal, fall through (should not happen on public API).
        return execute()

    try:
        if require_key:
            key = require_idempotency_key(request)
        else:
            key = extract_idempotency_key(request)
            if not key:
                return execute()
    except IdempotencyError as exc:
        return Response({"detail": str(exc)}, status=exc.status_code)

    request_hash = hash_request_payload(payload if payload is not None else {})

    with transaction.atomic():
        existing = (
            IdempotencyRecord.objects.select_for_update()
            .filter(organization=organization, api_key=api_key, key=key)
            .first()
        )
        if existing is not None:
            return _replay_or_conflict(existing, request_hash=request_hash, endpoint=endpoint)

        try:
            record = IdempotencyRecord.objects.create(
                organization=organization,
                api_key=api_key,
                key=key,
                endpoint=endpoint,
                request_hash=request_hash,
                state=IdempotencyRecord.State.STARTED,
            )
        except IntegrityError:
            existing = (
                IdempotencyRecord.objects.select_for_update()
                .filter(organization=organization, api_key=api_key, key=key)
                .first()
            )
            if existing is None:
                raise
            return _replay_or_conflict(existing, request_hash=request_hash, endpoint=endpoint)

    # Run outside the row lock so long writes don't block other keys;
    # re-lock only to finalize.
    try:
        response = execute()
    except Exception:
        IdempotencyRecord.objects.filter(pk=record.pk).delete()
        raise
    _finalize_record(record, response)
    response["Idempotent-Replayed"] = "false"
    return response


def _replay_or_conflict(
    record: IdempotencyRecord,
    *,
    request_hash: str,
    endpoint: str,
) -> Response:
    if record.request_hash != request_hash:
        return Response(
            {
                "detail": (
                    "Aynı Idempotency-Key farklı bir istek gövdesi ile kullanıldı."
                ),
                "code": "idempotency_key_reuse",
            },
            status=status.HTTP_409_CONFLICT,
        )
    if record.endpoint and record.endpoint != endpoint:
        return Response(
            {
                "detail": "Idempotency-Key başka bir endpoint için kullanılmış.",
                "code": "idempotency_endpoint_mismatch",
            },
            status=status.HTTP_409_CONFLICT,
        )
    if record.state != IdempotencyRecord.State.COMPLETED:
        return Response(
            {
                "detail": "Bu Idempotency-Key ile bir istek hâlâ işleniyor.",
                "code": "idempotency_in_progress",
            },
            status=status.HTTP_409_CONFLICT,
        )
    response = Response(record.response_body, status=record.response_status or 200)
    response["Idempotent-Replayed"] = "true"
    return response


def _finalize_record(record: IdempotencyRecord, response: Response) -> None:
    # Only cache successful creates and client/validation errors that are deterministic.
    # 5xx is not stored so clients can retry with the same key.
    status_code = int(response.status_code)
    if status_code >= 500:
        IdempotencyRecord.objects.filter(pk=record.pk).delete()
        return
    IdempotencyRecord.objects.filter(pk=record.pk).update(
        state=IdempotencyRecord.State.COMPLETED,
        response_status=status_code,
        response_body=serialize_response_data(response.data),
    )
