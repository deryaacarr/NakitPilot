"""NP-326 — archive old hot-path rows."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.ops.models import ArchiveRun

ARCHIVABLE = {
    "audit_log": ("apps.audit.models", "AuditLog", "created_at"),
    "workflow_log": ("apps.workflows.models", "WorkflowExecutionLog", "created_at"),
    "notification": ("apps.notifications.models", "DashboardAlert", "created_at"),
    "webhook_delivery": ("apps.webhooks.models", "WebhookDelivery", "created_at"),
    "sync_log": ("apps.integrations.models", "SyncJob", "created_at"),
}


def archive_entity(
    entity: str,
    *,
    older_than_days: int = 365,
    dry_run: bool = True,
    batch_size: int = 1000,
    user=None,
) -> ArchiveRun:
    if entity not in ARCHIVABLE:
        raise ValueError(f"Desteklenmeyen entity: {entity}")
    module_path, model_name, field = ARCHIVABLE[entity]
    run = ArchiveRun.objects.create(
        entity=entity,
        older_than_days=older_than_days,
        dry_run=dry_run,
        started_by=user,
    )
    cutoff = timezone.now() - timedelta(days=older_than_days)
    details: dict[str, Any] = {"cutoff": cutoff.isoformat()}
    moved = 0
    try:
        module = __import__(module_path, fromlist=[model_name])
        model = getattr(module, model_name)
        qs = model.objects.filter(**{f"{field}__lt": cutoff}).order_by(field)
        count = qs.count()
        details["matched"] = count
        if not dry_run and count:
            # Soft archive: mark metadata or delete in batches (hot DB relief)
            # Prefer deleting webhook bodies / old notifications; audit may move to cold table later.
            if entity in {"notification", "webhook_delivery", "sync_log", "workflow_log"}:
                while True:
                    ids = list(qs.values_list("pk", flat=True)[:batch_size])
                    if not ids:
                        break
                    deleted, _ = model.objects.filter(pk__in=ids).delete()
                    moved += deleted
            elif entity == "audit_log":
                # Keep audit longer — only trim if explicitly requested; mark in details
                details["note"] = "Audit log silinmedi; cold storage dışa aktarımı önerilir."
                moved = 0
        else:
            moved = 0 if dry_run else moved
            if dry_run:
                moved = count
        run.rows_moved = moved
        run.details = details
        run.finished_at = timezone.now()
        run.save()
    except Exception as exc:  # noqa: BLE001
        run.details = {**details, "error": str(exc)}
        run.finished_at = timezone.now()
        run.save()
    return run
