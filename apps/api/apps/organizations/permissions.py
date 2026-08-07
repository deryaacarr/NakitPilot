from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.organizations.roles import Permission
from apps.organizations.services import get_active_membership, user_has_organization_permission

ORGANIZATION_HEADER = "HTTP_X_ORGANIZATION_ID"


def resolve_organization_id(request) -> int | None:
    """Resolve tenant from header, query param, URL kwargs, or bound request.organization."""
    raw = request.META.get(ORGANIZATION_HEADER) or request.query_params.get("organization_id")
    if raw in (None, ""):
        kwargs = request.parser_context.get("kwargs", {}) if hasattr(request, "parser_context") else {}
        raw = kwargs.get("organization_id", kwargs.get("pk"))
    if raw not in (None, ""):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    org = getattr(request, "organization", None)
    if org is not None:
        return org.pk
    return None


class IsOrganizationMember(BasePermission):
    """User must have an active membership in the target organization."""

    message = "Active organization membership is required."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        organization_id = resolve_organization_id(request)
        if organization_id is None:
            return False
        membership = get_active_membership(request.user, organization_id)
        if membership is None:
            return False
        request.membership = membership
        request.organization = membership.organization
        return True


class HasOrganizationPermission(BasePermission):
    """
    Require a specific Permission for the organization context.

    Set `required_permission` on the view, or `read_permission` / `write_permission`.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        organization_id = resolve_organization_id(request)
        if organization_id is None:
            return False

        permission = getattr(view, "required_permission", None)
        if permission is None:
            if request.method in SAFE_METHODS:
                permission = getattr(view, "read_permission", Permission.VIEW_REPORTS)
            else:
                permission = getattr(view, "write_permission", None)
        if permission is None:
            return False

        if not user_has_organization_permission(request.user, organization_id, permission):
            return False

        membership = get_active_membership(request.user, organization_id)
        request.membership = membership
        if membership is not None:
            request.organization = membership.organization
        return True


class CanManageOrganizationSettings(BasePermission):
    """Members may read; MANAGE_SETTINGS required to update organization."""

    message = "You do not have permission to change organization settings."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        organization_id = resolve_organization_id(request)
        if organization_id is None:
            return False
        membership = get_active_membership(request.user, organization_id)
        if membership is None:
            return False
        request.membership = membership
        request.organization = membership.organization
        if request.method in SAFE_METHODS:
            return True
        return user_has_organization_permission(
            request.user,
            organization_id,
            Permission.MANAGE_SETTINGS,
        )
