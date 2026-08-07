"""Celery tasks for collections (NP-084)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="collections.process_broken_promises")
def process_broken_promises_task() -> dict:
    from apps.collections.promises import process_broken_promises

    result = process_broken_promises()
    logger.info("process_broken_promises %s", result)
    return result


@shared_task(name="collections.auto_generate_collection_tasks")
def auto_generate_collection_tasks_task() -> dict:
    from apps.collections.services import auto_generate_collection_tasks

    result = auto_generate_collection_tasks()
    logger.info("auto_generate_collection_tasks %s", result)
    return result


@shared_task(name="collections.mark_overdue_tasks_and_promises")
def mark_overdue_tasks_and_promises_task() -> dict:
    """Alias used in architecture docs — same daily generator."""
    return auto_generate_collection_tasks_task()
