"""Upsert customers from accounting connectors (NP-193 / NP-196)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers.field_ownership import (
    KOLAYBI_MANAGED_CUSTOMER_FIELDS,
    SYNC_ALWAYS_CUSTOMER_FIELDS,
)
from apps.customers.models import Customer, CustomerSource
from apps.integrations.connectors.base import AccountingConnector
from apps.integrations.connectors.types import NormalizedCustomer
from apps.integrations.models import (
    ExternalObjectMapping,
    IntegrationConnection,
    SyncError,
    SyncJob,
    SyncRecord,
    SyncRecordAction,
)
from apps.integrations.sync_state import (
    checksum_unchanged,
    finalize_entity_state,
    parse_remote_updated_at,
    payload_checksum,
    plan_incremental,
    remember_checksum,
)


SOURCE_BY_PROVIDER = {
    "kolaybi": CustomerSource.KOLAYBI,
}


def sync_customers_for_connection(
    connection: IntegrationConnection,
    connector: AccountingConnector,
    job: SyncJob,
    *,
    force_full: bool = False,
) -> dict[str, Any]:
    source = SOURCE_BY_PROVIDER.get(connection.provider)
    if source is None:
        raise ValueError(f"Customer sync not supported for provider={connection.provider}")

    plan = plan_incremental(connection, "customers", force_full=force_full)
    since = plan.since if plan.mode == "incremental" else None

    stats = {
        "pages": 0,
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "inactive": 0,
        "mode": plan.mode,
        "checksum_skipped": 0,
    }
    cursor: str | None = None
    max_remote = plan.state.last_remote_update_at
    last_cursor = ""

    while True:
        page = connector.fetch_customers(cursor=cursor, updated_since=since)
        stats["pages"] += 1
        for item in page.items:
            stats["fetched"] += 1
            checksum = payload_checksum(
                {
                    "external_id": item.external_id,
                    "name": item.name,
                    "tax_number": item.tax_number,
                    "email": item.email,
                    "phone": item.phone,
                    "is_active": item.is_active,
                    "code": item.code,
                }
            )
            if plan.mode == "incremental" and checksum_unchanged(plan.state, item.external_id, checksum):
                stats["checksum_skipped"] += 1
                stats["skipped"] += 1
                continue
            try:
                action = _upsert_customer(connection, source, item, job)
                remember_checksum(plan.state, item.external_id, checksum)
                remote_ts = parse_remote_updated_at(item.metadata or {})
                if remote_ts and (max_remote is None or remote_ts > max_remote):
                    max_remote = remote_ts
                if action == SyncRecordAction.CREATED:
                    stats["created"] += 1
                elif action == SyncRecordAction.UPDATED:
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
                if not item.is_active:
                    stats["inactive"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["failed"] += 1
                SyncError.objects.create(
                    organization=connection.organization,
                    job=job,
                    code="customer_upsert_failed",
                    message=str(exc),
                    raw_detail=item.external_id,
                )
        last_cursor = page.next_cursor or last_cursor or (cursor or "")
        if not page.has_more:
            break
        cursor = page.next_cursor

    finalize_entity_state(
        plan.state,
        last_cursor=last_cursor or "",
        max_remote_updated_at=max_remote,
        success=stats["failed"] == 0 or stats["created"] + stats["updated"] > 0,
    )
    return stats


@transaction.atomic
def _upsert_customer(
    connection: IntegrationConnection,
    source: str,
    item: NormalizedCustomer,
    job: SyncJob,
) -> str:
    org = connection.organization
    overrides = set()
    customer = (
        Customer.objects.select_for_update()
        .filter(organization=org, source=source, external_id=item.external_id)
        .first()
    )
    created = customer is None
    if created:
        customer = Customer(
            organization=org,
            source=source,
            external_id=item.external_id,
            name=item.name,
        )
    else:
        overrides = set(customer.local_field_overrides or [])

    changed_fields: list[str] = []

    def set_if(field: str, value: Any) -> None:
        nonlocal customer
        if field in KOLAYBI_MANAGED_CUSTOMER_FIELDS and field in overrides:
            return
        if field in KOLAYBI_MANAGED_CUSTOMER_FIELDS or field in SYNC_ALWAYS_CUSTOMER_FIELDS:
            current = getattr(customer, field)
            if current != value:
                setattr(customer, field, value)
                changed_fields.append(field)

    set_if("name", item.name)
    set_if("tax_number", item.tax_number or "")
    set_if("email", (item.email or "").strip().lower())
    set_if("phone", item.phone or "")
    set_if("is_active", bool(item.is_active))
    if item.code:
        set_if("code", item.code)

    customer.last_synced_at = timezone.now()
    changed_fields.append("last_synced_at")

    if created:
        customer.save()
        action = SyncRecordAction.CREATED
    elif changed_fields:
        customer.save(update_fields=[*dict.fromkeys(changed_fields), "updated_at"])
        action = SyncRecordAction.UPDATED
    else:
        action = SyncRecordAction.SKIPPED

    ExternalObjectMapping.objects.update_or_create(
        connection=connection,
        entity_type="customer",
        external_id=item.external_id,
        defaults={
            "organization": org,
            "internal_model": "customers.Customer",
            "internal_id": str(customer.pk),
        },
    )

    SyncRecord.objects.create(
        organization=org,
        job=job,
        entity_type="customer",
        external_id=item.external_id,
        internal_id=str(customer.pk),
        action=action,
        payload_summary={
            "name": item.name,
            "is_active": item.is_active,
            "overrides_honored": sorted(overrides & KOLAYBI_MANAGED_CUSTOMER_FIELDS),
        },
    )
    return action
