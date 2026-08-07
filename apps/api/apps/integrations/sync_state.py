"""Incremental sync helpers — cursors, timestamps, checksums (NP-196)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.integrations.models import IntegrationConnection, SyncEntityState

EntityType = Literal["customers", "invoices", "payments"]


@dataclass
class IncrementalPlan:
    mode: Literal["full", "incremental"]
    since: datetime | None
    state: SyncEntityState


def get_or_create_state(connection: IntegrationConnection, entity_type: EntityType) -> SyncEntityState:
    state, _ = SyncEntityState.objects.get_or_create(
        connection=connection,
        entity_type=entity_type,
        defaults={"organization": connection.organization},
    )
    return state


def plan_incremental(
    connection: IntegrationConnection,
    entity_type: EntityType,
    *,
    force_full: bool = False,
) -> IncrementalPlan:
    state = get_or_create_state(connection, entity_type)
    if force_full or state.last_successful_sync_at is None:
        return IncrementalPlan(mode="full", since=None, state=state)
    return IncrementalPlan(mode="incremental", since=state.last_remote_update_at, state=state)


def payload_checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def checksum_unchanged(state: SyncEntityState, external_id: str, checksum: str) -> bool:
    stored = (state.checksums_json or {}).get(str(external_id))
    return bool(stored) and stored == checksum


def remember_checksum(state: SyncEntityState, external_id: str, checksum: str) -> None:
    checksums = dict(state.checksums_json or {})
    checksums[str(external_id)] = checksum
    # Cap map size to avoid unbounded growth in long-running tenants.
    if len(checksums) > 20000:
        # Drop oldest arbitrary keys (dict order is insertion order on 3.7+)
        overflow = len(checksums) - 20000
        for key in list(checksums.keys())[:overflow]:
            checksums.pop(key, None)
    state.checksums_json = checksums


def parse_remote_updated_at(raw: dict[str, Any]) -> datetime | None:
    for key in ("updated_at", "updatedAt", "modified_at", "remote_updated_at"):
        value = raw.get(key)
        if not value:
            continue
        if isinstance(value, datetime):
            return value
        parsed = parse_datetime(str(value).replace("Z", "+00:00"))
        if parsed is not None:
            return parsed
    return None


def finalize_entity_state(
    state: SyncEntityState,
    *,
    last_cursor: str = "",
    max_remote_updated_at: datetime | None = None,
    success: bool = True,
) -> SyncEntityState:
    now = timezone.now()
    state.last_cursor = last_cursor or state.last_cursor
    state.last_sync_at = now
    if success:
        state.last_successful_sync_at = now
        if max_remote_updated_at is not None:
            if (
                state.last_remote_update_at is None
                or max_remote_updated_at > state.last_remote_update_at
            ):
                state.last_remote_update_at = max_remote_updated_at
        elif state.last_remote_update_at is None:
            state.last_remote_update_at = now
    state.save()
    return state
