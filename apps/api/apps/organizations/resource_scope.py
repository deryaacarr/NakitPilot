"""NP-301 — resource-based authorization helpers."""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from apps.organizations.structure import ResourceAccess, ResourceScope


def get_resource_rules(membership) -> dict[str, Any]:
    if membership is None:
        return {}
    if getattr(membership, "custom_role_id", None) and membership.custom_role_id:
        role = membership.custom_role
        if role is not None:
            return dict(role.resource_rules or {})
    # Built-in roles: full access unless VIEWER-like
    from apps.organizations.models import Role

    if membership.role == Role.VIEWER:
        return {
            "customers": ResourceScope.ALL,
            "invoices": ResourceScope.ALL,
            "payments": ResourceAccess.READ,
            "risk_score": True,
            "risk_reasons": False,
        }
    return {
        "customers": ResourceScope.ALL,
        "invoices": ResourceScope.ALL,
        "payments": ResourceAccess.FULL,
        "risk_score": True,
        "risk_reasons": True,
    }


def can_mutate_payments(membership) -> bool:
    rules = get_resource_rules(membership)
    return rules.get("payments", ResourceAccess.FULL) == ResourceAccess.FULL


def can_view_risk_reasons(membership) -> bool:
    return bool(get_resource_rules(membership).get("risk_reasons", True))


def can_view_risk_score(membership) -> bool:
    return bool(get_resource_rules(membership).get("risk_score", True))


def filter_customers_for_membership(membership, qs: QuerySet) -> QuerySet:
    rules = get_resource_rules(membership)
    scope = rules.get("customers", ResourceScope.ALL)
    if scope in (ResourceScope.ALL, "all", None):
        return qs
    if scope in (ResourceScope.NONE, "none"):
        return qs.none()
    user_id = membership.user_id
    if scope in (ResourceScope.ASSIGNED, "assigned_only"):
        return qs.filter(
            Q(assignments__user_id=user_id) | Q(assigned_user_id=user_id)
        ).distinct()
    if scope in (ResourceScope.BRANCH, "branch") and membership.branch_id:
        return qs.filter(
            Q(assignments__branch_id=membership.branch_id) | Q(assignments__user_id=user_id)
        ).distinct()
    if scope in (ResourceScope.TEAM, "team"):
        from apps.organizations.structure import TeamMembership

        team_ids = list(
            TeamMembership.objects.filter(
                organization_id=membership.organization_id,
                user_id=user_id,
            ).values_list("team_id", flat=True)
        )
        return qs.filter(
            Q(assignments__team_id__in=team_ids) | Q(assignments__user_id=user_id)
        ).distinct()
    return qs


def filter_invoices_for_membership(membership, qs: QuerySet) -> QuerySet:
    rules = get_resource_rules(membership)
    scope = rules.get("invoices", ResourceScope.ALL)
    if scope in (ResourceScope.ALL, "all", None):
        return qs
    if scope in (ResourceScope.NONE, "none"):
        return qs.none()
    # Restrict via customer visibility
    from apps.customers.models import Customer

    customer_ids = filter_customers_for_membership(
        membership, Customer.objects.filter(organization_id=membership.organization_id)
    ).values_list("id", flat=True)
    return qs.filter(customer_id__in=customer_ids)


def mask_customer_payload(payload: dict[str, Any], membership) -> dict[str, Any]:
    """NP-313 — role-based PII masking for API responses."""
    from apps.governance.masking import mask_email_display, mask_phone_display, mask_tax_display

    rules = get_resource_rules(membership)
    # Roles with only view_reports or external accountant style → mask PII
    perms = set()
    if membership.custom_role_id and membership.custom_role:
        perms = set(membership.custom_role.permissions or [])
    from apps.organizations.roles import permissions_for_role

    if not perms:
        perms = {p.value for p in permissions_for_role(membership.role)}

    needs_mask = (
        membership.custom_role
        and membership.custom_role.slug in {"sadece-rapor", "dis-muhasebeci"}
    ) or (
        "manage_users" not in perms
        and "manage_settings" not in perms
        and rules.get("customers") != ResourceScope.ALL
    )
    # Always apply light mask for VIEWER
    from apps.organizations.models import Role

    if membership.role == Role.VIEWER or needs_mask:
        if "email" in payload and payload["email"]:
            payload["email"] = mask_email_display(str(payload["email"]))
        if "phone" in payload and payload["phone"]:
            payload["phone"] = mask_phone_display(str(payload["phone"]))
        if "tax_number" in payload and payload["tax_number"]:
            payload["tax_number"] = mask_tax_display(str(payload["tax_number"]))
    if not can_view_risk_score(membership):
        payload.pop("risk_score", None)
        payload["risk_status"] = payload.get("risk_status", "***")
    if not can_view_risk_reasons(membership):
        payload.pop("risk_reasons", None)
        payload.pop("risk_explanation", None)
        if "notes" in payload:
            payload["notes"] = ""
    return payload
