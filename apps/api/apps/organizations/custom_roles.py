"""NP-300 — seed & manage custom roles."""

from __future__ import annotations

from typing import Any

from apps.organizations.structure import DEFAULT_ROLE_TEMPLATES, CustomRole


def ensure_role_templates(organization) -> list[CustomRole]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    out = []
    for tmpl in DEFAULT_ROLE_TEMPLATES:
        role, _ = CustomRole.objects.get_or_create(
            organization_id=org_id,
            slug=tmpl["slug"],
            defaults={
                "name": tmpl["name"],
                "permissions": tmpl["permissions"],
                "resource_rules": tmpl["resource_rules"],
                "is_system_template": True,
                "is_active": True,
            },
        )
        out.append(role)
    return out


def role_payload(role: CustomRole) -> dict[str, Any]:
    return {
        "id": role.id,
        "name": role.name,
        "slug": role.slug,
        "description": role.description,
        "permissions": role.permissions,
        "resource_rules": role.resource_rules,
        "is_system_template": role.is_system_template,
        "is_active": role.is_active,
    }
