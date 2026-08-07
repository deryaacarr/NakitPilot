"""Connection actions for wizard flow (NP-192)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.integrations.connectors import build
from apps.integrations.models import (
    ConnectionStatus,
    IntegrationConnection,
    SyncFrequency,
    SyncJob,
    SyncJobStatus,
)
from apps.integrations.services import get_connection_credentials


class ConnectionActionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _bound_connector(connection: IntegrationConnection):
    try:
        credentials = get_connection_credentials(connection)
    except Exception as exc:  # noqa: BLE001 — map to action error
        raise ConnectionActionError("Bu bağlantı için kimlik bilgisi yok.", status_code=400) from exc
    settings = dict(connection.settings_json or {})
    if connection.external_company_id:
        settings.setdefault("external_company_id", connection.external_company_id)
    return build(
        connection.provider,
        credentials=credentials,
        settings=settings,
    )


def test_connection(connection: IntegrationConnection) -> dict[str, Any]:
    connector = _bound_connector(connection)
    result = connector.test_connection()
    ok = bool(result.get("ok"))
    if ok:
        connection.last_error = ""
        if connection.status == ConnectionStatus.ERROR:
            connection.status = ConnectionStatus.CONNECTED
        connection.save(update_fields=["last_error", "status", "updated_at"])
    else:
        message = str(result.get("message") or "Bağlantı testi başarısız.")
        connection.last_error = message
        connection.status = ConnectionStatus.ERROR
        connection.save(update_fields=["last_error", "status", "updated_at"])
    return result


def list_companies(connection: IntegrationConnection) -> list[dict[str, str]]:
    connector = _bound_connector(connection)
    try:
        page = connector.fetch_companies()
    except Exception as exc:  # noqa: BLE001
        connection.last_error = str(exc)
        connection.status = ConnectionStatus.ERROR
        connection.save(update_fields=["last_error", "status", "updated_at"])
        raise ConnectionActionError(str(exc), status_code=502) from exc
    return [
        {
            "external_id": item.external_id,
            "name": item.name,
            "tax_number": item.tax_number,
        }
        for item in page.items
    ]


@transaction.atomic
def select_company(
    connection: IntegrationConnection,
    *,
    external_company_id: str,
    external_company_name: str = "",
) -> IntegrationConnection:
    company_id = (external_company_id or "").strip()
    if not company_id:
        raise ConnectionActionError("Şirket seçimi zorunlu.")
    name = (external_company_name or "").strip()
    if not name:
        # Resolve name from provider list when possible.
        for company in list_companies(connection):
            if company["external_id"] == company_id:
                name = company["name"]
                break
    connection.external_company_id = company_id
    connection.external_company_name = name or company_id
    connection.status = ConnectionStatus.CONNECTED
    connection.last_error = ""
    connection.save(
        update_fields=[
            "external_company_id",
            "external_company_name",
            "status",
            "last_error",
            "updated_at",
        ]
    )
    return connection


def compute_next_sync_at(frequency: str, *, from_time=None):
    now = from_time or timezone.now()
    if frequency == SyncFrequency.HOURLY:
        return now + timedelta(hours=1)
    if frequency == SyncFrequency.DAILY:
        return now + timedelta(days=1)
    return None


@transaction.atomic
def update_sync_settings(
    connection: IntegrationConnection,
    *,
    sync_frequency: str,
    settings_json: dict[str, Any] | None = None,
) -> IntegrationConnection:
    if sync_frequency not in SyncFrequency.values:
        raise ConnectionActionError("Geçersiz senkronizasyon sıklığı.")
    connection.sync_frequency = sync_frequency
    connection.next_sync_at = compute_next_sync_at(sync_frequency)
    update_fields = ["sync_frequency", "next_sync_at", "updated_at"]
    if settings_json is not None:
        if not isinstance(settings_json, dict):
            raise ConnectionActionError("settings_json bir nesne olmalı.")
        connection.settings_json = settings_json
        update_fields.append("settings_json")
    connection.save(update_fields=update_fields)
    return connection


@transaction.atomic
def start_sync(
    connection: IntegrationConnection,
    *,
    job_type: str = "manual",
) -> SyncJob:
    if not connection.external_company_id:
        raise ConnectionActionError("Önce bir KolayBi şirketi seçin.")
    if not connection_has_credentials_safe(connection):
        raise ConnectionActionError("Kimlik bilgisi eksik.")

    force_full = job_type in {"initial", "full"}
    job = SyncJob.objects.create(
        organization=connection.organization,
        connection=connection,
        job_type=job_type or "manual",
        status=SyncJobStatus.PENDING,
    )
    now = timezone.now()
    job.status = SyncJobStatus.RUNNING
    job.started_at = now
    job.save(update_fields=["status", "started_at", "updated_at"])

    import time

    t0 = time.perf_counter()
    rate_limit = {"limited": False, "remaining": None, "reset_at": None, "message": ""}

    try:
        connector = _bound_connector(connection)
        probe = connector.test_connection()
        if not probe.get("ok"):
            raise ConnectionActionError(str(probe.get("message") or "Senkronizasyon öncesi test başarısız."))

        from apps.integrations.sync_customers import sync_customers_for_connection
        from apps.integrations.sync_invoices import sync_invoices_for_connection
        from apps.integrations.sync_payments import sync_payments_for_connection

        customer_stats = sync_customers_for_connection(
            connection, connector, job, force_full=force_full
        )
        invoice_stats = sync_invoices_for_connection(
            connection, connector, job, force_full=force_full
        )
        payment_stats = sync_payments_for_connection(
            connection, connector, job, force_full=force_full
        )

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        job.status = SyncJobStatus.COMPLETED
        job.finished_at = timezone.now()
        job.stats_json = {
            "mode": "full" if force_full else "incremental",
            "customers": customer_stats,
            "invoices": invoice_stats,
            "payments": payment_stats,
            "api_duration_ms": elapsed_ms,
            "rate_limit": rate_limit,
        }
        job.error_message = ""
        job.save(update_fields=["status", "finished_at", "stats_json", "error_message", "updated_at"])

        connection.last_sync_at = job.finished_at
        connection.last_successful_sync_at = job.finished_at
        connection.last_error = ""
        connection.status = ConnectionStatus.CONNECTED
        connection.next_sync_at = compute_next_sync_at(connection.sync_frequency, from_time=job.finished_at)
        connection.save(
            update_fields=[
                "last_sync_at",
                "last_successful_sync_at",
                "last_error",
                "status",
                "next_sync_at",
                "updated_at",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "429" in message or "rate limit" in message.lower():
            rate_limit = {
                "limited": True,
                "remaining": 0,
                "reset_at": None,
                "message": message[:300],
            }
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        job.status = SyncJobStatus.FAILED
        job.finished_at = timezone.now()
        job.error_message = message
        job.stats_json = {
            **(job.stats_json or {}),
            "api_duration_ms": elapsed_ms,
            "rate_limit": rate_limit,
        }
        job.save(
            update_fields=["status", "finished_at", "error_message", "stats_json", "updated_at"]
        )
        connection.last_sync_at = job.finished_at
        connection.last_error = message
        connection.status = ConnectionStatus.ERROR
        connection.save(update_fields=["last_sync_at", "last_error", "status", "updated_at"])
        raise ConnectionActionError(message, status_code=502) from exc

    return job


def connection_has_credentials_safe(connection: IntegrationConnection) -> bool:
    from apps.integrations.services import connection_has_credentials

    return connection_has_credentials(connection)
