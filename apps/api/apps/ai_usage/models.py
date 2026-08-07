"""NP-235 — AI usage metrics and cost-control limits."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.0000")


class AIFeature(models.TextChoices):
    CUSTOMER_SUMMARY = "customer_summary", "Customer summary"
    CALL_PREP = "call_prep", "Call preparation"
    NOTE_PARSE = "note_parse", "Note parsing"
    MESSAGE_ASSISTANT = "message_assistant", "Message assistant"
    PAYMENT_PLAN = "payment_plan", "Payment plan"
    GENERIC = "generic", "Generic"


class AIPackage(models.TextChoices):
    STARTER = "starter", "Starter"
    PRO = "pro", "Pro"
    ENTERPRISE = "enterprise", "Enterprise"


class AIUsageEvent(TenantModel):
    """
    Per-call metering row.

    Fields required by NP-235: organization_id, user_id, feature,
    input_tokens, output_tokens, estimated_cost, model, created_at.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_events",
    )
    feature = models.CharField(max_length=64, choices=AIFeature.choices, db_index=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    model = models.CharField(max_length=64, default="deterministic")
    cache_hit = models.BooleanField(default=False)
    truncated = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "AI usage event"
        verbose_name_plural = "AI usage events"
        indexes = [
            models.Index(fields=("organization", "created_at")),
            models.Index(fields=("organization", "user", "created_at")),
            models.Index(fields=("organization", "feature", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.feature} {self.input_tokens}+{self.output_tokens} @ {self.model}"


class AIUsageLimitConfig(TenantModel):
    """Per-organization package quotas and budgets (NP-235)."""

    package = models.CharField(
        max_length=32,
        choices=AIPackage.choices,
        default=AIPackage.STARTER,
    )
    # Package-based monthly token pool (input+output).
    package_monthly_tokens = models.PositiveIntegerField(default=100_000)
    # Daily per-user token cap.
    daily_user_tokens = models.PositiveIntegerField(default=10_000)
    # Organization monthly budget in currency units (TRY).
    org_budget_monthly = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("50.0000"),
        validators=[MinValueValidator(ZERO)],
    )
    # Long-content truncation threshold (characters).
    max_input_chars = models.PositiveIntegerField(default=8_000)
    # Response cache TTL in seconds (0 = disabled).
    cache_ttl_seconds = models.PositiveIntegerField(default=3_600)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI usage limit config"
        verbose_name_plural = "AI usage limit configs"
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                name="ai_usage_limit_one_per_org",
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization_id} · {self.package}"
