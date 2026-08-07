"""Ops Celery tasks — alerts + read-model refresh."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="ops.evaluate_alerts")
def evaluate_alerts_task() -> dict:
    from apps.ops.alerts import evaluate_alerts

    fired = evaluate_alerts()
    logger.info("ops.evaluate_alerts fired=%s", len(fired))
    return {"fired": len(fired)}


@shared_task(name="ops.refresh_read_models")
def refresh_read_models_task(organization_id: int | None = None) -> dict:
    from apps.dashboard.read_models import refresh_organization_daily_metrics
    from apps.ops.locks import LockError, distributed_lock
    from apps.organizations.models import Organization

    qs = Organization.objects.filter(is_active=True)
    if organization_id is not None:
        qs = qs.filter(pk=organization_id)
    n = 0
    for org in qs.iterator(chunk_size=50):
        try:
            with distributed_lock("read_model_refresh", org.pk, timeout=600):
                refresh_organization_daily_metrics(org.pk)
            n += 1
        except LockError:
            continue
    return {"refreshed": n}
