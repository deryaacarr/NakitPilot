"""NP-311 — organization data export."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.governance.models import DataExportJob, DataExportStatus

ALLOWED_DATASETS = frozenset(
    {
        "customers",
        "invoices",
        "payments",
        "tasks",
        "activities",
        "files",
        "audit",
    }
)


def run_export_job(job: DataExportJob) -> DataExportJob:
    job.status = DataExportStatus.RUNNING
    job.save(update_fields=["status"])
    org = job.organization
    org_id = org.pk
    datasets = [d for d in (job.datasets or []) if d in ALLOWED_DATASETS]
    payload: dict[str, Any] = {"organization_id": org_id, "exported_at": timezone.now().isoformat()}
    counts: dict[str, int] = {}

    if "customers" in datasets:
        from apps.customers.models import Customer

        rows = list(
            Customer.objects.filter(organization_id=org_id, is_sample=False).values(
                "id", "code", "name", "email", "phone", "tax_number", "city", "risk_status"
            )
        )
        payload["customers"] = rows
        counts["customers"] = len(rows)

    if "invoices" in datasets:
        from apps.invoices.models import Invoice

        rows = list(
            Invoice.objects.filter(organization_id=org_id, is_sample=False).values(
                "id", "number", "customer_id", "total_amount", "status", "due_date"
            )
        )
        payload["invoices"] = rows
        counts["invoices"] = len(rows)

    if "payments" in datasets:
        try:
            from apps.payments.models import Payment

            rows = list(
                Payment.objects.filter(organization_id=org_id).values(
                    "id", "amount", "currency", "paid_at", "customer_id"
                )
            )
            payload["payments"] = rows
            counts["payments"] = len(rows)
        except Exception:  # noqa: BLE001
            payload["payments"] = []
            counts["payments"] = 0

    if "tasks" in datasets:
        try:
            from apps.collections.models import CollectionTask

            rows = list(
                CollectionTask.objects.filter(organization_id=org_id).values(
                    "id", "title", "status", "due_date", "customer_id"
                )
            )
            payload["tasks"] = rows
            counts["tasks"] = len(rows)
        except Exception:  # noqa: BLE001
            payload["tasks"] = []
            counts["tasks"] = 0

    if "activities" in datasets:
        try:
            from apps.collections.models import CollectionActivity

            rows = list(
                CollectionActivity.objects.filter(organization_id=org_id).values(
                    "id", "activity_type", "summary", "occurred_at", "customer_id"
                )[:5000]
            )
            payload["activities"] = rows
            counts["activities"] = len(rows)
        except Exception:  # noqa: BLE001
            payload["activities"] = []
            counts["activities"] = 0

    if "files" in datasets:
        payload["files"] = []
        counts["files"] = 0

    if "audit" in datasets:
        from apps.audit.models import AuditLog

        rows = list(
            AuditLog.objects.filter(organization_id=org_id).values(
                "id", "action", "entity_type", "entity_id", "summary", "created_at"
            )[:10000]
        )
        payload["audit"] = rows
        counts["audit"] = len(rows)

    root = Path(getattr(settings, "PRIVATE_UPLOAD_ROOT", settings.BASE_DIR / "private_uploads"))
    out_dir = root / f"org/{org_id}/exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"export_{job.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")

    job.file_path = str(path)
    job.row_counts = counts
    job.status = DataExportStatus.READY
    job.completed_at = timezone.now()
    job.expires_at = timezone.now() + timedelta(hours=24)
    job.save(
        update_fields=[
            "file_path",
            "row_counts",
            "status",
            "completed_at",
            "expires_at",
        ]
    )
    return job
