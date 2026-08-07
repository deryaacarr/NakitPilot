"""Integration monitoring aggregates (NP-198)."""

from __future__ import annotations

from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.integrations.models import (
    IntegrationConnection,
    SyncConflict,
    SyncConflictStatus,
    SyncEntityState,
    SyncJob,
    SyncJobStatus,
)


def build_monitoring_payload(connection: IntegrationConnection) -> dict[str, Any]:
    latest = (
        SyncJob.objects.filter(connection=connection)
        .order_by("-created_at")
        .first()
    )
    open_conflicts = SyncConflict.objects.filter(
        connection=connection,
        status=SyncConflictStatus.OPEN,
    ).count()

    entity_states = []
    for state in SyncEntityState.objects.filter(connection=connection).order_by("entity_type"):
        entity_states.append(
            {
                "entity_type": state.entity_type,
                "last_cursor": state.last_cursor,
                "last_remote_update_at": state.last_remote_update_at,
                "last_sync_at": state.last_sync_at,
                "last_successful_sync_at": state.last_successful_sync_at,
                "checksum_count": len(state.checksums_json or {}),
            }
        )

    stats = (latest.stats_json if latest else {}) or {}
    customers = stats.get("customers") or {}
    invoices = stats.get("invoices") or {}
    payments = stats.get("payments") or {}

    def sum_key(key: str) -> int:
        return int(customers.get(key, 0) or 0) + int(invoices.get(key, 0) or 0) + int(
            payments.get(key, 0) or 0
        )

    duration_ms = stats.get("api_duration_ms")
    rate_limit = stats.get("rate_limit") or {
        "limited": False,
        "remaining": None,
        "reset_at": None,
        "message": "",
    }

    finished = latest.finished_at if latest else None
    started = latest.started_at if latest else None
    last_duration_ms = None
    if finished and started:
        last_duration_ms = int((finished - started).total_seconds() * 1000)

    return {
        "connection_id": connection.id,
        "status": connection.status,
        "last_sync_at": connection.last_sync_at,
        "last_successful_sync_at": connection.last_successful_sync_at,
        "last_error": connection.last_error,
        "open_conflicts": open_conflicts,
        "metrics": {
            "fetched": sum_key("fetched"),
            "created": sum_key("created"),
            "updated": sum_key("updated"),
            "skipped": sum_key("skipped") + sum_key("checksum_skipped"),
            "failed": sum_key("failed"),
            "api_duration_ms": duration_ms if duration_ms is not None else last_duration_ms,
            "rate_limit": rate_limit,
            "last_sync_duration_ms": last_duration_ms,
        },
        "breakdown": {
            "customers": customers,
            "invoices": invoices,
            "payments": payments,
        },
        "entity_states": entity_states,
        "latest_job": (
            {
                "id": latest.id,
                "job_type": latest.job_type,
                "status": latest.status,
                "started_at": latest.started_at,
                "finished_at": latest.finished_at,
                "error_message": latest.error_message,
            }
            if latest
            else None
        ),
    }
