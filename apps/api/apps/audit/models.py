"""Audit log model + write helper (NP-073)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from apps.organizations.tenancy import TenantModel


class AuditLog(TenantModel):
    """Immutable-ish trail for sensitive business actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    summary = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "audit log"
        verbose_name_plural = "audit logs"
        indexes = [
            models.Index(fields=("organization", "entity_type", "entity_id")),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}:{self.entity_id}"


def write_audit_log(
    *,
    organization,
    actor=None,
    action: str,
    entity_type: str,
    entity_id: str | int,
    summary: str = "",
    changes: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        summary=summary[:255],
        changes=changes or {},
    )
