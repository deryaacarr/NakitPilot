"""EPIC 16 — report export jobs (NP-163)."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel


class ReportType(models.TextChoices):
    OVERDUE_RECEIVABLES = "OVERDUE_RECEIVABLES", "Gecikmiş alacak"
    COLLECTION_ACTIVITY = "COLLECTION_ACTIVITY", "Tahsilat aktivite"
    CUSTOMER_RISK = "CUSTOMER_RISK", "Müşteri risk"


class ExportJobStatus(models.TextChoices):
    PREPARING = "PREPARING", "Hazırlanıyor"
    READY = "READY", "Hazır"
    FAILED = "FAILED", "Başarısız"
    EXPIRED = "EXPIRED", "Süresi doldu"


class ExportJob(TenantModel):
    """Async Excel export job (NP-163)."""

    report_type = models.CharField(max_length=64, choices=ReportType.choices)
    status = models.CharField(
        max_length=16,
        choices=ExportJobStatus.choices,
        default=ExportJobStatus.PREPARING,
        db_index=True,
    )
    filters = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_export_jobs",
    )
    original_filename = models.CharField(max_length=255, blank=True)
    stored_path = models.CharField(max_length=512, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    row_count = models.PositiveIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "export job"
        verbose_name_plural = "export jobs"
        indexes = [
            models.Index(fields=("organization", "status", "created_at")),
            models.Index(fields=("organization", "report_type")),
        ]

    def __str__(self) -> str:
        return f"{self.report_type} ({self.status})"

    @property
    def is_downloadable(self) -> bool:
        if self.status != ExportJobStatus.READY:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return bool(self.stored_path)
