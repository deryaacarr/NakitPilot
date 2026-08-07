"""EPIC 29 — onboarding & product adoption (NP-290–294)."""

from __future__ import annotations

from django.db import models

from apps.organizations.tenancy import TenantModel


class OnboardingStep(models.TextChoices):
    COMPANY = "company", "Şirket bilgileri"
    INVITE = "invite", "Kullanıcı daveti"
    DATA_SOURCE = "data_source", "Veri kaynağı seçimi"
    FIRST_IMPORT = "first_import", "İlk veri aktarımı"
    RISK = "risk", "Risk ayarları"
    WORKFLOW = "workflow", "İlk tahsilat workflow’u"
    DASHBOARD = "dashboard", "Dashboard sonucu"


WIZARD_STEPS = [c.value for c in OnboardingStep]


class OnboardingState(TenantModel):
    """Per-organization wizard + adoption progress (NP-290 / NP-292)."""

    current_step = models.CharField(
        max_length=32,
        choices=OnboardingStep.choices,
        default=OnboardingStep.COMPANY,
    )
    completed_steps = models.JSONField(default=list, blank=True)
    wizard_completed = models.BooleanField(default=False)
    sample_data_enabled = models.BooleanField(default=False)
    # NP-292 weighted checklist flags (auto + manual)
    flags = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                name="onboarding_one_state_per_org",
            )
        ]

    def __str__(self) -> str:
        return f"Onboarding {self.organization_id} · {self.current_step}"


class FeatureAnnouncement(models.Model):
    """NP-293 — in-product feature announcements."""

    key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    help_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title


class ProductAnalyticsEvent(TenantModel):
    """
    NP-294 — product analytics.

    Never store free-text user inputs or financial amounts in `properties`.
    """

    event_name = models.CharField(max_length=64, db_index=True)
    properties = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=["organization", "event_name", "occurred_at"]),
        ]
