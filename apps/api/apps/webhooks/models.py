"""Webhook subscription models (NP-203 / NP-205)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel
from apps.webhooks.events import WebhookEventType


class WebhookEndpoint(TenantModel):
    """HTTPS destination that receives signed webhook POSTs."""

    name = models.CharField(max_length=128)
    url = models.URLField(max_length=2048)
    description = models.TextField(blank=True, default="")
    # Fernet-encrypted signing secret; never expose after creation.
    secret_encrypted = models.TextField()
    secret_hint = models.CharField(max_length=16, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_webhook_endpoints",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "webhook endpoint"
        verbose_name_plural = "webhook endpoints"
        indexes = [
            models.Index(
                fields=("organization", "is_active"),
                name="wh_ep_org_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} → {self.url}"

    def deactivate(self) -> None:
        if self.is_active:
            self.is_active = False
            self.disabled_at = timezone.now()
            self.save(update_fields=["is_active", "disabled_at", "updated_at"])


class WebhookSubscription(TenantModel):
    """Subscribes an endpoint to a single event type."""

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    event_type = models.CharField(
        max_length=64,
        choices=WebhookEventType.choices,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("event_type",)
        verbose_name = "webhook subscription"
        verbose_name_plural = "webhook subscriptions"
        constraints = [
            models.UniqueConstraint(
                fields=("endpoint", "event_type"),
                name="uniq_wh_sub_endpoint_event",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "event_type", "is_active"),
                name="wh_sub_org_event_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.endpoint_id}:{self.event_type}"


class WebhookDeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    EXHAUSTED = "exhausted", "Exhausted"


class WebhookDelivery(TenantModel):
    """One outbound delivery of an event payload to an endpoint."""

    # Stable external id used in X-NakitPilot-Delivery-Id across all retries.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    subscription = models.ForeignKey(
        WebhookSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    event_type = models.CharField(
        max_length=64,
        choices=WebhookEventType.choices,
        db_index=True,
    )
    # Stable id for the producing domain event (dedupe / tracing).
    event_id = models.CharField(max_length=128, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=WebhookDeliveryStatus.choices,
        default=WebhookDeliveryStatus.PENDING,
        db_index=True,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    # Initial attempt + 6 retries (1m, 5m, 15m, 1h, 6h, 24h).
    max_attempts = models.PositiveIntegerField(default=7)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "webhook delivery"
        verbose_name_plural = "webhook deliveries"
        constraints = [
            models.UniqueConstraint(
                fields=("endpoint", "event_type", "event_id"),
                name="uniq_wh_delivery_ep_event",
            )
        ]
        indexes = [
            models.Index(
                fields=("status", "next_attempt_at"),
                name="wh_deliv_status_next_idx",
            ),
            models.Index(
                fields=("organization", "event_type", "created_at"),
                name="wh_deliv_org_event_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.event_id} → {self.endpoint_id} ({self.status})"


class WebhookAttempt(TenantModel):
    """Single HTTP attempt for a webhook delivery."""

    delivery = models.ForeignKey(
        WebhookDelivery,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt_number = models.PositiveIntegerField()
    request_url = models.URLField(max_length=2048, blank=True, default="")
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("attempt_number",)
        verbose_name = "webhook attempt"
        verbose_name_plural = "webhook attempts"
        constraints = [
            models.UniqueConstraint(
                fields=("delivery", "attempt_number"),
                name="uniq_wh_attempt_deliv_num",
            )
        ]

    def __str__(self) -> str:
        return f"delivery={self.delivery_id} attempt={self.attempt_number}"
