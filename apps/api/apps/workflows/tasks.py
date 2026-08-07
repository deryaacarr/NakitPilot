"""Celery tasks for workflow delay resumes (NP-214)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="workflows.process_due_resumes")
def process_due_workflow_resumes(limit: int = 100) -> dict:
    from apps.workflows.engine import process_due_resumes

    result = process_due_resumes(limit=limit)
    logger.info("workflow due resumes processed=%s", result)
    return result
