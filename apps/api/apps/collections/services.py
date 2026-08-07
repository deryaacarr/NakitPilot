"""Priority scoring (NP-082) and task lifecycle services."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.audit.models import write_audit_log
from apps.collections.models import (
    CallOutcome,
    CollectionActivity,
    CollectionActivityType,
    CollectionTask,
    CollectionTaskPriority,
    CollectionTaskSource,
    CollectionTaskStatus,
    CollectionTaskType,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer, RiskStatus
from apps.invoices.models import Invoice, InvoiceStatus

User = get_user_model()
ZERO = Decimal("0.00")
HIGH_OVERDUE_THRESHOLD = Decimal("5000.00")


def evaluate_promises_after_payment(customer, payment=None) -> int:
    """Delegate to promises module (NP-092)."""
    from apps.collections.promises import evaluate_promises_after_payment as _eval

    return _eval(customer, payment=payment)


class CollectionValidationError(Exception):
    def __init__(self, message: str, code: str = "invalid_task"):
        super().__init__(message)
        self.message = message
        self.code = code


def priority_level_for_score(score: int) -> str:
    if score >= 90:
        return CollectionTaskPriority.CRITICAL
    if score >= 60:
        return CollectionTaskPriority.HIGH
    if score >= 30:
        return CollectionTaskPriority.MEDIUM
    return CollectionTaskPriority.LOW


def compute_priority_score(
    customer: Customer,
    *,
    as_of: date | None = None,
    promise_today: bool | None = None,
    promise_broken: bool | None = None,
) -> tuple[int, str, dict[str, Any]]:
    """NP-082 rule-based priority."""
    today = as_of or timezone.localdate()
    metrics = customer_financial_metrics(customer)
    overdue_balance = Decimal(str(metrics.get("overdue_balance") or ZERO))
    oldest = metrics.get("oldest_overdue_days")

    if promise_today is None:
        promise_today = PaymentPromise.objects.filter(
            customer=customer,
            status=PaymentPromiseStatus.PENDING,
            promised_date=today,
        ).exists()
    if promise_broken is None:
        promise_broken = PaymentPromise.objects.filter(
            customer=customer,
            status=PaymentPromiseStatus.BROKEN,
        ).exists()

    last_contact = customer.last_contact_at
    contact_stale = last_contact is None or (
        timezone.now() - last_contact
    ).days > 7

    score = 0
    details: dict[str, Any] = {}
    if overdue_balance >= HIGH_OVERDUE_THRESHOLD:
        score += 25
        details["overdue_amount_high"] = 25
    if oldest is not None and oldest > 30:
        score += 25
        details["overdue_days_gt_30"] = 25
    if promise_today:
        score += 30
        details["promise_today"] = 30
    if promise_broken:
        score += 40
        details["promise_broken"] = 40
    if contact_stale:
        score += 15
        details["no_contact_7d"] = 15
    if customer.risk_status in {RiskStatus.HIGH, RiskStatus.CRITICAL}:
        score += 20
        details["high_risk"] = 20

    score = max(0, min(100, score))
    return score, priority_level_for_score(score), details


def refresh_task_priority(task: CollectionTask, *, save: bool = True) -> CollectionTask:
    score, level, _ = compute_priority_score(task.customer)
    task.priority_score = score
    task.priority = level
    if save:
        task.save(update_fields=["priority_score", "priority", "updated_at"])
    return task


@transaction.atomic
def create_task(
    *,
    organization,
    customer: Customer,
    due_date: date,
    title: str = "",
    description: str = "",
    task_type: str = CollectionTaskType.CALL,
    assigned_to=None,
    created_by=None,
    invoice: Invoice | None = None,
    related_promise: PaymentPromise | None = None,
    source: str = CollectionTaskSource.MANUAL,
) -> CollectionTask:
    if customer.organization_id != organization.id:
        raise CollectionValidationError("Müşteri bu organizasyona ait değil.", "customer_mismatch")

    assignee = assigned_to or customer.assigned_user
    warning = None
    if assignee is not None and not assignee.is_active:
        warning = "assigned_user_inactive"

    score, level, _ = compute_priority_score(
        customer,
        promise_broken=related_promise.status == PaymentPromiseStatus.BROKEN
        if related_promise
        else None,
        promise_today=related_promise.promised_date == timezone.localdate()
        if related_promise
        else None,
    )
    if source == CollectionTaskSource.BROKEN_PROMISE:
        score = max(score, 90)
        level = CollectionTaskPriority.CRITICAL

    task = CollectionTask.objects.create(
        organization=organization,
        customer=customer,
        invoice=invoice,
        related_promise=related_promise,
        task_type=task_type,
        title=title or f"Tahsilat — {customer.name}",
        description=description,
        due_date=due_date,
        assigned_to=assignee,
        created_by=created_by,
        source=source,
        priority_score=score,
        priority=level,
    )
    write_audit_log(
        organization=organization,
        actor=created_by,
        action="collection_task.create",
        entity_type="CollectionTask",
        entity_id=task.id,
        summary=task.title,
        changes={"warning": warning, "assigned_to": assignee.id if assignee else None},
    )
    task._assign_warning = warning  # type: ignore[attr-defined]
    return task


@transaction.atomic
def complete_task(
    task: CollectionTask,
    *,
    actor=None,
    outcome: str,
    outcome_notes: str,
    create_follow_up: bool = False,
    promise_given: bool = False,
    callback_date: date | None = None,
    promise_amount: Decimal | None = None,
    promise_date: date | None = None,
) -> dict[str, Any]:
    """NP-083 complete with required outcome fields."""
    if not task.is_open:
        raise CollectionValidationError("Görev zaten kapalı.", "task_closed")
    if outcome not in CallOutcome.values:
        raise CollectionValidationError("Geçersiz görüşme sonucu.", "invalid_outcome")
    notes = (outcome_notes or "").strip()
    if not notes:
        raise CollectionValidationError("Görüşme notu zorunlu.", "notes_required")
    if create_follow_up and callback_date is None:
        raise CollectionValidationError(
            "Yeni görev için tekrar aranma tarihi gerekli.",
            "callback_date_required",
        )
    if promise_given and (promise_amount is None or promise_date is None):
        raise CollectionValidationError(
            "Ödeme sözü için tutar ve tarih gerekli.",
            "promise_fields_required",
        )

    now = timezone.now()
    task.status = CollectionTaskStatus.COMPLETED
    task.outcome = outcome
    task.outcome_notes = notes
    task.callback_date = callback_date
    task.completed_at = now
    task.save(
        update_fields=[
            "status",
            "outcome",
            "outcome_notes",
            "callback_date",
            "completed_at",
            "updated_at",
        ]
    )

    customer = task.customer
    customer.last_contact_at = now
    customer.save(update_fields=["last_contact_at", "updated_at"])

    CollectionActivity.objects.create(
        organization=task.organization,
        customer=customer,
        task=task,
        activity_type=CollectionActivityType.TASK_COMPLETED,
        summary=f"Görev tamamlandı: {dict(CallOutcome.choices).get(outcome, outcome)}",
        notes=notes,
        occurred_at=now,
        created_by=actor,
        metadata={"outcome": outcome, "task_id": task.id},
    )
    if outcome == CallOutcome.REACHED or task.task_type == CollectionTaskType.CALL:
        CollectionActivity.objects.create(
            organization=task.organization,
            customer=customer,
            task=task,
            activity_type=CollectionActivityType.CALL,
            summary="Telefon görüşmesi",
            notes=notes,
            occurred_at=now,
            created_by=actor,
            metadata={"outcome": outcome},
        )

    follow_up = None
    if create_follow_up and callback_date is not None:
        follow_up = create_task(
            organization=task.organization,
            customer=customer,
            due_date=callback_date,
            title=f"Takip — {customer.name}",
            description=f"Önceki görev #{task.id} sonrası takip",
            task_type=CollectionTaskType.FOLLOW_UP,
            assigned_to=task.assigned_to,
            created_by=actor,
            invoice=task.invoice,
            source=CollectionTaskSource.FOLLOW_UP,
        )

    promise = None
    if promise_given:
        promise = PaymentPromise.objects.create(
            organization=task.organization,
            customer=customer,
            invoice=task.invoice,
            promised_date=promise_date,
            amount=promise_amount or ZERO,
            currency=task.invoice.currency if task.invoice_id else "TRY",
            status=PaymentPromiseStatus.PENDING,
            notes=notes,
            created_by=actor,
        )
        CollectionActivity.objects.create(
            organization=task.organization,
            customer=customer,
            task=task,
            activity_type=CollectionActivityType.PROMISE,
            summary=f"Ödeme sözü: {promise.amount} {promise.currency} / {promise.promised_date}",
            notes=notes,
            occurred_at=now,
            created_by=actor,
            metadata={"promise_id": promise.id},
        )

    write_audit_log(
        organization=task.organization,
        actor=actor,
        action="collection_task.complete",
        entity_type="CollectionTask",
        entity_id=task.id,
        summary=f"Tamamlandı ({outcome})",
        changes={"outcome": outcome},
    )
    # NP-103: görev tamamlanması (+ söz verilmişse) → risk
    from apps.risk.triggers import bump_customer_risk

    bump_customer_risk(customer)
    return {"task": task, "follow_up": follow_up, "promise": promise}


@transaction.atomic
def confirm_structured_call_notes(
    task: CollectionTask,
    *,
    actor=None,
    raw_notes: str,
    promised_amount: Decimal | None = None,
    promised_date: date | None = None,
    next_action_date: date | None = None,
    sentiment: str | None = None,
    objection: str | None = None,
    complete_task_flag: bool = False,
) -> dict[str, Any]:
    """
    NP-232: persist structured fields only after explicit user confirmation.

    Creates a NOTE activity with structured metadata. Optionally creates a
    PaymentPromise and/or follow-up task. Completing the collection task is
    opt-in via ``complete_task_flag``.
    """
    if task.organization_id is None:
        raise CollectionValidationError("Görev organizasyonu eksik.", "missing_org")
    notes = (raw_notes or "").strip()
    if not notes:
        raise CollectionValidationError("Görüşme notu zorunlu.", "notes_required")

    now = timezone.now()
    structured = {
        "promised_amount": str(promised_amount) if promised_amount is not None else None,
        "promised_date": promised_date.isoformat() if promised_date else None,
        "next_action_date": next_action_date.isoformat() if next_action_date else None,
        "sentiment": sentiment or "neutral",
        "objection": objection,
        "confirmed": True,
    }

    activity = CollectionActivity.objects.create(
        organization=task.organization,
        customer=task.customer,
        task=task,
        activity_type=CollectionActivityType.NOTE,
        summary="Yapılandırılmış görüşme notu (onaylı)",
        notes=notes,
        occurred_at=now,
        created_by=actor,
        metadata={"structured_notes": structured, "source": "np232"},
    )

    promise = None
    if promised_amount is not None and promised_date is not None:
        promise = PaymentPromise.objects.create(
            organization=task.organization,
            customer=task.customer,
            invoice=task.invoice,
            promised_date=promised_date,
            amount=promised_amount,
            currency=task.invoice.currency if task.invoice_id else "TRY",
            status=PaymentPromiseStatus.PENDING,
            notes=notes,
            created_by=actor,
        )
        CollectionActivity.objects.create(
            organization=task.organization,
            customer=task.customer,
            task=task,
            activity_type=CollectionActivityType.PROMISE,
            summary=f"Ödeme sözü: {promise.amount} {promise.currency} / {promise.promised_date}",
            notes=notes,
            occurred_at=now,
            created_by=actor,
            metadata={
                "promise_id": promise.id,
                "structured_notes": structured,
                "source": "np232",
            },
        )

    follow_up = None
    if next_action_date is not None:
        follow_up = create_task(
            organization=task.organization,
            customer=task.customer,
            due_date=next_action_date,
            title=f"Takip — {task.customer.name}",
            description=f"Yapılandırılmış not sonrası takip (görev #{task.id})",
            task_type=CollectionTaskType.FOLLOW_UP,
            assigned_to=task.assigned_to,
            created_by=actor,
            invoice=task.invoice,
            source=CollectionTaskSource.FOLLOW_UP,
        )

    complete_result = None
    if complete_task_flag and task.is_open:
        outcome = CallOutcome.PROMISE_GIVEN if promise is not None else CallOutcome.REACHED
        if objection:
            outcome = CallOutcome.DISPUTED if promise is None else CallOutcome.PROMISE_GIVEN
        complete_result = complete_task(
            task,
            actor=actor,
            outcome=outcome,
            outcome_notes=notes,
            create_follow_up=False,
            promise_given=False,
            callback_date=None,
            promise_amount=None,
            promise_date=None,
        )

    from apps.risk.triggers import bump_customer_risk

    bump_customer_risk(task.customer)

    return {
        "activity_id": activity.id,
        "promise": promise,
        "follow_up": follow_up,
        "structured": structured,
        "task": complete_result["task"] if complete_result else task,
        "completed": bool(complete_result),
    }


@transaction.atomic
def cancel_task(task: CollectionTask, *, actor=None, reason: str = "") -> CollectionTask:
    if task.status == CollectionTaskStatus.CANCELLED:
        raise CollectionValidationError("Görev zaten iptal.", "already_cancelled")
    if task.status == CollectionTaskStatus.COMPLETED:
        raise CollectionValidationError("Tamamlanan görev iptal edilemez.", "completed")
    task.status = CollectionTaskStatus.CANCELLED
    task.cancelled_at = timezone.now()
    task.cancellation_reason = (reason or "").strip()
    task.save(
        update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"]
    )
    write_audit_log(
        organization=task.organization,
        actor=actor,
        action="collection_task.cancel",
        entity_type="CollectionTask",
        entity_id=task.id,
        summary="Görev iptal",
        changes={"reason": reason},
    )
    return task


@transaction.atomic
def assign_tasks(
    *,
    organization,
    task_ids: list[int],
    assigned_to,
    actor=None,
) -> dict[str, Any]:
    """NP-085 assign / bulk assign."""
    if assigned_to is None:
        raise CollectionValidationError("Sorumlu kullanıcı gerekli.", "assignee_required")

    warning = None
    if not assigned_to.is_active:
        warning = "assigned_user_inactive"

    qs = CollectionTask.objects.for_organization(organization).filter(
        id__in=task_ids,
        status__in=[CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS],
    )
    updated = qs.update(assigned_to=assigned_to, updated_at=timezone.now())
    write_audit_log(
        organization=organization,
        actor=actor,
        action="collection_task.assign",
        entity_type="CollectionTask",
        entity_id=",".join(str(i) for i in task_ids[:50]),
        summary=f"{updated} görev atandı",
        changes={
            "assigned_to": assigned_to.id,
            "warning": warning,
            "task_ids": task_ids,
        },
    )
    return {"updated": updated, "warning": warning, "assigned_to": assigned_to.id}


def mark_broken_promises(*, organization=None, as_of: date | None = None) -> int:
    from apps.collections.promises import process_broken_promises

    return process_broken_promises(organization=organization, as_of=as_of)["broken"]


def generate_overdue_invoice_collection_tasks(
    *, organization=None, as_of: date | None = None
) -> dict[str, int]:
    """Create collection tasks for overdue invoices (NP-084 / NP-142 00:15)."""
    from apps.workflows.engine import (
        build_invoice_overdue_context,
        dispatch_trigger,
        org_has_active_workflow,
    )
    from apps.workflows.enums import WorkflowTriggerType

    today = as_of or timezone.localdate()
    invoice_qs = Invoice.objects.filter(
        status__in=[InvoiceStatus.OVERDUE, InvoiceStatus.OPEN, InvoiceStatus.PARTIALLY_PAID],
        due_date__lt=today,
    ).select_related("customer", "customer__assigned_user", "organization")
    if organization is not None:
        invoice_qs = invoice_qs.filter(organization=organization)

    created_overdue = 0
    workflow_dispatched = 0
    for invoice in invoice_qs.iterator(chunk_size=200):
        if invoice.remaining_amount() <= ZERO:
            continue

        overdue_days = max((today - invoice.due_date).days, 0)
        if org_has_active_workflow(invoice.organization, WorkflowTriggerType.INVOICE_OVERDUE):
            context = build_invoice_overdue_context(invoice, as_of=today)
            dispatch_trigger(
                invoice.organization,
                WorkflowTriggerType.INVOICE_OVERDUE,
                customer=invoice.customer,
                context=context,
                idempotency_key=f"invoice:{invoice.id}:overdue:{overdue_days}",
                trigger_entity_type="invoices.Invoice",
                trigger_entity_id=str(invoice.id),
                invoice=invoice,
            )
            workflow_dispatched += 1
            continue

        has_open = CollectionTask.objects.filter(
            organization_id=invoice.organization_id,
            invoice_id=invoice.id,
            status__in=[CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS],
        ).exists()
        if has_open:
            continue

        create_task(
            organization=invoice.organization,
            customer=invoice.customer,
            due_date=today,
            title=f"Gecikmiş fatura {invoice.number}",
            description=f"Vade {invoice.due_date}, kalan {invoice.remaining_amount()}",
            task_type=CollectionTaskType.CALL,
            assigned_to=invoice.customer.assigned_user,
            invoice=invoice,
            source=CollectionTaskSource.OVERDUE_INVOICE,
        )
        created_overdue += 1

    return {
        "tasks_from_overdue": created_overdue,
        "workflows_dispatched": workflow_dispatched,
    }


def auto_generate_collection_tasks(*, organization=None, as_of: date | None = None) -> dict[str, int]:
    """
    NP-084 / NP-093 daily job:
    - process broken promises (status, critical task, risk, alert)
    - create tasks for overdue invoices (no open task on same invoice)
    """
    from apps.collections.promises import process_broken_promises

    today = as_of or timezone.localdate()
    broken_result = process_broken_promises(organization=organization, as_of=today)
    overdue = generate_overdue_invoice_collection_tasks(
        organization=organization, as_of=today
    )

    return {
        "promises_marked_broken": broken_result["broken"],
        "tasks_from_broken_promises": broken_result["tasks_created"],
        "alerts_created": broken_result["alerts_created"],
        "tasks_from_overdue": overdue["tasks_from_overdue"],
    }


def today_board(*, organization, as_of: date | None = None) -> dict[str, list[CollectionTask]]:
    """NP-081 grouped tasks for the day board."""
    today = as_of or timezone.localdate()
    base = (
        CollectionTask.objects.for_organization(organization)
        .select_related(
            "customer",
            "customer__assigned_user",
            "assigned_to",
            "invoice",
            "related_promise",
        )
        .order_by("-priority_score", "due_date", "id")
    )

    overdue = list(
        base.filter(
            status__in=[CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS],
            due_date__lt=today,
        )[:100]
    )
    due_today = list(
        base.filter(
            status__in=[CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS],
            due_date=today,
        )[:100]
    )
    upcoming = list(
        base.filter(
            status__in=[CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS],
            due_date__gt=today,
            due_date__lte=today + timedelta(days=7),
        )[:100]
    )
    completed = list(
        base.filter(
            status=CollectionTaskStatus.COMPLETED,
            completed_at__date=today,
        )[:100]
    )
    return {
        "overdue": overdue,
        "today": due_today,
        "upcoming": upcoming,
        "completed": completed,
    }


def customer_timeline(*, organization, customer_id: int, limit: int = 100) -> list[dict[str, Any]]:
    """NP-086 chronological timeline for customer detail."""
    from apps.payments.models import Payment

    events: list[dict[str, Any]] = []

    activities = (
        CollectionActivity.objects.for_organization(organization)
        .filter(customer_id=customer_id)
        .select_related("created_by", "task")[:limit]
    )
    for row in activities:
        events.append(
            {
                "id": f"activity-{row.id}",
                "kind": row.activity_type,
                "label": dict(CollectionActivityType.choices).get(
                    row.activity_type, row.activity_type
                ),
                "summary": row.summary,
                "notes": row.notes,
                "occurred_at": row.occurred_at.isoformat(),
                "actor": row.created_by.email if row.created_by_id else None,
                "metadata": row.metadata,
            }
        )

    promises = (
        PaymentPromise.objects.for_organization(organization)
        .filter(customer_id=customer_id)
        .order_by("-created_at")[:limit]
    )
    for row in promises:
        events.append(
            {
                "id": f"promise-{row.id}",
                "kind": CollectionActivityType.PROMISE,
                "label": "Ödeme sözü",
                "summary": f"{row.amount} {row.currency} — {row.status}",
                "notes": row.notes,
                "occurred_at": row.created_at.isoformat(),
                "actor": row.created_by.email if row.created_by_id else None,
                "metadata": {
                    "promised_date": row.promised_date.isoformat(),
                    "status": row.status,
                },
            }
        )

    payments = (
        Payment.objects.for_organization(organization)
        .filter(customer_id=customer_id, cancelled_at__isnull=True)
        .order_by("-payment_date", "-id")[:limit]
    )
    for row in payments:
        occurred = timezone.make_aware(
            datetime.combine(row.payment_date, datetime.min.time())
        )
        events.append(
            {
                "id": f"payment-{row.id}",
                "kind": CollectionActivityType.PAYMENT,
                "label": "Ödeme",
                "summary": f"{row.amount} {row.currency}",
                "notes": row.notes,
                "occurred_at": occurred.isoformat(),
                "actor": row.recorded_by.email if row.recorded_by_id else None,
                "metadata": {"payment_id": row.id, "method": row.method},
            }
        )

    events.sort(key=lambda e: e["occurred_at"], reverse=True)
    return events[:limit]
