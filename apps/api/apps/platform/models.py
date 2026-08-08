"""EPIC 36 — platform ops: super-admin, impersonation, flags, maintenance."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class FeatureFlagKey(models.TextChoices):
    KOLAYBI_INTEGRATION = "kolaybi_integration", "KolayBi entegrasyonu"
    AI_ASSISTANT = "ai_assistant", "AI asistan"
    WORKFLOW_BUILDER = "workflow_builder", "İş akışı oluşturucu"
    WHATSAPP = "whatsapp", "WhatsApp"
    ADVANCED_FORECAST = "advanced_forecast", "Gelişmiş tahmin"
    LEGAL_MODULE = "legal_module", "Hukuki modül"


class FeatureFlag(models.Model):
    """NP-362 — runtime feature flags (org / plan / % / environment)."""

    key = models.CharField(max_length=64, unique=True, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    enabled = models.BooleanField(default=False)
    # Empty list = all environments
    environments = models.JSONField(default=list, blank=True)
    # Empty list = all plans
    plan_codes = models.JSONField(default=list, blank=True)
    # Empty list = all orgs (unless organization_ids empty + require_org_list)
    organization_ids = models.JSONField(default=list, blank=True)
    rollout_percentage = models.PositiveSmallIntegerField(
        default=100,
        help_text="0–100; deterministic hash of org/user id.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)
        verbose_name = "feature flag"
        verbose_name_plural = "feature flags"

    def __str__(self) -> str:
        return self.key


class MaintenanceScope(models.TextChoices):
    GLOBAL = "GLOBAL", "Tüm sistem"
    ORGANIZATION = "ORGANIZATION", "Organizasyon"
    MODULE = "MODULE", "Modül"


class MaintenanceMode(models.TextChoices):
    FULL = "FULL", "Tam bakım (erişim kapalı)"
    READ_ONLY = "READ_ONLY", "Salt okunur"


class MaintenanceWindow(models.Model):
    """NP-363 — maintenance / read-only windows."""

    scope = models.CharField(max_length=32, choices=MaintenanceScope.choices)
    mode = models.CharField(
        max_length=16,
        choices=MaintenanceMode.choices,
        default=MaintenanceMode.FULL,
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="maintenance_windows",
    )
    module = models.CharField(
        max_length=64,
        blank=True,
        help_text="e.g. collections, legal, billing, payments",
    )
    message = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_maintenance_windows",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-starts_at",)
        verbose_name = "maintenance window"
        verbose_name_plural = "maintenance windows"

    def __str__(self) -> str:
        return f"{self.scope}:{self.mode}:{self.module or '*'}"

    def is_in_effect(self, *, now=None) -> bool:
        now = now or timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at <= now:
            return False
        return True


class ImpersonationSession(models.Model):
    """NP-361 — time-boxed support impersonation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="impersonation_sessions_as_staff",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="impersonation_sessions_as_target",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="impersonation_sessions",
    )
    reason = models.TextField()
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=64, blank=True)
    notify_target = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-started_at",)
        verbose_name = "impersonation session"
        verbose_name_plural = "impersonation sessions"
        indexes = [
            models.Index(fields=("is_active", "expires_at")),
            models.Index(fields=("target_user", "is_active")),
        ]

    def __str__(self) -> str:
        return f"Impersonation {self.staff_user_id}→{self.target_user_id}"

    def is_valid(self, *, now=None) -> bool:
        now = now or timezone.now()
        return bool(self.is_active and self.ended_at is None and self.expires_at > now)


class SupportTicketStatus(models.TextChoices):
    OPEN = "OPEN", "Açık"
    IN_PROGRESS = "IN_PROGRESS", "İşlemde"
    WAITING_CUSTOMER = "WAITING_CUSTOMER", "Müşteri bekleniyor"
    RESOLVED = "RESOLVED", "Çözüldü"
    CLOSED = "CLOSED", "Kapalı"


class SupportTicket(models.Model):
    """NP-360 — lightweight support tickets (no customer PII by default in admin)."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="support_tickets",
    )
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=SupportTicketStatus.choices,
        default=SupportTicketStatus.OPEN,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_support_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "support ticket"
        verbose_name_plural = "support tickets"


class PlatformAuditLog(models.Model):
    """Platform-level audit (not tenant-scoped) for staff actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_audit_logs",
    )
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64, blank=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_audit_logs",
    )
    summary = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "platform audit log"
        verbose_name_plural = "platform audit logs"
