"""Export job orchestration (NP-163)."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.reports.excel import rows_to_workbook
from apps.reports.models import ExportJob, ExportJobStatus, ReportType
from apps.reports.services_activity import collection_activity_report
from apps.reports.services_overdue import overdue_receivables_report
from apps.reports.services_risk import customer_risk_report

logger = logging.getLogger(__name__)

EXPORT_TTL_HOURS = 24
FILENAME_PREFIX = {
    ReportType.OVERDUE_RECEIVABLES: "gecikmis_alacak",
    ReportType.COLLECTION_ACTIVITY: "tahsilat_aktivite",
    ReportType.CUSTOMER_RISK: "musteri_risk",
}


def collect_report_rows(organization, report_type: str, filters: dict[str, Any]) -> list[dict]:
    if report_type == ReportType.OVERDUE_RECEIVABLES:
        return overdue_receivables_report(organization, filters=filters)
    if report_type == ReportType.COLLECTION_ACTIVITY:
        return collection_activity_report(organization, filters=filters)
    if report_type == ReportType.CUSTOMER_RISK:
        return customer_risk_report(organization, filters=filters)
    raise ValueError(f"Unknown report_type: {report_type}")


def _exports_root(organization_id: int) -> Path:
    root = Path(getattr(settings, "PRIVATE_UPLOAD_ROOT", settings.BASE_DIR / "private_uploads"))
    path = root / "org" / str(organization_id) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_export_job(
    *,
    organization,
    report_type: str,
    filters: dict[str, Any] | None = None,
    requested_by=None,
) -> ExportJob:
    if report_type not in ReportType.values:
        raise ValueError("invalid_report_type")
    stamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    prefix = FILENAME_PREFIX.get(report_type, "rapor")
    filename = f"{prefix}_{stamp}.xlsx"
    job = ExportJob.objects.create(
        organization=organization,
        report_type=report_type,
        status=ExportJobStatus.PREPARING,
        filters=filters or {},
        requested_by=requested_by,
        original_filename=filename,
        expires_at=timezone.now() + timedelta(hours=EXPORT_TTL_HOURS),
    )
    return job


def enqueue_export_job(job: ExportJob) -> ExportJob:
    """Enqueue Celery task, or run sync in DEBUG / tests / ALWAYS_EAGER."""
    import sys

    from apps.reports.tasks import generate_export_task

    run_sync = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)) or settings.DEBUG or any(
        "pytest" in arg for arg in sys.argv
    )
    if run_sync:
        generate_export_job(job.id)
        job.refresh_from_db()
        return job

    try:
        async_result = generate_export_task.delay(job.id)
        job.celery_task_id = async_result.id or ""
        job.save(update_fields=["celery_task_id", "updated_at"])
    except Exception:  # noqa: BLE001 — fall back if broker is down
        logger.warning("celery enqueue failed; generating export synchronously id=%s", job.id)
        generate_export_job(job.id)
        job.refresh_from_db()
    return job


def generate_export_job(job_id: int) -> dict[str, Any]:
    try:
        job = ExportJob.objects.select_related("organization").get(pk=job_id)
    except ExportJob.DoesNotExist:
        return {"ok": False, "detail": "not_found"}

    if job.status == ExportJobStatus.EXPIRED:
        return {"ok": False, "detail": "expired"}

    try:
        rows = collect_report_rows(job.organization, job.report_type, job.filters or {})
        content = rows_to_workbook(job.report_type, rows)
        dest = _exports_root(job.organization_id) / f"{uuid.uuid4().hex}.xlsx"
        dest.write_bytes(content)
        job.stored_path = str(dest)
        job.file_size = len(content)
        job.row_count = len(rows)
        job.status = ExportJobStatus.READY
        job.error_message = ""
        job.completed_at = timezone.now()
        if not job.expires_at:
            job.expires_at = timezone.now() + timedelta(hours=EXPORT_TTL_HOURS)
        job.save(
            update_fields=[
                "stored_path",
                "file_size",
                "row_count",
                "status",
                "error_message",
                "completed_at",
                "expires_at",
                "updated_at",
            ]
        )
        logger.info("export ready id=%s rows=%s", job.id, job.row_count)
        return {"ok": True, "job_id": job.id, "rows": job.row_count}
    except Exception as exc:  # noqa: BLE001
        logger.exception("export failed id=%s", job_id)
        ExportJob.objects.filter(pk=job_id).update(
            status=ExportJobStatus.FAILED,
            error_message=str(exc)[:2000],
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return {"ok": False, "detail": str(exc)}


def expire_stale_exports() -> dict[str, int]:
    now = timezone.now()
    qs = ExportJob.objects.filter(
        status=ExportJobStatus.READY,
        expires_at__isnull=False,
        expires_at__lte=now,
    )
    expired = 0
    for job in qs.iterator(chunk_size=100):
        if job.stored_path:
            try:
                Path(job.stored_path).unlink(missing_ok=True)
            except OSError:
                pass
        job.status = ExportJobStatus.EXPIRED
        job.save(update_fields=["status", "updated_at"])
        expired += 1
    return {"expired": expired}
