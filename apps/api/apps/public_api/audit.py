"""Audit helpers for public API writes (NP-201)."""

from __future__ import annotations

from typing import Any

from apps.audit.models import write_audit_log
from apps.organizations.tenancy import get_request_organization


def audit_public_write(
    request,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int,
    summary: str = "",
    changes: dict[str, Any] | None = None,
):
    organization = get_request_organization(request)
    api_key = getattr(request, "auth", None)
    payload = dict(changes or {})
    payload["via"] = "api_v1"
    if api_key is not None and getattr(api_key, "pk", None) is not None:
        payload["api_key_id"] = api_key.pk
        payload["api_key_prefix"] = getattr(api_key, "display_prefix", "")
    return write_audit_log(
        organization=organization,
        actor=getattr(request, "user", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        changes=payload,
    )
