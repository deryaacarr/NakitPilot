"""NP-331 — lightweight distributed tracing helpers."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Iterator

from apps.ops.logging_context import bind_context, get_context

logger = logging.getLogger("apps.ops.trace")


@contextmanager
def span(name: str, **attrs) -> Iterator[str]:
    """Create a child span; logs start/end with trace_id correlation."""
    ctx = get_context()
    parent = ctx.get("span_id", "-")
    span_id = uuid.uuid4().hex[:16]
    bind_context(span_id=span_id, action=name)
    started = time.perf_counter()
    logger.info(
        "span.start %s parent=%s attrs=%s",
        name,
        parent,
        {k: v for k, v in attrs.items() if k not in {"password", "token", "body"}},
        extra={"action": name, "status": "start"},
    )
    try:
        yield span_id
        status = "ok"
    except Exception:
        status = "error"
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "span.end %s",
            name,
            extra={"action": name, "duration_ms": duration_ms, "status": status},
        )
        bind_context(span_id=parent)


def celery_headers_from_context() -> dict[str, str]:
    ctx = get_context()
    return {
        "np_request_id": str(ctx.get("request_id") or ""),
        "np_trace_id": str(ctx.get("trace_id") or ctx.get("request_id") or ""),
    }


def bind_celery_headers(headers: dict | None) -> None:
    if not headers:
        return
    bind_context(
        request_id=headers.get("np_request_id") or None,
        trace_id=headers.get("np_trace_id") or headers.get("np_request_id") or None,
        service="celery",
    )
