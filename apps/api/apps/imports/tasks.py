"""Celery tasks for import processing (NP-066)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="imports.process_import_job", bind=True, queue="imports")
def process_import_job_task(self, job_id: int) -> dict:
    from apps.imports.models import ImportJob
    from apps.imports.services import process_import_job
    from apps.ops.locks import LockError, distributed_lock
    from apps.ops.tracing import bind_celery_headers, span

    bind_celery_headers(getattr(self.request, "headers", None) or {})
    ImportJob.objects.filter(pk=job_id).update(celery_task_id=self.request.id or "")
    try:
        with distributed_lock("import_job", job_id, timeout=3600):
            with span("import.process", job_id=job_id):
                result = process_import_job(job_id)
    except LockError:
        logger.warning("import job already running id=%s", job_id)
        return {"skipped": True, "reason": "lock_held", "job_id": job_id}
    logger.info("process_import_job id=%s result=%s", job_id, result)
    return result
