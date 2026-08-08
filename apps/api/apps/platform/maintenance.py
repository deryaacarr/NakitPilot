"""NP-363 — maintenance / read-only evaluation."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.platform.models import MaintenanceMode, MaintenanceScope, MaintenanceWindow

# URL path prefix → module key
MODULE_PATH_PREFIXES: list[tuple[str, str]] = [
    ("/api/collection-tasks/", "collections"),
    ("/api/payment-promises/", "collections"),
    ("/api/disputes/", "collections"),
    ("/api/legal/", "legal"),
    ("/api/billing/", "billing"),
    ("/api/payments/", "payments"),
    ("/api/invoices/", "invoices"),
    ("/api/customers/", "customers"),
    ("/api/workflows/", "workflows"),
    ("/api/integrations/", "integrations"),
    ("/api/forecast/", "forecast"),
    ("/api/messaging/", "messaging"),
    ("/api/message-templates/", "messaging"),
]


def path_module(path: str) -> str | None:
    for prefix, module in MODULE_PATH_PREFIXES:
        if path.startswith(prefix):
            return module
    return None


def active_windows(*, now=None) -> list[MaintenanceWindow]:
    now = now or timezone.now()
    rows = list(
        MaintenanceWindow.objects.filter(is_active=True)
        .select_related("organization")
        .order_by("-starts_at")
    )
    return [w for w in rows if w.is_in_effect(now=now)]


def matching_windows(
    *,
    organization=None,
    module: str | None = None,
    now=None,
) -> list[MaintenanceWindow]:
    matches: list[MaintenanceWindow] = []
    for window in active_windows(now=now):
        if window.scope == MaintenanceScope.GLOBAL:
            matches.append(window)
        elif window.scope == MaintenanceScope.ORGANIZATION:
            if organization is not None and window.organization_id == organization.pk:
                matches.append(window)
        elif window.scope == MaintenanceScope.MODULE:
            if module and window.module and window.module.lower() == module.lower():
                # Optional org filter on module windows
                if window.organization_id and (
                    organization is None or window.organization_id != organization.pk
                ):
                    continue
                matches.append(window)
    return matches


def maintenance_state(
    *,
    organization=None,
    path: str = "",
    now=None,
) -> dict[str, Any] | None:
    module = path_module(path) if path else None
    matches = matching_windows(organization=organization, module=module, now=now)
    if not matches:
        return None
    # Prefer FULL over READ_ONLY
    full = next((m for m in matches if m.mode == MaintenanceMode.FULL), None)
    chosen = full or matches[0]
    return {
        "id": chosen.id,
        "scope": chosen.scope,
        "mode": chosen.mode,
        "module": chosen.module,
        "organization_id": chosen.organization_id,
        "message": chosen.message
        or "Sistem bakımda. Lütfen daha sonra tekrar deneyin.",
    }
