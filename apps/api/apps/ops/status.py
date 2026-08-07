"""NP-335 — status page components."""

from __future__ import annotations

from typing import Any

from apps.ops.models import StatusComponent, StatusComponentCode, StatusState

DEFAULT_COMPONENTS = [
    (StatusComponentCode.WEB, "Web uygulaması"),
    (StatusComponentCode.API, "API"),
    (StatusComponentCode.INTEGRATIONS, "Entegrasyonlar"),
    (StatusComponentCode.EMAIL, "E-posta"),
    (StatusComponentCode.WEBHOOK, "Webhook"),
    (StatusComponentCode.FILE_UPLOAD, "Dosya yükleme"),
    (StatusComponentCode.REPORTING, "Raporlama"),
]


def ensure_components() -> list[StatusComponent]:
    out = []
    for code, name in DEFAULT_COMPONENTS:
        obj, _ = StatusComponent.objects.get_or_create(
            code=code,
            defaults={"name": name, "state": StatusState.OPERATIONAL},
        )
        out.append(obj)
    return out


def status_payload() -> dict[str, Any]:
    comps = ensure_components()
    # Probe API readiness lightly
    api_state = StatusState.OPERATIONAL
    try:
        from django.db import connection

        connection.ensure_connection()
    except Exception:  # noqa: BLE001
        api_state = StatusState.MAJOR_OUTAGE
        StatusComponent.objects.filter(code=StatusComponentCode.API).update(
            state=api_state, message="Veritabanı bağlantısı yok"
        )

    results = []
    overall = StatusState.OPERATIONAL
    rank = {
        StatusState.OPERATIONAL: 0,
        StatusState.DEGRADED: 1,
        StatusState.PARTIAL_OUTAGE: 2,
        StatusState.MAJOR_OUTAGE: 3,
    }
    for c in StatusComponent.objects.all():
        results.append(
            {
                "code": c.code,
                "name": c.name,
                "state": c.state,
                "message": c.message,
                "updated_at": c.updated_at.isoformat(),
            }
        )
        if rank.get(c.state, 0) > rank.get(overall, 0):
            overall = c.state
    return {"overall": overall, "components": results}
