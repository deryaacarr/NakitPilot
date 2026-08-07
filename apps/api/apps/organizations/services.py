from __future__ import annotations

from apps.organizations.models import Membership, Organization, Role
from apps.organizations.roles import Permission, role_has_permission


def get_active_membership(user, organization: Organization | int) -> Membership | None:
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    org_id = organization.pk if isinstance(organization, Organization) else organization
    return (
        Membership.objects.select_related("organization", "user", "custom_role", "branch")
        .filter(
            user=user,
            organization_id=org_id,
            is_active=True,
        )
        .first()
    )


def membership_has_permission(membership: Membership, permission: Permission | str) -> bool:
    """NP-300 — custom role permissions override built-in matrix."""
    permission = Permission(permission)
    if membership.custom_role_id and membership.custom_role and membership.custom_role.is_active:
        perms = set(membership.custom_role.permissions or [])
        # OWNER/ADMIN system roles keep full access even with custom role attached
        if membership.role in {Role.OWNER, Role.ADMIN}:
            return True
        return permission.value in perms or str(permission) in perms
    return role_has_permission(membership.role, permission)


def user_has_organization_permission(
    user,
    organization: Organization | int,
    permission: Permission | str,
) -> bool:
    membership = get_active_membership(user, organization)
    if membership is None:
        return False
    return membership_has_permission(membership, permission)


def user_organizations_queryset(user):
    return Organization.objects.filter(
        memberships__user=user,
        memberships__is_active=True,
    ).distinct()
