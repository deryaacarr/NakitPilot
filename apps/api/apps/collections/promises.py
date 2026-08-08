"""PaymentPromise CRUD, validation, status (NP-090–094)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import write_audit_log
from apps.collections.models import (
    CollectionActivity,
    CollectionActivityType,
    CollectionTask,
    CollectionTaskSource,
    CollectionTaskStatus,
    CollectionTaskType,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.notifications.models import AlertSeverity, create_dashboard_alert
from apps.payments.models import ZERO, Payment
from apps.risk.triggers import bump_customer_risk

CLOSED_INVOICE_STATUSES = {
    InvoiceStatus.PAID,
    InvoiceStatus.CANCELLED,
    InvoiceStatus.DRAFT,
}


class PromiseValidationError(Exception):
    def __init__(self, message: str, code: str = "invalid_promise"):
        super().__init__(message)
        self.message = message
        self.code = code


def paid_toward_promise(promise: PaymentPromise) -> Decimal:
    """
    Payments attributable to this promise (MVP FIFO):
    Active customer+currency payments in a date window, minus amounts already
    claimed by earlier promises (promised_date, id).
    """
    created_date = (
        timezone.localdate(promise.created_at) if promise.created_at else promise.promised_date
    )
    window_start = min(created_date, promise.promised_date) - timedelta(days=7)
    total_paid = (
        Payment.objects.filter(
            customer_id=promise.customer_id,
            currency=promise.currency,
            cancelled_at__isnull=True,
            payment_date__gte=window_start,
        ).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )
    total_paid = Decimal(str(total_paid))

    earlier = (
        PaymentPromise.objects.filter(
            customer_id=promise.customer_id,
            currency=promise.currency,
        )
        .exclude(status=PaymentPromiseStatus.CANCELLED)
        .exclude(pk=promise.pk)
        .filter(
            models.Q(promised_date__lt=promise.promised_date)
            | models.Q(promised_date=promise.promised_date, id__lt=promise.id)
        )
    )
    claimed = ZERO
    for other in earlier:
        claimed += min(other.amount, total_paid - claimed)
        if claimed >= total_paid:
            break

    remaining = total_paid - claimed
    if remaining < ZERO:
        return ZERO
    return remaining


def compute_promise_status(
    promise: PaymentPromise,
    *,
    as_of: date | None = None,
    paid: Decimal | None = None,
) -> str:
    """NP-092 status rules (CANCELLED left unchanged)."""
    if promise.status == PaymentPromiseStatus.CANCELLED:
        return PaymentPromiseStatus.CANCELLED

    today = as_of or timezone.localdate()
    amount_paid = paid if paid is not None else paid_toward_promise(promise)

    if amount_paid >= promise.amount and promise.amount > ZERO:
        return PaymentPromiseStatus.FULFILLED
    if amount_paid > ZERO:
        # partial before or after due
        if promise.promised_date < today and amount_paid < promise.amount:
            # still partial after due — keep partially fulfilled (not broken if some payment)
            return PaymentPromiseStatus.PARTIALLY_FULFILLED
        return PaymentPromiseStatus.PARTIALLY_FULFILLED
    if promise.promised_date < today:
        return PaymentPromiseStatus.BROKEN
    return PaymentPromiseStatus.PENDING


def refresh_promise_status(promise: PaymentPromise, *, as_of: date | None = None) -> PaymentPromise:
    new_status = compute_promise_status(promise, as_of=as_of)
    if new_status != promise.status:
        promise.status = new_status
        update_fields = ["status", "updated_at"]
        if new_status == PaymentPromiseStatus.FULFILLED and promise.fulfilled_at is None:
            promise.fulfilled_at = timezone.now()
            update_fields.append("fulfilled_at")
        elif new_status != PaymentPromiseStatus.FULFILLED:
            promise.fulfilled_at = None
            update_fields.append("fulfilled_at")
        promise.save(update_fields=update_fields)
    return promise


def validate_promise_inputs(
    *,
    organization,
    customer: Customer,
    promised_date: date,
    amount: Decimal,
    invoice: Invoice | None = None,
    as_of: date | None = None,
    allow_past_date: bool = False,
) -> dict[str, Any]:
    """NP-091 validations; returns warnings dict (non-blocking)."""
    today = as_of or timezone.localdate()
    warnings: dict[str, Any] = {}

    if customer.organization_id != organization.id:
        raise PromiseValidationError("Müşteri bu organizasyona ait değil.", "customer_mismatch")

    if amount is None or amount <= ZERO:
        raise PromiseValidationError(
            "Söz tutarı sıfır veya negatif olamaz.",
            "invalid_amount",
        )

    if not allow_past_date and promised_date < today:
        raise PromiseValidationError(
            "Söz tarihi geçmiş bir tarih olamaz.",
            "past_promised_date",
        )

    if invoice is not None:
        if invoice.organization_id != organization.id:
            raise PromiseValidationError("Fatura bulunamadı.", "invoice_not_found")
        if invoice.customer_id != customer.id:
            raise PromiseValidationError(
                "Fatura bu müşteriye ait değil.",
                "invoice_customer_mismatch",
            )
        if invoice.status in CLOSED_INVOICE_STATUSES:
            raise PromiseValidationError(
                "Kapalı faturaya ödeme sözü girilemez.",
                "invoice_closed",
            )

    metrics = customer_financial_metrics(customer)
    open_balance = Decimal(str(metrics.get("open_balance") or ZERO))
    warnings["open_balance"] = str(open_balance)
    if amount > open_balance:
        warnings["amount_exceeds_open_balance"] = {
            "code": "amount_exceeds_open_balance",
            "detail": (
                f"Söz tutarı ({amount}) açık bakiyeden ({open_balance}) fazla."
            ),
            "open_balance": str(open_balance),
        }

    # NP-430 — same-date existing promises for this customer.
    same_date = list(
        PaymentPromise.objects.for_organization(organization)
        .filter(customer=customer, promised_date=promised_date)
        .exclude(status=PaymentPromiseStatus.CANCELLED)
        .order_by("id")
        .values("id", "amount", "currency", "status")[:20]
    )
    if same_date:
        warnings["same_date_promises"] = {
            "code": "same_date_promises",
            "detail": (
                f"Bu müşteri için {promised_date.isoformat()} tarihinde "
                f"{len(same_date)} mevcut söz var."
            ),
            "promises": [
                {
                    "id": row["id"],
                    "amount": str(row["amount"]),
                    "currency": row["currency"],
                    "status": row["status"],
                }
                for row in same_date
            ],
        }

    return warnings


@transaction.atomic
def create_promise(
    *,
    organization,
    customer: Customer,
    promised_date: date,
    amount: Decimal,
    currency: str = "TRY",
    notes: str = "",
    invoice: Invoice | None = None,
    created_by=None,
    create_follow_up: bool = False,
    assigned_to=None,
    follow_up_due_date: date | None = None,
) -> tuple[PaymentPromise, dict[str, Any]]:
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    currency = (currency or "TRY").upper()
    warnings = validate_promise_inputs(
        organization=organization,
        customer=customer,
        promised_date=promised_date,
        amount=amount,
        invoice=invoice,
    )
    promise = PaymentPromise.objects.create(
        organization=organization,
        customer=customer,
        invoice=invoice,
        promised_date=promised_date,
        amount=amount,
        currency=currency,
        status=PaymentPromiseStatus.PENDING,
        notes=notes or "",
        created_by=created_by,
    )
    CollectionActivity.objects.create(
        organization=organization,
        customer=customer,
        activity_type=CollectionActivityType.PROMISE,
        summary=f"Ödeme sözü: {amount} {currency} / {promised_date}",
        notes=notes or "",
        created_by=created_by,
        metadata={"promise_id": promise.id},
    )
    follow_up = None
    if create_follow_up:
        from apps.collections.services import create_task

        due = follow_up_due_date or promised_date
        assignee = assigned_to or customer.assigned_user or created_by
        follow_up = create_task(
            organization=organization,
            customer=customer,
            due_date=due,
            title=f"Ödeme sözü takibi — {customer.name}",
            description=(
                f"Söz #{promise.id}: {amount} {currency} / {promised_date}"
            ),
            task_type=CollectionTaskType.FOLLOW_UP,
            assigned_to=assignee,
            created_by=created_by,
            invoice=invoice,
            related_promise=promise,
            source=CollectionTaskSource.FOLLOW_UP,
        )
        warnings["follow_up_task_id"] = follow_up.id

    write_audit_log(
        organization=organization,
        actor=created_by,
        action="payment_promise.create",
        entity_type="PaymentPromise",
        entity_id=promise.id,
        summary=f"Ödeme sözü {amount} {currency}",
        changes={
            "warnings": {
                k: v
                for k, v in warnings.items()
                if k not in {"open_balance", "follow_up_task_id"}
            },
            "follow_up_task_id": follow_up.id if follow_up else None,
        },
    )
    # NP-103: söz verilmesi → risk
    bump_customer_risk(customer)
    return promise, warnings


@transaction.atomic
def update_promise(
    promise: PaymentPromise,
    *,
    actor=None,
    promised_date: date | None = None,
    amount: Decimal | None = None,
    notes: str | None = None,
    invoice: Invoice | None = None,
    clear_invoice: bool = False,
) -> tuple[PaymentPromise, dict[str, Any]]:
    if promise.status in {
        PaymentPromiseStatus.CANCELLED,
        PaymentPromiseStatus.FULFILLED,
    }:
        raise PromiseValidationError(
            "Bu durumdaki söz güncellenemez.",
            "immutable_status",
        )

    new_date = promised_date if promised_date is not None else promise.promised_date
    new_amount = (
        Decimal(str(amount)).quantize(Decimal("0.01"))
        if amount is not None
        else promise.amount
    )
    new_invoice = promise.invoice
    if clear_invoice:
        new_invoice = None
    elif invoice is not None:
        new_invoice = invoice

    warnings = validate_promise_inputs(
        organization=promise.organization,
        customer=promise.customer,
        promised_date=new_date,
        amount=new_amount,
        invoice=new_invoice,
        allow_past_date=new_date == promise.promised_date,
    )
    promise.promised_date = new_date
    promise.amount = new_amount
    if notes is not None:
        promise.notes = notes
    promise.invoice = new_invoice
    promise.save()
    refresh_promise_status(promise)
    write_audit_log(
        organization=promise.organization,
        actor=actor,
        action="payment_promise.update",
        entity_type="PaymentPromise",
        entity_id=promise.id,
        summary="Ödeme sözü güncellendi",
        changes={"warnings": warnings},
    )
    return promise, warnings


@transaction.atomic
def cancel_promise(promise: PaymentPromise, *, actor=None, reason: str = "") -> PaymentPromise:
    if promise.status == PaymentPromiseStatus.CANCELLED:
        raise PromiseValidationError("Söz zaten iptal.", "already_cancelled")
    promise.status = PaymentPromiseStatus.CANCELLED
    if reason:
        promise.notes = (promise.notes + f"\n[İptal] {reason}").strip()
    promise.save(update_fields=["status", "notes", "updated_at"])
    write_audit_log(
        organization=promise.organization,
        actor=actor,
        action="payment_promise.cancel",
        entity_type="PaymentPromise",
        entity_id=promise.id,
        summary="Ödeme sözü iptal",
        changes={"reason": reason},
    )
    return promise


def evaluate_promises_after_payment(customer, payment=None) -> int:
    """Recalculate open promises after a payment (NP-092 / NP-073)."""
    del payment
    updated = 0
    qs = PaymentPromise.objects.filter(
        customer=customer,
        status__in={
            PaymentPromiseStatus.PENDING,
            PaymentPromiseStatus.PARTIALLY_FULFILLED,
            PaymentPromiseStatus.BROKEN,
        },
    )
    for promise in qs:
        before = promise.status
        refresh_promise_status(promise)
        if promise.status != before:
            updated += 1
    return updated


@transaction.atomic
def process_broken_promises(*, organization=None, as_of: date | None = None) -> dict[str, int]:
    """
    NP-093 daily:
    - PENDING past due → BROKEN
    - critical collection task
    - raise customer risk
    - dashboard alert
    """
    from apps.collections.services import create_task

    today = as_of or timezone.localdate()
    qs = (
        PaymentPromise.objects.filter(
            status=PaymentPromiseStatus.PENDING,
            promised_date__lt=today,
        )
        .select_related("customer", "customer__assigned_user", "organization")
    )
    if organization is not None:
        qs = qs.filter(organization=organization)

    broken = 0
    tasks = 0
    alerts = 0
    for promise in qs:
        paid = paid_toward_promise(promise)
        if paid >= promise.amount:
            refresh_promise_status(promise, as_of=today, paid=paid)
            continue
        if paid > ZERO:
            promise.status = PaymentPromiseStatus.PARTIALLY_FULFILLED
            promise.save(update_fields=["status", "updated_at"])
            continue

        promise.status = PaymentPromiseStatus.BROKEN
        promise.save(update_fields=["status", "updated_at"])
        broken += 1

        from apps.workflows.engine import (
            build_promise_context,
            dispatch_trigger,
            org_has_active_workflow,
        )
        from apps.workflows.enums import WorkflowTriggerType

        if org_has_active_workflow(promise.organization, WorkflowTriggerType.PROMISE_BROKEN):
            context = build_promise_context(promise)
            dispatch_trigger(
                promise.organization,
                WorkflowTriggerType.PROMISE_BROKEN,
                customer=promise.customer,
                context=context,
                idempotency_key=f"promise:{promise.id}:broken",
                trigger_entity_type="collections.PaymentPromise",
                trigger_entity_id=str(promise.id),
                invoice=promise.invoice,
                promise=promise,
            )
            continue

        has_open = CollectionTask.objects.filter(
            organization_id=promise.organization_id,
            related_promise_id=promise.id,
            status__in=[CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS],
        ).exists()
        if not has_open:
            create_task(
                organization=promise.organization,
                customer=promise.customer,
                due_date=today,
                title=f"Bozulan ödeme sözü — {promise.customer.name}",
                description=f"Söz tarihi {promise.promised_date}, tutar {promise.amount}",
                task_type=CollectionTaskType.CALL,
                assigned_to=promise.customer.assigned_user,
                invoice=promise.invoice,
                related_promise=promise,
                source=CollectionTaskSource.BROKEN_PROMISE,
            )
            tasks += 1

        # NP-103: sözün bozulması → risk
        bump_customer_risk(promise.customer)

        create_dashboard_alert(
            organization=promise.organization,
            title=f"Bozulan ödeme sözü: {promise.customer.name}",
            body=(
                f"{promise.promised_date} tarihli {promise.amount} {promise.currency} "
                "sözü bozuldu. Kritik tahsilat görevi oluşturuldu."
            ),
            severity=AlertSeverity.CRITICAL,
            notification_type="PROMISE_BROKEN",
            category="broken_promise",
            entity_type="PaymentPromise",
            entity_id=promise.id,
            created_for=promise.customer.assigned_user,
        )
        alerts += 1

    return {"broken": broken, "tasks_created": tasks, "alerts_created": alerts}


def promises_calendar(*, organization, as_of: date | None = None) -> dict[str, list[PaymentPromise]]:
    """NP-094 calendar groups (legacy 4 buckets)."""
    board = promises_status_board(organization=organization, as_of=as_of)
    return {
        "today": board["today"],
        "upcoming": board["upcoming"],
        "broken": board["broken"],
        "fulfilled": board["fulfilled"] + board["partial"],
    }


def promises_status_board(
    *, organization, as_of: date | None = None
) -> dict[str, list[PaymentPromise]]:
    """NP-431 — Bekliyor / Bugün / Yaklaşıyor / Kısmi / Karşılandı / Bozuldu."""
    today = as_of or timezone.localdate()
    base = (
        PaymentPromise.objects.for_organization(organization)
        .exclude(status=PaymentPromiseStatus.CANCELLED)
        .select_related(
            "customer",
            "customer__assigned_user",
            "invoice",
            "created_by",
        )
        .order_by("promised_date", "id")
    )
    pending_future = base.filter(
        status=PaymentPromiseStatus.PENDING,
        promised_date__gt=today + timedelta(days=7),
    )
    return {
        "pending": list(pending_future[:100]),
        "today": list(
            base.filter(status=PaymentPromiseStatus.PENDING, promised_date=today)[:100]
        ),
        "upcoming": list(
            base.filter(
                status=PaymentPromiseStatus.PENDING,
                promised_date__gt=today,
                promised_date__lte=today + timedelta(days=7),
            )[:100]
        ),
        "partial": list(
            base.filter(status=PaymentPromiseStatus.PARTIALLY_FULFILLED)
            .order_by("-promised_date")[:100]
        ),
        "fulfilled": list(
            base.filter(status=PaymentPromiseStatus.FULFILLED)
            .order_by("-promised_date")[:100]
        ),
        "broken": list(base.filter(status=PaymentPromiseStatus.BROKEN)[:100]),
    }
