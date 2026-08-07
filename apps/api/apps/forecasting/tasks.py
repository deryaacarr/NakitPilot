"""Celery tasks for forecasting (NP-112)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="forecasting.calculate_organization_forecast")
def calculate_organization_forecast_task(
    organization_id: int | None = None,
) -> dict:
    from apps.forecasting.weekly import calculate_organization_forecast
    from apps.organizations.models import Organization

    qs = Organization.objects.filter(is_active=True)
    if organization_id is not None:
        qs = qs.filter(pk=organization_id)

    updated = 0
    for org in qs.iterator(chunk_size=100):
        calculate_organization_forecast(org.pk, persist=True)
        updated += 1
    logger.info("calculate_organization_forecast updated=%s", updated)
    return {"updated": updated}
