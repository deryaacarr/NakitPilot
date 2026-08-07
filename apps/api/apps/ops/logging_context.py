"""NP-330 — request-scoped logging context."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

_local = threading.local()


def reset_context() -> None:
    _local.ctx = {}


def get_context() -> dict[str, Any]:
    ctx = getattr(_local, "ctx", None)
    if ctx is None:
        _local.ctx = {}
        ctx = _local.ctx
    return ctx


def bind_context(**kwargs: Any) -> None:
    get_context().update({k: v for k, v in kwargs.items() if v is not None})


def ensure_request_id(request_id: str | None = None) -> str:
    ctx = get_context()
    rid = request_id or ctx.get("request_id") or uuid.uuid4().hex
    ctx["request_id"] = rid
    return rid


class ContextFilter(logging.Filter):
    """Inject NP-330 fields into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_context()
        record.request_id = ctx.get("request_id", "-")
        record.organization_id = ctx.get("organization_id", "-")
        record.user_id = ctx.get("user_id", "-")
        record.service = ctx.get("service", "api")
        record.environment = ctx.get("environment", "development")
        record.action = getattr(record, "action", ctx.get("action", record.name))
        record.duration_ms = getattr(record, "duration_ms", ctx.get("duration_ms", "-"))
        record.status = getattr(record, "status", ctx.get("status", "-"))
        record.trace_id = ctx.get("trace_id", record.request_id)
        record.span_id = ctx.get("span_id", "-")
        return True


class RequestTiming:
    def __init__(self):
        self.started = time.perf_counter()

    def duration_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)
