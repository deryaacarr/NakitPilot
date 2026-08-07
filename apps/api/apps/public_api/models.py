"""Idempotency records for public API writes (NP-202)."""

from django.db import models

from apps.organizations.tenancy import TenantModel


class IdempotencyRecord(TenantModel):
    """
    Stores the first successful (or failed) response for an Idempotency-Key.

    Scoped per organization + API key so keys cannot collide across tenants.
    """

    class State(models.TextChoices):
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"

    api_key = models.ForeignKey(
        "api_keys.ApiKey",
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    key = models.CharField(max_length=255)
    endpoint = models.CharField(max_length=128, help_text="e.g. POST /api/v1/payments")
    request_hash = models.CharField(max_length=64)
    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.STARTED,
        db_index=True,
    )
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "idempotency record"
        verbose_name_plural = "idempotency records"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "api_key", "key"),
                name="uniq_idempotency_org_apikey_key",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "key"),
                name="idempotency_org_key_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.key} ({self.state})"
