"""KolayBi sales invoice sync (NP-194)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.customers.models import Customer, CustomerSource
from apps.integrations.connectors.base import AccountingConnector
from apps.integrations.connectors.types import NormalizedInvoice
from apps.integrations.conversion import parse_money
from apps.integrations.models import (
    ExternalObjectMapping,
    IntegrationConnection,
    SyncError,
    SyncJob,
    SyncRecord,
    SyncRecordAction,
)
from apps.invoices.models import Invoice, InvoiceSource, InvoiceStatus, ZERO
from apps.invoices.services import recalculate_invoice_status
from apps.payments.models import PaymentAllocation
from apps.integrations.conflicts import detect_invoice_conflicts, detect_local_edited_invoice

SOURCE_BY_PROVIDER = {"kolaybi": InvoiceSource.KOLAYBI}

STATUS_MAP = {
    "draft": InvoiceStatus.DRAFT,
    "open": InvoiceStatus.OPEN,
    "unpaid": InvoiceStatus.OPEN,
    "partial": InvoiceStatus.PARTIALLY_PAID,
    "partially_paid": InvoiceStatus.PARTIALLY_PAID,
    "paid": InvoiceStatus.PAID,
    "overdue": InvoiceStatus.OVERDUE,
    "cancelled": InvoiceStatus.CANCELLED,
    "canceled": InvoiceStatus.CANCELLED,
    "deleted": InvoiceStatus.CANCELLED,
    "void": InvoiceStatus.CANCELLED,
}


def map_invoice_status(raw_status: str, *, is_cancelled: bool = False) -> str:
    if is_cancelled:
        return InvoiceStatus.CANCELLED
    key = (raw_status or "").strip().lower().replace(" ", "_").replace("-", "_")
    return STATUS_MAP.get(key, InvoiceStatus.OPEN)


def sync_invoices_for_connection(
    connection: IntegrationConnection,
    connector: AccountingConnector,
    job: SyncJob,
    *,
    force_full: bool = False,
) -> dict[str, Any]:
    source = SOURCE_BY_PROVIDER.get(connection.provider)
    if source is None:
        raise ValueError(f"Invoice sync not supported for provider={connection.provider}")

    from apps.integrations.sync_state import (
        checksum_unchanged,
        finalize_entity_state,
        parse_remote_updated_at,
        payload_checksum,
        plan_incremental,
        remember_checksum,
    )

    plan = plan_incremental(connection, "invoices", force_full=force_full)
    since = plan.since if plan.mode == "incremental" else None

    stats = {
        "pages": 0,
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "cancelled": 0,
        "payment_conflicts": 0,
        "mode": plan.mode,
        "checksum_skipped": 0,
    }
    cursor: str | None = None
    max_remote = plan.state.last_remote_update_at
    last_cursor = ""

    while True:
        page = connector.fetch_invoices(cursor=cursor, updated_since=since)
        stats["pages"] += 1
        for item in page.items:
            stats["fetched"] += 1
            checksum = payload_checksum(
                {
                    "external_id": item.external_id,
                    "number": item.number,
                    "total_amount": str(item.total_amount),
                    "status": item.status,
                    "due_date": str(item.due_date),
                    "invoice_date": str(item.invoice_date),
                    "is_cancelled": bool(item.metadata.get("is_cancelled")),
                }
            )
            if plan.mode == "incremental" and checksum_unchanged(plan.state, item.external_id, checksum):
                stats["checksum_skipped"] += 1
                stats["skipped"] += 1
                continue
            try:
                action, meta = _upsert_invoice(connection, source, item, job)
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
                if meta.get("cancelled"):
                    stats["cancelled"] += 1
                if meta.get("payment_conflict"):
                    stats["payment_conflicts"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["failed"] += 1
                from apps.integrations.conflicts import record_customer_missing_conflict

                if "Müşteri bulunamadı" in str(exc):
                    record_customer_missing_conflict(
                        connection,
                        job,
                        entity_type="invoice",
                        external_id=item.external_id,
                        external_customer_id=item.external_customer_id,
                        source_payload={
                            "number": item.number,
                            "external_customer_id": item.external_customer_id,
                        },
                    )
                SyncError.objects.create(
                    organization=connection.organization,
                    job=job,
                    code="invoice_upsert_failed",
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
        success=True,
    )
    return stats


def _local_payment_allocation_total(invoice: Invoice) -> Decimal:
    from apps.payments.models import PaymentSource

    total = (
        PaymentAllocation.objects.filter(invoice=invoice, payment__cancelled_at__isnull=True)
        .exclude(payment__source=PaymentSource.KOLAYBI)
        .aggregate(total=Sum("amount"))["total"]
    )
    return total if total is not None else ZERO


@transaction.atomic
def _upsert_invoice(
    connection: IntegrationConnection,
    source: str,
    item: NormalizedInvoice,
    job: SyncJob,
) -> tuple[str, dict[str, Any]]:
    org = connection.organization
    customer = Customer.objects.filter(
        organization=org,
        source=CustomerSource.KOLAYBI,
        external_id=item.external_customer_id,
    ).first()
    if customer is None:
        raise ValueError(f"Müşteri bulunamadı: {item.external_customer_id}")

    detect_invoice_conflicts(
        connection,
        job,
        item_number=item.number,
        item_external_id=item.external_id,
        source_payload={
            "number": item.number,
            "total_amount": str(item.total_amount),
            "status": item.status,
            "description": item.description,
        },
    )

    total = parse_money(item.total_amount, field_name="total_amount")
    subtotal = parse_money(item.subtotal_amount or ZERO, field_name="subtotal_amount")
    tax = parse_money(item.tax_amount or ZERO, field_name="tax_amount")
    currency = (item.currency or "TRY").upper()[:3]

    is_cancelled = bool(item.metadata.get("is_cancelled")) or (
        map_invoice_status(item.status) == InvoiceStatus.CANCELLED
    )
    mapped_status = map_invoice_status(item.status, is_cancelled=is_cancelled)
    meta: dict[str, Any] = {"cancelled": is_cancelled, "payment_conflict": False}

    invoice = (
        Invoice.objects.select_for_update()
        .filter(organization=org, source=source, external_id=item.external_id)
        .first()
    )
    created = invoice is None

    if created:
        invoice = Invoice(
            organization=org,
            customer=customer,
            source=source,
            external_id=item.external_id,
            number=_unique_number(org, item.number, item.external_id),
            invoice_date=item.invoice_date,
            due_date=item.due_date,
            currency=currency,
            total_amount=total,
            subtotal_amount=subtotal,
            tax_amount=tax,
            status=InvoiceStatus.CANCELLED if is_cancelled else mapped_status,
            description=item.description or "",
            cancelled_at=timezone.now() if is_cancelled else None,
            last_synced_at=timezone.now(),
        )
        try:
            invoice.save()
        except IntegrityError:
            invoice.number = _unique_number(org, f"{item.number}-{item.external_id}", item.external_id)
            invoice.save()
        action = SyncRecordAction.CREATED
    else:
        detect_local_edited_invoice(
            connection,
            job,
            invoice,
            source_description=item.description or "",
            source_payload={
                "number": item.number,
                "total_amount": str(item.total_amount),
                "description": item.description,
            },
        )
        local_alloc = _local_payment_allocation_total(invoice)
        changed: list[str] = []

        if invoice.customer_id != customer.id:
            invoice.customer = customer
            changed.append("customer")
        if invoice.invoice_date != item.invoice_date:
            invoice.invoice_date = item.invoice_date
            changed.append("invoice_date")
        if invoice.due_date != item.due_date:
            invoice.due_date = item.due_date
            changed.append("due_date")
        if invoice.currency != currency:
            invoice.currency = currency
            changed.append("currency")
        if invoice.subtotal_amount != subtotal:
            invoice.subtotal_amount = subtotal
            changed.append("subtotal_amount")
        if invoice.tax_amount != tax:
            invoice.tax_amount = tax
            changed.append("tax_amount")
        if (item.description or "") != invoice.description:
            invoice.description = item.description or ""
            changed.append("description")

        if total < local_alloc:
            meta["payment_conflict"] = True
            SyncError.objects.create(
                organization=org,
                job=job,
                code="invoice_local_payment_conflict",
                message=(
                    f"Fatura {item.external_id}: kaynak tutar ({total}) yerel ödeme "
                    f"dağıtımından ({local_alloc}) küçük; tutar güncellenmedi."
                ),
                raw_detail=item.external_id,
            )
        elif invoice.total_amount != total:
            invoice.total_amount = total
            changed.append("total_amount")

        if is_cancelled:
            if invoice.status != InvoiceStatus.CANCELLED:
                if local_alloc > ZERO:
                    meta["payment_conflict"] = True
                    SyncError.objects.create(
                        organization=org,
                        job=job,
                        code="invoice_cancel_with_local_payments",
                        message=(
                            f"Fatura {item.external_id} kaynakta iptal/silindi; yerel ödemeler "
                            f"korunarak iptal işaretlendi (dağıtım={local_alloc})."
                        ),
                        raw_detail=item.external_id,
                    )
                invoice.status = InvoiceStatus.CANCELLED
                invoice.cancelled_at = invoice.cancelled_at or timezone.now()
                changed.extend(["status", "cancelled_at"])
        else:
            if invoice.cancelled_at is not None:
                invoice.cancelled_at = None
                changed.append("cancelled_at")
            invoice.status = mapped_status
            changed.append("status")
            # Allocation-aware refresh when not draft/cancelled from source intent.
            if mapped_status not in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}:
                recalculate_invoice_status(invoice, save=False)

        invoice.last_synced_at = timezone.now()
        changed.append("last_synced_at")
        if changed:
            invoice.save(update_fields=[*dict.fromkeys([*changed, "updated_at"])])
            action = SyncRecordAction.UPDATED
        else:
            action = SyncRecordAction.SKIPPED

    ExternalObjectMapping.objects.update_or_create(
        connection=connection,
        entity_type="invoice",
        external_id=item.external_id,
        defaults={
            "organization": org,
            "internal_model": "invoices.Invoice",
            "internal_id": str(invoice.pk),
        },
    )
    SyncRecord.objects.create(
        organization=org,
        job=job,
        entity_type="invoice",
        external_id=item.external_id,
        internal_id=str(invoice.pk),
        action=action,
        payload_summary={
            "number": invoice.number,
            "status": invoice.status,
            "total_amount": str(invoice.total_amount),
            **meta,
        },
    )
    return action, meta


def _unique_number(organization, number: str, external_id: str) -> str:
    base = (number or "").strip() or f"KB-{external_id}"
    if not Invoice.objects.filter(organization=organization, number=base).exists():
        return base
    candidate = f"{base}-{external_id}"[:64]
    if not Invoice.objects.filter(organization=organization, number=candidate).exists():
        return candidate
    return f"KB-{external_id}"[:64]
