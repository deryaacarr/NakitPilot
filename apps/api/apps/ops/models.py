"""EPIC 32/33 — ops models (metrics samples, alerts, archive, status, loadtest)."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel


class MetricKind(models.TextChoices):
    TECHNICAL = "technical", "Teknik"
    BUSINESS = "business", "İş"


class MetricSample(models.Model):
    """Point-in-time metric sample (NP-332 / NP-333). organization may be null for global."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="metric_samples",
    )
    kind = models.CharField(max_length=16, choices=MetricKind.choices)
    name = models.CharField(max_length=64, db_index=True)
    value = models.FloatField()
    labels = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [
            models.Index(fields=["name", "recorded_at"]),
            models.Index(fields=["organization", "name", "recorded_at"]),
        ]


class AlertSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class AlertRule(models.Model):
    """NP-334 — declarative alert rules."""

    key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    severity = models.CharField(
        max_length=16, choices=AlertSeverity.choices, default=AlertSeverity.WARNING
    )
    # expression metadata: metric, operator, threshold
    metric_name = models.CharField(max_length=64)
    operator = models.CharField(max_length=8, default=">")  # >, >=, <
    threshold = models.FloatField()
    is_enabled = models.BooleanField(default=True)
    runbook_key = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("key",)


class AlertEvent(models.Model):
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name="events")
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alert_events",
    )
    message = models.CharField(max_length=255)
    value = models.FloatField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class StatusComponentCode(models.TextChoices):
    WEB = "web", "Web uygulaması"
    API = "api", "API"
    INTEGRATIONS = "integrations", "Entegrasyonlar"
    EMAIL = "email", "E-posta"
    WEBHOOK = "webhook", "Webhook"
    FILE_UPLOAD = "file_upload", "Dosya yükleme"
    REPORTING = "reporting", "Raporlama"


class StatusState(models.TextChoices):
    OPERATIONAL = "operational", "Çalışıyor"
    DEGRADED = "degraded", "Yavaşlama"
    PARTIAL_OUTAGE = "partial_outage", "Kısmi kesinti"
    MAJOR_OUTAGE = "major_outage", "Kesinti"


class StatusComponent(models.Model):
    """NP-335 — public status page components."""

    code = models.CharField(max_length=32, choices=StatusComponentCode.choices, unique=True)
    name = models.CharField(max_length=128)
    state = models.CharField(
        max_length=32, choices=StatusState.choices, default=StatusState.OPERATIONAL
    )
    message = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)


class ArchiveRun(models.Model):
    """NP-326 — archive job audit."""

    entity = models.CharField(max_length=64)
    older_than_days = models.PositiveIntegerField()
    rows_moved = models.PositiveIntegerField(default=0)
    dry_run = models.BooleanField(default=True)
    details = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )


class LoadTestRun(TenantModel):
    """NP-320 — recorded scale benchmark results."""

    profile = models.CharField(max_length=32, default="small")
    concurrent_users = models.PositiveIntegerField(default=1)
    customers = models.PositiveIntegerField(default=0)
    invoices = models.PositiveIntegerField(default=0)
    activities = models.PositiveIntegerField(default=0)
    timings_ms = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
