"""DRF mixins/permissions that enforce organization-scoped access."""

from __future__ import annotations

from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from apps.organizations.tenancy import get_request_organization


class TenantQuerysetMixin:
    """
    Force queryset filtering by the request's current organization.

    Cross-tenant primary keys resolve as 404 (no existence leak).
    """

    organization_field = "organization"

    def get_current_organization(self):
        organization = get_request_organization(self.request)
        if organization is None:
            raise PermissionDenied(detail="Organization context is required.")
        return organization

    def get_queryset(self):
        queryset = super().get_queryset()
        organization = self.get_current_organization()
        user = self.request.user
        # NP-024 contract: filters use request.user.current_organization
        user.current_organization = organization
        if hasattr(queryset, "for_organization"):
            return queryset.for_organization(user.current_organization)
        return queryset.filter(**{self.organization_field: user.current_organization})

    def perform_create(self, serializer):
        organization = self.get_current_organization()
        self.request.user.current_organization = organization
        serializer.save(**{self.organization_field: self.request.user.current_organization})


class RequireTenantContextPermission(BasePermission):
    """Authenticated user must have current_organization bound by TenantMiddleware."""

    message = "Valid X-Organization-Id with active membership is required."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        organization = get_request_organization(request)
        if organization is None:
            return False
        request.user.current_organization = organization
        return True

    def has_object_permission(self, request, view, obj) -> bool:
        organization = get_request_organization(request)
        if organization is None:
            return False
        obj_org_id = getattr(obj, "organization_id", None)
        if obj_org_id is None and hasattr(obj, "organization"):
            obj_org_id = getattr(obj.organization, "pk", None)
        if obj_org_id != organization.pk:
            raise NotFound()
        return True
