"""KolayBi payment sync (NP-195)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers.models import Customer, CustomerSource
from apps.integrations.connectors.base import AccountingConnector
from apps.integrations.connectors.types import NormalizedPayment
from apps.integrations.conversion import parse_money
from apps.integrations.models import (
    ExternalObjectMapping,
    IntegrationConnection,
    SyncError,
    SyncJob,
    SyncRecord,
    SyncRecordAction,
)
from apps.invoices.models import Invoice, InvoiceSource, InvoiceStatus
from apps.invoices.services import recalculate_invoices_after_payment
from apps.payments.models import ZERO, Payment, PaymentAllocation, PaymentMethod, PaymentSource

SOURCE_BY_PROVIDER = {"kolaybi": PaymentSource.KOLAYBI}

METHOD_MAP = {
    "cash": PaymentMethod.CASH,
    "nakit": PaymentMethod.CASH,
    "bank": PaymentMethod.BANK_TRANSFER,
    "bank_transfer": PaymentMethod.BANK_TRANSFER,
    "havale": PaymentMethod.BANK_TRANSFER,
    "eft": PaymentMethod.BANK_TRANSFER,
    "card": PaymentMethod.CREDIT_CARD,
    "credit_card": PaymentMethod.CREDIT_CARD,
    "check": PaymentMethod.CHECK,
    "cek": PaymentMethod.CHECK,
}


def map_payment_method(raw: str) -> str:
    key = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    return METHOD_MAP.get(key, PaymentMethod.OTHER if raw else PaymentMethod.BANK_TRANSFER)


def sync_payments_for_connection(
    connection: IntegrationConnection,
    connector: AccountingConnector,
    job: SyncJob,
    *,
    force_full: bool = False,
) -> dict[str, Any]:
    source = SOURCE_BY_PROVIDER.get(connection.provider)
    if source is None:
        raise ValueError(f"Payment sync not supported for provider={connection.provider}")

    from apps.integrations.sync_state import (
        checksum_unchanged,
        finalize_entity_state,
        parse_remote_updated_at,
        payload_checksum,
        plan_incremental,
        remember_checksum,
    )

    plan = plan_incremental(connection, "payments", force_full=force_full)
    since = plan.since if plan.mode == "incremental" else None

    stats = {
        "pages": 0,
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "cancelled": 0,
        "allocated": 0,
        "unallocated": 0,
        "mode": plan.mode,
        "checksum_skipped": 0,
    }
    cursor: str | None = None
    max_remote = plan.state.last_remote_update_at
    last_cursor = ""

    while True:
        page = connector.fetch_payments(cursor=cursor, updated_since=since)
        stats["pages"] += 1
        for item in page.items:
            stats["fetched"] += 1
            checksum = payload_checksum(
                {
                    "external_id": item.external_id,
                    "amount": str(item.amount),
                    "payment_date": str(item.payment_date),
                    "invoice_ids": list(item.external_invoice_ids),
                    "is_cancelled": bool(item.metadata.get("is_cancelled")),
                }
            )
            if plan.mode == "incremental" and checksum_unchanged(plan.state, item.external_id, checksum):
                stats["checksum_skipped"] += 1
                stats["skipped"] += 1
                continue
            try:
                action, meta = _upsert_payment(connection, source, item, job)
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
                if meta.get("allocated"):
                    stats["allocated"] += 1
                if meta.get("unallocated"):
                    stats["unallocated"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["failed"] += 1
                SyncError.objects.create(
                    organization=connection.organization,
                    job=job,
                    code="payment_upsert_failed",
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
    from apps.billing.usage import meter_integration_sync

    meter_integration_sync(connection.organization_id)
    return stats


@transaction.atomic
def _upsert_payment(
    connection: IntegrationConnection,
    source: str,
    item: NormalizedPayment,
    job: SyncJob,
) -> tuple[str, dict[str, Any]]:
    org = connection.organization
    customer = Customer.objects.filter(
        organization=org,
        source=CustomerSource.KOLAYBI,
        external_id=item.external_customer_id,
    ).first()
    if customer is None:
        raise ValueError(f"Ödeme müşterisi bulunamadı: {item.external_customer_id}")

    amount = parse_money(item.amount, field_name="amount")
    currency = (item.currency or "TRY").upper()[:3]
    method = map_payment_method(item.method)
    is_cancelled = bool(item.metadata.get("is_cancelled"))
    meta: dict[str, Any] = {
        "cancelled": is_cancelled,
        "allocated": False,
        "unallocated": False,
    }

    payment = (
        Payment.objects.select_for_update()
        .filter(organization=org, source=source, external_id=item.external_id)
        .first()
    )
    created = payment is None
    touched_invoice_ids: list[int] = []

    if created:
        payment = Payment(
            organization=org,
            customer=customer,
            source=source,
            external_id=item.external_id,
            payment_date=item.payment_date,
            amount=amount,
            currency=currency,
            method=method,
            reference=item.reference or "",
            notes=item.notes or "",
            unallocated_amount=amount,
            last_synced_at=timezone.now(),
        )
        if is_cancelled:
            payment.cancelled_at = timezone.now()
            payment.cancellation_reason = "KolayBi iptal/silme"
            payment.unallocated_amount = ZERO
        payment.save()
        action = SyncRecordAction.CREATED
    else:
        from apps.integrations.conflicts import detect_payment_amount_conflict

        detect_payment_amount_conflict(
            connection,
            job,
            payment,
            new_amount=amount,
            source_payload={
                "amount": str(amount),
                "payment_date": str(item.payment_date),
                "invoice_ids": list(item.external_invoice_ids),
            },
        )
        changed: list[str] = []
        if payment.customer_id != customer.id:
            payment.customer = customer
            changed.append("customer")
        if payment.payment_date != item.payment_date:
            payment.payment_date = item.payment_date
            changed.append("payment_date")
        if payment.amount != amount:
            payment.amount = amount
            changed.append("amount")
        if payment.currency != currency:
            payment.currency = currency
            changed.append("currency")
        if payment.method != method:
            payment.method = method
            changed.append("method")
        if (item.reference or "") != payment.reference:
            payment.reference = item.reference or ""
            changed.append("reference")

        if is_cancelled and not payment.is_cancelled:
            payment.cancelled_at = timezone.now()
            payment.cancellation_reason = "KolayBi iptal/silme"
            changed.extend(["cancelled_at", "cancellation_reason"])
            # Drop provider allocations on cancel.
            touched_invoice_ids = list(payment.allocations.values_list("invoice_id", flat=True))
            payment.allocations.all().delete()
            payment.unallocated_amount = ZERO
            changed.append("unallocated_amount")
        elif not is_cancelled and payment.is_cancelled:
            payment.cancelled_at = None
            payment.cancelled_by = None
            payment.cancellation_reason = ""
            changed.extend(["cancelled_at", "cancelled_by", "cancellation_reason"])

        payment.last_synced_at = timezone.now()
        changed.append("last_synced_at")
        payment.save(update_fields=[*dict.fromkeys([*changed, "updated_at"])])
        action = SyncRecordAction.UPDATED if changed else SyncRecordAction.SKIPPED

    if not is_cancelled:
        alloc_meta = _sync_allocations(payment, item.external_invoice_ids)
        meta.update(alloc_meta)
        touched_invoice_ids = list(
            set(touched_invoice_ids) | set(payment.allocations.values_list("invoice_id", flat=True))
        )
    else:
        meta["cancelled"] = True

    if touched_invoice_ids:
        recalculate_invoices_after_payment(touched_invoice_ids)

    ExternalObjectMapping.objects.update_or_create(
        connection=connection,
        entity_type="payment",
        external_id=item.external_id,
        defaults={
            "organization": org,
            "internal_model": "payments.Payment",
            "internal_id": str(payment.pk),
        },
    )
    SyncRecord.objects.create(
        organization=org,
        job=job,
        entity_type="payment",
        external_id=item.external_id,
        internal_id=str(payment.pk),
        action=action,
        payload_summary={
            "amount": str(payment.amount),
            "unallocated_amount": str(payment.unallocated_amount),
            **meta,
        },
    )
    return action, meta


def _sync_allocations(payment: Payment, external_invoice_ids: tuple[str, ...]) -> dict[str, Any]:
    """Create allocations when invoices resolve; otherwise leave unallocated."""
    org = payment.organization
    # Replace only provider-managed allocations for this payment.
    payment.allocations.all().delete()

    if not external_invoice_ids:
        payment.refresh_unallocated(save=True)
        return {"allocated": False, "unallocated": payment.unallocated_amount > ZERO}

    remaining = payment.amount
    allocated_any = False
    for ext_id in external_invoice_ids:
        if remaining <= ZERO:
            break
        invoice = Invoice.objects.filter(
            organization=org,
            source=InvoiceSource.KOLAYBI,
            external_id=str(ext_id),
        ).first()
        if invoice is None:
            continue
        if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}:
            continue
        if invoice.currency != payment.currency:
            continue
        if invoice.customer_id != payment.customer_id:
            continue

        due = invoice.remaining_amount()
        # remaining_amount after we deleted this payment's allocations already.
        if due <= ZERO:
            continue
        take = due if due <= remaining else remaining
        take = parse_money(take)
        if take <= ZERO:
            continue
        PaymentAllocation.objects.create(
            organization=org,
            payment=payment,
            invoice=invoice,
            amount=take,
        )
        remaining -= take
        allocated_any = True

    payment.refresh_unallocated(save=True)
    return {
        "allocated": allocated_any,
        "unallocated": payment.unallocated_amount > ZERO,
    }
