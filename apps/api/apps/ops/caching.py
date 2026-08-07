"""NP-323 — org-scoped cache helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from django.core.cache import cache

# Default TTLs (seconds)
TTL_DASHBOARD = 60
TTL_AGING = 120
TTL_RISK = 180
TTL_FORECAST = 300
TTL_ORG_SETTINGS = 600
TTL_PERMISSIONS = 300


def org_cache_key(organization_id: int, namespace: str, *parts: Any) -> str:
    """Cache key MUST include organization id (NP-323)."""
    raw = ":".join(str(p) for p in parts)
    digest = hashlib.sha1(raw.encode()).hexdigest()[:12] if raw else "0"
    return f"np:org:{organization_id}:{namespace}:{digest}"


def get_or_set_org(
    organization_id: int,
    namespace: str,
    producer: Callable[[], Any],
    *parts: Any,
    ttl: int = 60,
) -> Any:
    key = org_cache_key(organization_id, namespace, *parts)
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = producer()
    # JSON-serializable safety for Redis
    try:
        cache.set(key, value, ttl)
    except Exception:  # noqa: BLE001
        try:
            cache.set(key, json.loads(json.dumps(value, default=str)), ttl)
        except Exception:  # noqa: BLE001
            pass
    return value


def invalidate_org_namespace(organization_id: int, namespace: str) -> None:
    """Best-effort: LocMem/Redis without SCAN — delete known common keys via version bump."""
    bump_key = f"np:org:{organization_id}:ver:{namespace}"
    try:
        cache.incr(bump_key)
    except ValueError:
        cache.set(bump_key, 1, None)


def versioned_org_key(organization_id: int, namespace: str, *parts: Any) -> str:
    ver = cache.get(f"np:org:{organization_id}:ver:{namespace}") or 0
    return org_cache_key(organization_id, f"{namespace}:v{ver}", *parts)
