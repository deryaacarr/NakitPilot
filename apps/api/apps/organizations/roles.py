"""Organization role → permission matrix (NP-023)."""

from __future__ import annotations

from enum import StrEnum

from apps.organizations.models import Role


class Permission(StrEnum):
    MANAGE_USERS = "manage_users"
    ADD_CUSTOMER = "add_customer"
    ADD_INVOICE = "add_invoice"
    MANAGE_COLLECTION_TASK = "manage_collection_task"
    ADD_PAYMENT = "add_payment"
    VIEW_REPORTS = "view_reports"
    MANAGE_SETTINGS = "manage_settings"
    # NP-353 / EPIC 35
    MANAGE_LEGAL = "manage_legal"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(Permission),
    Role.FINANCE_MANAGER: frozenset(
        {
            Permission.ADD_CUSTOMER,
            Permission.ADD_INVOICE,
            Permission.MANAGE_COLLECTION_TASK,
            Permission.ADD_PAYMENT,
            Permission.VIEW_REPORTS,
            Permission.MANAGE_LEGAL,
        }
    ),
    Role.COLLECTION_AGENT: frozenset(
        {
            Permission.MANAGE_COLLECTION_TASK,
            Permission.VIEW_REPORTS,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.VIEW_REPORTS,
        }
    ),
    Role.EXTERNAL_LAWYER: frozenset(
        {
            Permission.MANAGE_LEGAL,
        }
    ),
}


def permissions_for_role(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role: str, permission: Permission | str) -> bool:
    permission = Permission(permission)
    return permission in permissions_for_role(role)
