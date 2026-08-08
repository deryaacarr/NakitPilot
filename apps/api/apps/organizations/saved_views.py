"""NP-402 — saved table filter views."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models, transaction

from apps.organizations.tenancy import TenantModel


class SavedTableView(TenantModel):
    """Named filter/column/sort snapshot for finance tables."""

    resource = models.CharField(max_length=64, db_index=True)  # invoices | customers
    name = models.CharField(max_length=120)
    filters = models.JSONField(default=dict, blank=True)
    hidden_columns = models.JSONField(default=list, blank=True)
    sort = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    share_token = models.CharField(max_length=48, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_table_views",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "saved table view"
        verbose_name_plural = "saved table views"
        indexes = [
            models.Index(fields=["organization", "resource"], name="savedview_org_resource_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.resource}: {self.name}"

    def ensure_share_token(self) -> str:
        if not self.share_token:
            self.share_token = secrets.token_urlsafe(18)
            self.save(update_fields=["share_token", "updated_at"])
        return self.share_token

    @classmethod
    def set_default(cls, *, organization_id: int, resource: str, view_id: int, user_id: int | None) -> "SavedTableView":
        with transaction.atomic():
            cls.objects.filter(
                organization_id=organization_id,
                resource=resource,
                created_by_id=user_id,
                is_default=True,
            ).update(is_default=False)
            view = cls.objects.select_for_update().get(
                pk=view_id, organization_id=organization_id, resource=resource
            )
            view.is_default = True
            view.save(update_fields=["is_default", "updated_at"])
            return view
