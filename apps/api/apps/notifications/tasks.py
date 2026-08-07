"""Celery tasks for in-app notifications and org-TZ scheduling (NP-142)."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# (job_key, hour, minute, weekday|None) — weekday: Mon=0 … Sun=6
ORG_SCHEDULE = (
    ("daily_reminders", 8, 0, None),
    ("overdue_invoices", 0, 15, None),
    ("broken_promises", 0, 30, None),
    ("risk_scores", 1, 0, None),
    ("weekly_forecast", 1, 30, 0),  # Monday 01:30 local
)

WINDOW_SECONDS = 5 * 60


def _org_tz(organization) -> ZoneInfo:
    name = (organization.timezone or "Europe/Istanbul").strip() or "Europe/Istanbul"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Istanbul")


def _local_now(organization) -> datetime:
    return datetime.now(_org_tz(organization))


def _in_window(local_now: datetime, hour: int, minute: int, weekday: int | None) -> bool:
    if weekday is not None and local_now.weekday() != weekday:
        return False
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = (local_now - target).total_seconds()
    return 0 <= delta < WINDOW_SECONDS


def _claim(organization_id: int, job: str, local_date) -> bool:
    key = f"np:sched:{organization_id}:{job}:{local_date.isoformat()}"
    return bool(cache.add(key, "1", timeout=60 * 60 * 26))


def run_org_job(organization, job: str) -> dict:
    """Execute a single scheduled job for one organization (org local date)."""
    from apps.collections.promises import process_broken_promises
    from apps.collections.services import generate_overdue_invoice_collection_tasks
    from apps.forecasting.weekly import calculate_organization_forecast
    from apps.invoices.services import recalculate_all_invoice_statuses
    from apps.notifications.services import (
        generate_daily_task_promise_reminders,
        notify_high_risk_customers,
    )
    from apps.risk.services import calculate_customer_risk
    from apps.customers.models import Customer

    tz = _org_tz(organization)
    with timezone.override(tz):
        as_of = timezone.localdate()
        if job == "daily_reminders":
            return generate_daily_task_promise_reminders(organization, as_of=as_of)
        if job == "overdue_invoices":
            statuses = recalculate_all_invoice_statuses(
                as_of=as_of, organization=organization
            )
            tasks = generate_overdue_invoice_collection_tasks(
                organization=organization, as_of=as_of
            )
            return {**statuses, **tasks}
        if job == "broken_promises":
            return process_broken_promises(organization=organization, as_of=as_of)
        if job == "risk_scores":
            updated = 0
            for customer in Customer.objects.filter(
                organization=organization, is_active=True
            ).iterator(chunk_size=200):
                calculate_customer_risk(customer.pk)
                updated += 1
            alerts = notify_high_risk_customers(organization, as_of=as_of)
            return {"risk_updated": updated, "high_risk_alerts": alerts}
        if job == "weekly_forecast":
            calculate_organization_forecast(organization.pk, persist=True)
            return {"forecast": 1}
    return {"skipped": True}


@shared_task(name="notifications.dispatch_org_timezone_jobs")
def dispatch_org_timezone_jobs() -> dict:
    """
    NP-142: every ~5 minutes, run due jobs in each org's timezone.
    Idempotent via cache keys per org/job/local-date.
    """
    from apps.organizations.models import Organization

    fired: list[dict] = []
    for org in Organization.objects.filter(is_active=True).iterator(chunk_size=100):
        local_now = _local_now(org)
        local_date = local_now.date()
        for job, hour, minute, weekday in ORG_SCHEDULE:
            if not _in_window(local_now, hour, minute, weekday):
                continue
            if not _claim(org.id, job, local_date):
                continue
            try:
                result = run_org_job(org, job)
                fired.append({"org": org.id, "job": job, "result": result})
                logger.info(
                    "org schedule org=%s job=%s local=%s result=%s",
                    org.id,
                    job,
                    local_now.isoformat(),
                    result,
                )
            except Exception:  # noqa: BLE001 — one org must not block others
                logger.exception("org schedule failed org=%s job=%s", org.id, job)
                fired.append({"org": org.id, "job": job, "error": True})

    return {"fired": len(fired), "details": fired[:50]}


@shared_task(name="notifications.generate_daily_reminders")
def generate_daily_reminders_task(organization_id: int | None = None) -> dict:
    from apps.notifications.services import generate_daily_task_promise_reminders
    from apps.organizations.models import Organization

    qs = Organization.objects.filter(is_active=True)
    if organization_id is not None:
        qs = qs.filter(pk=organization_id)
    total = {}
    for org in qs:
        with timezone.override(_org_tz(org)):
            total[org.id] = generate_daily_task_promise_reminders(org)
    return total
