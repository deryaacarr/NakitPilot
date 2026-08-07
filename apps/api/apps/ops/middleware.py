"""NP-330 / NP-331 — request_id + timing + trace headers."""

from __future__ import annotations

import logging
import uuid

from django.conf import settings

from apps.ops.logging_context import (
    RequestTiming,
    bind_context,
    ensure_request_id,
    reset_context,
)
from apps.ops.metrics import record_api_timing

logger = logging.getLogger("apps.ops.request")


class ObservabilityMiddleware:
    """
    Adds:
    - X-Request-Id / X-Trace-Id
    - structured log line with duration_ms
    - contextvars for organization/user when available
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reset_context()
        timing = RequestTiming()
        incoming = request.headers.get("X-Request-Id") or request.headers.get("X-Correlation-Id")
        request_id = ensure_request_id(incoming)
        trace_id = request.headers.get("X-Trace-Id") or request_id
        span_id = uuid.uuid4().hex[:16]
        request.request_id = request_id
        request.trace_id = trace_id
        request.span_id = span_id

        bind_context(
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            service="api",
            environment=getattr(settings, "SENTRY_ENVIRONMENT", "development"),
            action=f"{request.method} {request.path}",
        )

        response = self.get_response(request)

        org = getattr(request, "organization", None)
        user = getattr(request, "user", None)
        bind_context(
            organization_id=getattr(org, "pk", None) or request.headers.get("X-Organization-Id"),
            user_id=getattr(user, "pk", None) if getattr(user, "is_authenticated", False) else None,
            status=response.status_code,
            duration_ms=timing.duration_ms(),
        )
        duration = timing.duration_ms()
        record_api_timing(request.path, response.status_code, duration)
        logger.info(
            "request completed",
            extra={
                "action": f"{request.method} {request.path}",
                "duration_ms": duration,
                "status": response.status_code,
            },
        )
        response["X-Request-Id"] = request_id
        response["X-Trace-Id"] = trace_id
        response["X-Span-Id"] = span_id
        return response
