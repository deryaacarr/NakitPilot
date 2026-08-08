from __future__ import annotations

from typing import Any

from apps.platform.models import PlatformAuditLog


def write_platform_audit(
    *,
    actor=None,
    action: str,
    entity_type: str,
    entity_id: str | int = "",
    organization=None,
    summary: str = "",
    changes: dict[str, Any] | None = None,
) -> PlatformAuditLog:
    return PlatformAuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id != "" else "",
        organization=organization,
        summary=(summary or "")[:255],
        changes=changes or {},
    )
