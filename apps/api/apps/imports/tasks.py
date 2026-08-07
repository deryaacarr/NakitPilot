"""Celery tasks for import processing (NP-066)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="imports.process_import_job", bind=True)
def process_import_job_task(self, job_id: int) -> dict:
    from apps.imports.models import ImportJob
    from apps.imports.services import process_import_job

    ImportJob.objects.filter(pk=job_id).update(celery_task_id=self.request.id or "")
    result = process_import_job(job_id)
    logger.info("process_import_job id=%s result=%s", job_id, result)
    return result
