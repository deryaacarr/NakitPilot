"""Sync conflict detection and resolution (NP-197)."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers.models import Customer, CustomerSource
from apps.integrations.models import (
    IntegrationConnection,
    SyncConflict,
    SyncConflictResolution,
    SyncConflictStatus,
    SyncConflictType,
    SyncJob,
)
from apps.invoices.models import Invoice, InvoiceSource
from apps.payments.models import Payment, PaymentSource


class ConflictResolutionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def open_conflict(
    connection: IntegrationConnection,
    *,
    job: SyncJob | None,
    entity_type: str,
    conflict_type: str,
    external_id: str = "",
    internal_model: str = "",
    internal_id: str = "",
    message: str = "",
    source_payload: dict | None = None,
    local_snapshot: dict | None = None,
) -> SyncConflict:
    existing = SyncConflict.objects.filter(
        connection=connection,
        entity_type=entity_type,
        conflict_type=conflict_type,
        external_id=external_id or "",
        status=SyncConflictStatus.OPEN,
    ).first()
    if existing:
        existing.message = message or existing.message
        existing.source_payload = source_payload or existing.source_payload
        existing.local_snapshot = local_snapshot or existing.local_snapshot
        existing.job = job or existing.job
        existing.save(
            update_fields=["message", "source_payload", "local_snapshot", "job", "updated_at"]
        )
        return existing
    return SyncConflict.objects.create(
        organization=connection.organization,
        connection=connection,
        job=job,
        entity_type=entity_type,
        conflict_type=conflict_type,
        external_id=external_id or "",
        internal_model=internal_model or "",
        internal_id=internal_id or "",
        message=message or "",
        source_payload=source_payload or {},
        local_snapshot=local_snapshot or {},
    )


def record_customer_missing_conflict(
    connection: IntegrationConnection,
    job: SyncJob,
    *,
    entity_type: str,
    external_id: str,
    external_customer_id: str,
    source_payload: dict,
) -> SyncConflict:
    return open_conflict(
        connection,
        job=job,
        entity_type=entity_type,
        conflict_type=SyncConflictType.CUSTOMER_MERGED_OR_DELETED,
        external_id=external_id,
        message=f"Kaynak müşteri bulunamadı / birleştirilmiş olabilir: {external_customer_id}",
        source_payload=source_payload,
    )


def detect_invoice_conflicts(
    connection: IntegrationConnection,
    job: SyncJob,
    *,
    item_number: str,
    item_external_id: str,
    source_payload: dict,
) -> SyncConflict | None:
    """Same invoice number exists as MANUAL while importing from API."""
    manual = (
        Invoice.objects.filter(
            organization=connection.organization,
            source=InvoiceSource.MANUAL,
            number=item_number,
        )
        .exclude(external_id=item_external_id)
        .first()
    )
    if not manual:
        return None
    return open_conflict(
        connection,
        job=job,
        entity_type="invoice",
        conflict_type=SyncConflictType.DUPLICATE_MANUAL_API,
        external_id=item_external_id,
        internal_model="invoices.Invoice",
        internal_id=str(manual.pk),
        message=f"Aynı fatura numarası yerelde manuel kayıtlı: {item_number}",
        source_payload=source_payload,
        local_snapshot={
            "id": manual.pk,
            "number": manual.number,
            "total_amount": str(manual.total_amount),
            "status": manual.status,
            "source": manual.source,
        },
    )


def detect_local_edited_invoice(
    connection: IntegrationConnection,
    job: SyncJob,
    invoice: Invoice,
    *,
    source_description: str,
    source_payload: dict,
) -> SyncConflict | None:
    """KolayBi invoice description diverged after local edit."""
    if invoice.source != InvoiceSource.KOLAYBI:
        return None
    local_desc = (invoice.description or "").strip()
    remote_desc = (source_description or "").strip()
    if local_desc and remote_desc and local_desc != remote_desc:
        # Prefer conflict when notes/description were locally customized.
        if invoice.notes.strip():
            return open_conflict(
                connection,
                job=job,
                entity_type="invoice",
                conflict_type=SyncConflictType.LOCAL_EDITED,
                external_id=invoice.external_id,
                internal_model="invoices.Invoice",
                internal_id=str(invoice.pk),
                message="KolayBi faturası yerelde değiştirilmiş görünüyor.",
                source_payload=source_payload,
                local_snapshot={
                    "description": invoice.description,
                    "notes": invoice.notes,
                    "total_amount": str(invoice.total_amount),
                },
            )
    return None


def detect_payment_amount_conflict(
    connection: IntegrationConnection,
    job: SyncJob,
    payment: Payment,
    *,
    new_amount,
    source_payload: dict,
) -> SyncConflict | None:
    if payment.amount == new_amount:
        return None
    if payment.source != PaymentSource.KOLAYBI:
        return None
    return open_conflict(
        connection,
        job=job,
        entity_type="payment",
        conflict_type=SyncConflictType.PAYMENT_AMOUNT_CHANGED,
        external_id=payment.external_id,
        internal_model="payments.Payment",
        internal_id=str(payment.pk),
        message=f"Ödeme tutarı kaynakta değişti: {payment.amount} → {new_amount}",
        source_payload=source_payload,
        local_snapshot={
            "amount": str(payment.amount),
            "unallocated_amount": str(payment.unallocated_amount),
            "allocations": list(
                payment.allocations.values("invoice_id", "amount")
            ),
        },
    )


@transaction.atomic
def resolve_conflict(
    conflict: SyncConflict,
    *,
    resolution: str,
    user=None,
    field: str = "",
) -> SyncConflict:
    if conflict.status == SyncConflictStatus.RESOLVED:
        raise ConflictResolutionError("Çakışma zaten çözülmüş.")
    if resolution not in SyncConflictResolution.values:
        raise ConflictResolutionError("Geçersiz çözüm seçeneği.")

    detail: dict[str, Any] = dict(conflict.resolution_detail or {})

    if resolution == SyncConflictResolution.USE_SOURCE:
        _apply_use_source(conflict)
    elif resolution == SyncConflictResolution.KEEP_LOCAL:
        detail["kept_local"] = True
    elif resolution == SyncConflictResolution.MERGE:
        _apply_merge(conflict)
        detail["merged"] = True
    elif resolution == SyncConflictResolution.SKIP_FIELD_FOREVER:
        if not field:
            raise ConflictResolutionError("skip_field_forever için field gerekli.")
        _apply_skip_field(conflict, field)
        skipped = list(detail.get("skipped_fields") or [])
        if field not in skipped:
            skipped.append(field)
        detail["skipped_fields"] = skipped

    conflict.resolution = resolution
    conflict.resolution_detail = detail
    conflict.status = SyncConflictStatus.RESOLVED
    conflict.resolved_at = timezone.now()
    conflict.resolved_by = user
    conflict.save(
        update_fields=[
            "resolution",
            "resolution_detail",
            "status",
            "resolved_at",
            "resolved_by",
            "updated_at",
        ]
    )
    return conflict


def _apply_use_source(conflict: SyncConflict) -> None:
    payload = conflict.source_payload or {}
    if conflict.entity_type == "invoice" and conflict.internal_id:
        invoice = Invoice.objects.filter(pk=conflict.internal_id).first()
        if invoice and payload.get("total_amount") is not None:
            from apps.integrations.conversion import parse_money

            invoice.total_amount = parse_money(payload["total_amount"])
            if payload.get("description") is not None:
                invoice.description = str(payload.get("description") or "")
            invoice.save()
    elif conflict.entity_type == "payment" and conflict.internal_id:
        payment = Payment.objects.filter(pk=conflict.internal_id).first()
        if payment and payload.get("amount") is not None:
            from apps.integrations.conversion import parse_money

            payment.amount = parse_money(payload["amount"])
            payment.refresh_unallocated(save=True)
            payment.save()


def _apply_merge(conflict: SyncConflict) -> None:
    """Attach external_id onto the local MANUAL invoice and mark as KOLAYBI-linked."""
    if conflict.conflict_type != SyncConflictType.DUPLICATE_MANUAL_API:
        return
    if not conflict.internal_id or not conflict.external_id:
        return
    invoice = Invoice.objects.filter(pk=conflict.internal_id).first()
    if not invoice:
        return
    invoice.source = InvoiceSource.KOLAYBI
    invoice.external_id = conflict.external_id
    invoice.save(update_fields=["source", "external_id", "updated_at"])


def _apply_skip_field(conflict: SyncConflict, field: str) -> None:
    if conflict.entity_type == "customer" and conflict.internal_id:
        customer = Customer.objects.filter(pk=conflict.internal_id).first()
        if customer:
            overrides = list(customer.local_field_overrides or [])
            if field not in overrides:
                overrides.append(field)
            customer.local_field_overrides = overrides
            customer.save(update_fields=["local_field_overrides", "updated_at"])
    elif conflict.entity_type == "invoice" and conflict.internal_id:
        invoice = Invoice.objects.filter(pk=conflict.internal_id).first()
        if invoice and field == "description":
            # Store skip preference on connection settings.
            settings = dict(conflict.connection.settings_json or {})
            skipped = dict(settings.get("skip_fields") or {})
            key = f"invoice:{conflict.external_id}"
            fields = list(skipped.get(key) or [])
            if field not in fields:
                fields.append(field)
            skipped[key] = fields
            settings["skip_fields"] = skipped
            conflict.connection.settings_json = settings
            conflict.connection.save(update_fields=["settings_json", "updated_at"])
