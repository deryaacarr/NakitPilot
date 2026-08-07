"""Celery tasks for report exports (NP-163)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="reports.generate_export", bind=True)
def generate_export_task(self, job_id: int) -> dict:
    from apps.reports.exports import generate_export_job
    from apps.reports.models import ExportJob

    ExportJob.objects.filter(pk=job_id).update(celery_task_id=self.request.id or "")
    result = generate_export_job(job_id)
    logger.info("generate_export id=%s result=%s", job_id, result)
    return result


@shared_task(name="reports.expire_stale_exports")
def expire_stale_exports_task() -> dict:
    from apps.reports.exports import expire_stale_exports

    result = expire_stale_exports()
    logger.info("expire_stale_exports %s", result)
    return result
