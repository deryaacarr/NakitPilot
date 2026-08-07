"""API key persistence (NP-200)."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel


class ApiKey(TenantModel):
    """Organization-scoped public API credential. Raw secret is never stored."""

    name = models.CharField(max_length=128)
    # Public identifier fragment shown in UI (npk_<prefix>…).
    prefix = models.CharField(max_length=16, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_keys",
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "API key"
        verbose_name_plural = "API keys"
        indexes = [
            models.Index(fields=("organization", "revoked_at"), name="apikey_org_revoked_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.display_prefix})"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @property
    def display_prefix(self) -> str:
        return f"npk_{self.prefix}"

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at", "updated_at"])

    def touch_last_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at", "updated_at"])


class ApiRequestLog(TenantModel):
    """Public API (/api/v1) request log for developer portal analytics (NP-206)."""

    api_key = models.ForeignKey(
        ApiKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_logs",
    )
    method = models.CharField(max_length=16)
    path = models.CharField(max_length=512)
    status_code = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_detail = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "API request log"
        verbose_name_plural = "API request logs"
        indexes = [
            models.Index(
                fields=("organization", "created_at"),
                name="apilog_org_created_idx",
            ),
            models.Index(
                fields=("organization", "status_code", "created_at"),
                name="apilog_org_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.path} → {self.status_code}"
