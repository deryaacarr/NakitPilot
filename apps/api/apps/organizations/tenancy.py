"""Tenant-aware model base and request helpers."""

from __future__ import annotations

from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_organization(self, organization):
        if organization is None:
            return self.none()
        org_id = organization.pk if hasattr(organization, "pk") else organization
        return self.filter(organization_id=org_id)


class TenantManager(models.Manager):
    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db)

    def for_organization(self, organization) -> TenantQuerySet:
        return self.get_queryset().for_organization(organization)


class TenantModel(models.Model):
    """
    Abstract base for all organization-scoped business data.

    Queries must go through `.for_organization(request.user.current_organization)`.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = TenantManager()

    class Meta:
        abstract = True


def get_request_organization(request):
    """Prefer middleware-bound organization, then user.current_organization."""
    organization = getattr(request, "organization", None)
    if organization is not None:
        return organization
    user = getattr(request, "user", None)
    if user is not None:
        return getattr(user, "current_organization", None)
    return None
