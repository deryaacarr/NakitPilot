"""NP-184 — liveness / readiness probes."""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views import View


def _check_postgres() -> dict:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


def _check_redis() -> dict:
    url = os.getenv("REDIS_URL") or getattr(settings, "REDIS_URL", "") or ""
    if not url:
        return {"ok": False, "error": "REDIS_URL_unset"}
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        pong = client.ping()
        return {"ok": bool(pong)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


def _check_storage() -> dict:
    """PRIVATE_UPLOAD_ROOT must exist and be writable (NP-152 / NP-184)."""
    root = Path(getattr(settings, "PRIVATE_UPLOAD_ROOT", settings.BASE_DIR / "private_uploads"))
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"ok": True, "path": str(root)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


class LiveView(View):
    """GET /api/health/live — process is up (no dependency checks)."""

    def get(self, request):
        return JsonResponse({"status": "live", "service": "nakitpilot-api"})


class ReadyView(View):
    """GET /api/health/ready — PostgreSQL, Redis, storage."""

    def get(self, request):
        checks = {
            "postgres": _check_postgres(),
            "redis": _check_redis(),
            "storage": _check_storage(),
        }
        ready = all(item.get("ok") for item in checks.values())
        payload = {"status": "ready" if ready else "not_ready", "checks": checks}
        return JsonResponse(payload, status=200 if ready else 503)
