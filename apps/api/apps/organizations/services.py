from __future__ import annotations

from apps.organizations.models import Membership, Organization
from apps.organizations.roles import Permission, role_has_permission


def get_active_membership(user, organization: Organization | int) -> Membership | None:
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    org_id = organization.pk if isinstance(organization, Organization) else organization
    return (
        Membership.objects.select_related("organization", "user")
        .filter(
            user=user,
            organization_id=org_id,
            is_active=True,
        )
        .first()
    )


def user_has_organization_permission(
    user,
    organization: Organization | int,
    permission: Permission | str,
) -> bool:
    membership = get_active_membership(user, organization)
    if membership is None:
        return False
    return role_has_permission(membership.role, permission)


def user_organizations_queryset(user):
    return Organization.objects.filter(
        memberships__user=user,
        memberships__is_active=True,
    ).distinct()
