"""NP-332 technical + NP-333 business metrics."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from apps.ops.models import MetricKind, MetricSample

_API_TIMINGS_KEY = "np:ops:api_timings"
_API_TIMINGS_MAX = 500


def record_api_timing(path: str, status_code: int, duration_ms: int) -> None:
    bucket = cache.get(_API_TIMINGS_KEY) or []
    bucket.append(
        {
            "path": path[:120],
            "status": int(status_code),
            "ms": int(duration_ms),
            "ts": timezone.now().isoformat(),
        }
    )
    cache.set(_API_TIMINGS_KEY, bucket[-_API_TIMINGS_MAX:], 3600)


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
    ordered = sorted(values)
    def pct(p: float) -> float:
        if len(ordered) == 1:
            return float(ordered[0])
        k = (len(ordered) - 1) * p
        f = int(k)
        c = min(f + 1, len(ordered) - 1)
        return float(ordered[f] + (ordered[c] - ordered[f]) * (k - f))
    return {
        "p50": round(pct(0.50), 2),
        "p95": round(pct(0.95), 2),
        "p99": round(pct(0.99), 2),
        "count": len(ordered),
        "error_rate": 0.0,
    }


def technical_metrics() -> dict[str, Any]:
    timings = cache.get(_API_TIMINGS_KEY) or []
    ms_values = [float(t["ms"]) for t in timings]
    errors = sum(1 for t in timings if int(t["status"]) >= 500)
    api = _percentiles(ms_values)
    if timings:
        api["error_rate"] = round(100.0 * errors / len(timings), 2)

    # Celery queue lengths (best-effort via Redis)
    queues = {}
    try:
        from django.conf import settings
        import redis

        client = redis.from_url(settings.CELERY_BROKER_URL)
        for q in (
            "default",
            "imports",
            "integrations",
            "notifications",
            "risk",
            "forecast",
            "exports",
            "webhooks",
            "ai",
        ):
            queues[q] = int(client.llen(q))
    except Exception:  # noqa: BLE001
        queues = {q: -1 for q in ("default", "imports", "notifications")}

    cache_hits = cache.get("np:ops:cache_hits") or 0
    cache_misses = cache.get("np:ops:cache_misses") or 0
    total = cache_hits + cache_misses
    hit_rate = round(100.0 * cache_hits / total, 2) if total else 0.0

    return {
        "api": api,
        "celery_queues": queues,
        "cache_hit_rate": hit_rate,
        "db_connections": _db_connection_count(),
        "sync_success_rate": _ratio_metric("sync_success", "sync_total"),
        "webhook_success_rate": _ratio_metric("webhook_success", "webhook_total"),
        "email_delivery_rate": _ratio_metric("email_success", "email_total"),
        "failed_tasks": cache.get("np:ops:failed_tasks") or 0,
    }


def _db_connection_count() -> int:
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
    except Exception:  # noqa: BLE001
        return -1


def _ratio_metric(ok_key: str, total_key: str) -> float:
    ok = cache.get(f"np:ops:{ok_key}") or 0
    total = cache.get(f"np:ops:{total_key}") or 0
    if not total:
        return 100.0
    return round(100.0 * ok / total, 2)


def bump_counter(name: str, amount: int = 1) -> None:
    key = f"np:ops:{name}"
    try:
        cache.incr(key, amount)
    except ValueError:
        cache.set(key, amount, None)


def business_metrics(organization) -> dict[str, Any]:
    from datetime import datetime, time

    from django.utils.timezone import make_aware

    org_id = organization.pk if hasattr(organization, "pk") else organization
    today = timezone.localdate()
    day_start = make_aware(datetime.combine(today, time.min))

    collected = 0.0
    try:
        from apps.payments.models import Payment

        agg = (
            Payment.objects.filter(
                organization_id=org_id,
                cancelled_at__isnull=True,
                paid_at__gte=day_start,
            ).aggregate(s=Sum("amount"))["s"]
            or 0
        )
        collected = float(agg)
    except Exception:  # noqa: BLE001
        collected = 0.0

    from apps.collections.models import (
        CollectionTask,
        CollectionTaskStatus,
        PaymentPromise,
        PaymentPromiseStatus,
    )

    created_tasks = CollectionTask.objects.filter(
        organization_id=org_id, created_at__gte=day_start
    ).count()
    completed_tasks = CollectionTask.objects.filter(
        organization_id=org_id,
        status=CollectionTaskStatus.COMPLETED,
        completed_at__gte=day_start,
    ).count()
    kept_promises = PaymentPromise.objects.filter(
        organization_id=org_id,
        status=PaymentPromiseStatus.FULFILLED,
        fulfilled_at__gte=day_start,
    ).count()
    broken_promises = PaymentPromise.objects.filter(
        organization_id=org_id,
        status=PaymentPromiseStatus.BROKEN,
        updated_at__gte=day_start,
    ).count()

    risky_balance = 0.0
    try:
        from apps.customers.models import Customer, RiskStatus
        from apps.customers.metrics import customer_financial_metrics

        risky = Customer.objects.filter(
            organization_id=org_id,
            is_active=True,
            risk_status__in=[RiskStatus.HIGH, RiskStatus.CRITICAL]
            if hasattr(RiskStatus, "CRITICAL")
            else [RiskStatus.HIGH],
        )[:200]
        for c in risky:
            m = customer_financial_metrics(c)
            risky_balance += float(m.get("open_balance") or m.get("overdue_balance") or 0)
    except Exception:  # noqa: BLE001
        risky_balance = 0.0

    return {
        "daily_collected_amount": collected,
        "tasks_created": created_tasks,
        "tasks_completed": completed_tasks,
        "promises_kept": kept_promises,
        "promises_broken": broken_promises,
        "collection_cycle_days": None,  # filled by snapshot jobs when available
        "risky_balance": round(risky_balance, 2),
        "as_of": timezone.now().isoformat(),
    }


def persist_sample(
    *,
    name: str,
    value: float,
    kind: str = MetricKind.TECHNICAL,
    organization=None,
    labels: dict | None = None,
) -> MetricSample:
    return MetricSample.objects.create(
        organization=organization,
        kind=kind,
        name=name,
        value=value,
        labels=labels or {},
    )
