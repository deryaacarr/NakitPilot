"""NP-314 — data access event recording + report."""

from __future__ import annotations

from typing import Any

from apps.governance.models import DataAccessEvent


def record_access(
    organization,
    *,
    actor,
    action: str,
    resource_type: str,
    resource_id: str | int = "",
    summary: str = "",
    metadata: dict[str, Any] | None = None,
) -> DataAccessEvent:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    return DataAccessEvent.objects.create(
        organization_id=org_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        summary=(summary or "")[:255],
        metadata=metadata or {},
    )


def access_report(organization, *, limit: int = 100) -> list[dict[str, Any]]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    rows = (
        DataAccessEvent.objects.filter(organization_id=org_id)
        .select_related("actor")
        .order_by("-created_at")[:limit]
    )
    return [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "actor_email": getattr(r.actor, "email", None),
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "summary": r.summary,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
