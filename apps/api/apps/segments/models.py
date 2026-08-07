"""EPIC 26 — dynamic segments, strategies, A/B tests (NP-260–263)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.organizations.tenancy import TenantModel


class CustomerSegment(TenantModel):
    """Dynamic customer segment with JSON rule tree (NP-260 / NP-261)."""

    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128)
    description = models.TextField(blank=True)
    # Rule tree: {"all": [...]} or {"any": [...]} with field/operator/value
    rules = models.JSONField(default=dict, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_segments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "customer segment"
        verbose_name_plural = "customer segments"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"),
                name="segments_uniq_org_slug",
            )
        ]

    def __str__(self) -> str:
        return self.name


class StrategyStepType(models.TextChoices):
    EMAIL = "EMAIL", "E-posta"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    CALL_TASK = "CALL_TASK", "Telefon görevi"
    WAIT_DAYS = "WAIT_DAYS", "Bekle"
    MANAGER_NOTIFY = "MANAGER_NOTIFY", "Yönetici bildirimi"
    DAILY_FOLLOWUP = "DAILY_FOLLOWUP", "Günlük takip"
    NO_AUTO_MESSAGE = "NO_AUTO_MESSAGE", "Otomatik mesaj yok"
    ACCOUNT_MANAGER_ONLY = "ACCOUNT_MANAGER_ONLY", "Yalnızca hesap yöneticisi"


class CollectionStrategy(TenantModel):
    """Segment-based collection playbook (NP-262)."""

    name = models.CharField(max_length=128)
    segment = models.ForeignKey(
        CustomerSegment,
        on_delete=models.CASCADE,
        related_name="strategies",
    )
    # Ordered list of steps: [{type, wait_days?, template_id?, tone?, note?}]
    steps = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "collection strategy"
        verbose_name_plural = "collection strategies"

    def __str__(self) -> str:
        return self.name


class ABTestChannel(models.TextChoices):
    EMAIL = "EMAIL", "E-posta"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    SMS = "SMS", "SMS"


class ABTestStatus(models.TextChoices):
    DRAFT = "DRAFT", "Taslak"
    RUNNING = "RUNNING", "Çalışıyor"
    PAUSED = "PAUSED", "Duraklatıldı"
    COMPLETED = "COMPLETED", "Tamamlandı"


class MessageABTest(TenantModel):
    """A/B message experiment (NP-263)."""

    name = models.CharField(max_length=128)
    status = models.CharField(
        max_length=16,
        choices=ABTestStatus.choices,
        default=ABTestStatus.DRAFT,
    )
    segment = models.ForeignKey(
        CustomerSegment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ab_tests",
    )
    # Factors under test
    variant_a = models.JSONField(default=dict, blank=True)
    variant_b = models.JSONField(default=dict, blank=True)
    # e.g. subject, tone, send_hour, channel, reminder_interval_days
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ab_tests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "message A/B test"
        verbose_name_plural = "message A/B tests"

    def __str__(self) -> str:
        return self.name


class MessageABTestAssignment(TenantModel):
    """Customer assigned to a variant; outcomes tracked for success metrics."""

    test = models.ForeignKey(
        MessageABTest,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="ab_test_assignments",
    )
    variant = models.CharField(max_length=1)  # A | B
    sent_at = models.DateTimeField(null=True, blank=True)
    replied = models.BooleanField(default=False)
    promise_within_7d = models.BooleanField(default=False)
    paid_within_7d = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("test", "customer"),
                name="segments_ab_assignment_uniq",
            )
        ]
