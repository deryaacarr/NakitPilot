"""Dry-run workflow simulation over recent history (NP-215)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.workflows.condition_engine import evaluate_step_conditions
from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowEdgeHandle,
    WorkflowStepType,
    WorkflowTriggerType,
)
from apps.workflows.models import CollectionWorkflow, WorkflowEdge, WorkflowStep


@dataclass
class SimulationCounters:
    events_evaluated: int = 0
    tasks_created: int = 0
    messages_sent: int = 0
    customers_messaged: set[int] = field(default_factory=set)
    critical_notifications: int = 0
    notifications: int = 0
    risk_recalculations: int = 0
    tags_added: int = 0
    webhooks_triggered: int = 0
    approvals_requested: int = 0
    delays_scheduled: int = 0
    by_action_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def to_dict(self) -> dict[str, Any]:
        return {
            "events_evaluated": self.events_evaluated,
            "tasks_created": self.tasks_created,
            "messages_sent": self.messages_sent,
            "customers_messaged": len(self.customers_messaged),
            "critical_notifications": self.critical_notifications,
            "notifications": self.notifications,
            "risk_recalculations": self.risk_recalculations,
            "tags_added": self.tags_added,
            "webhooks_triggered": self.webhooks_triggered,
            "approvals_requested": self.approvals_requested,
            "delays_scheduled": self.delays_scheduled,
            "by_action_type": dict(self.by_action_type),
        }


def _next_step(step: WorkflowStep, handle: str = WorkflowEdgeHandle.NEXT) -> WorkflowStep | None:
    edge = (
        WorkflowEdge.objects.filter(from_step=step, source_handle=handle)
        .select_related("to_step")
        .first()
    )
    if edge and edge.to_step.is_active:
        return edge.to_step
    if handle == WorkflowEdgeHandle.NEXT:
        return (
            WorkflowStep.objects.filter(
                workflow_id=step.workflow_id,
                order__gt=step.order,
                is_active=True,
            )
            .order_by("order", "id")
            .first()
        )
    return None


def _action_specs(step: WorkflowStep) -> list[tuple[str, dict]]:
    cfg = step.config or {}
    if cfg.get("action_type"):
        return [(cfg["action_type"], cfg.get("params") or {})]
    legacy = list(step.actions.order_by("order", "id"))
    if legacy:
        return [(a.action_type, a.params or {}) for a in legacy]
    return []


def _record_action(counters: SimulationCounters, action_type: str, params: dict, customer_id: int | None):
    counters.by_action_type[action_type] += 1
    if action_type == WorkflowActionType.CREATE_TASK:
        counters.tasks_created += 1
    elif action_type in {WorkflowActionType.PREPARE_EMAIL, WorkflowActionType.SEND_EMAIL}:
        counters.messages_sent += 1
        if customer_id:
            counters.customers_messaged.add(customer_id)
    elif action_type == WorkflowActionType.NOTIFY:
        counters.notifications += 1
        sev = str(params.get("severity") or "").lower()
        if sev in {"critical", "error"}:
            counters.critical_notifications += 1
        if customer_id:
            counters.customers_messaged.add(customer_id)
    elif action_type == WorkflowActionType.RECALCULATE_RISK:
        counters.risk_recalculations += 1
    elif action_type == WorkflowActionType.ADD_TAG:
        counters.tags_added += 1
    elif action_type == WorkflowActionType.TRIGGER_WEBHOOK:
        counters.webhooks_triggered += 1
    elif action_type == WorkflowActionType.REQUEST_APPROVAL:
        counters.approvals_requested += 1


def dry_run_workflow(
    workflow: CollectionWorkflow,
    context: dict[str, Any],
    *,
    customer_id: int | None = None,
    counters: SimulationCounters | None = None,
    skip_delays: bool = True,
) -> SimulationCounters:
    """Walk the graph without writing; accumulate action counters."""
    counters = counters or SimulationCounters()
    start = (
        workflow.steps.filter(step_type=WorkflowStepType.TRIGGER, is_active=True)
        .order_by("order", "id")
        .first()
        or workflow.steps.filter(is_active=True).order_by("order", "id").first()
    )
    current = start
    visited = 0
    while current is not None and visited < 100:
        visited += 1
        stype = current.step_type
        if stype == WorkflowStepType.TRIGGER:
            current = _next_step(current)
            continue
        if stype == WorkflowStepType.STOP:
            break
        if stype in {WorkflowStepType.CONDITION, WorkflowStepType.BRANCH}:
            matched = evaluate_step_conditions(current, context)
            if stype == WorkflowStepType.BRANCH:
                handle = WorkflowEdgeHandle.TRUE if matched else WorkflowEdgeHandle.FALSE
                current = _next_step(current, handle)
                continue
            if matched:
                current = _next_step(current, WorkflowEdgeHandle.NEXT)
            else:
                alt = _next_step(current, WorkflowEdgeHandle.FALSE)
                if alt is None:
                    break
                current = alt
            continue
        if stype == WorkflowStepType.DELAY:
            counters.delays_scheduled += 1
            if skip_delays:
                # Assume wait completes and continue (historical what-if).
                current = _next_step(current)
            else:
                break
            continue
        if stype == WorkflowStepType.ACTION:
            for atype, params in _action_specs(current):
                _record_action(counters, atype, params, customer_id)
            current = _next_step(current)
            continue
        current = _next_step(current)
    return counters


def _collect_invoice_overdue_events(organization, *, days: int, as_of) -> list[dict[str, Any]]:
    from apps.invoices.models import Invoice, InvoiceStatus
    from apps.workflows.engine import build_invoice_overdue_context

    window_start = as_of - timedelta(days=days)
    events: list[dict[str, Any]] = []
    invoices = (
        Invoice.objects.filter(organization=organization)
        .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED])
        .filter(due_date__lt=as_of)
        .select_related("customer")
    )
    # Milestone days commonly used in overdue workflows
    milestones = (1, 7, 14, 21, 30, 45, 60, 90)
    for invoice in invoices.iterator(chunk_size=200):
        # Approximate: if still has remaining OR was paid after due in window
        remaining = invoice.remaining_amount()
        paid_late = (
            invoice.status == InvoiceStatus.PAID
            and invoice.payment_completion_date
            and invoice.payment_completion_date >= window_start
            and invoice.payment_completion_date > invoice.due_date
        )
        if remaining <= 0 and not paid_late:
            continue
        # Days after due that fell inside the simulation window
        first_overdue_day = invoice.due_date + timedelta(days=1)
        last_day = as_of
        if paid_late and invoice.payment_completion_date:
            last_day = min(as_of, invoice.payment_completion_date)
        if last_day < window_start:
            continue
        for m in milestones:
            milestone_date = invoice.due_date + timedelta(days=m)
            if milestone_date < window_start or milestone_date > last_day:
                continue
            if milestone_date < first_overdue_day:
                continue
            ctx = build_invoice_overdue_context(invoice, as_of=milestone_date)
            events.append(
                {
                    "customer_id": invoice.customer_id,
                    "context": ctx,
                    "key": f"invoice:{invoice.id}:overdue:{m}",
                }
            )
    return events


def _collect_promise_broken_events(organization, *, days: int, as_of) -> list[dict[str, Any]]:
    from apps.collections.models import PaymentPromise, PaymentPromiseStatus
    from apps.workflows.engine import build_promise_context

    window_start = as_of - timedelta(days=days)
    qs = (
        PaymentPromise.objects.filter(
            organization=organization,
            status=PaymentPromiseStatus.BROKEN,
            promised_date__gte=window_start - timedelta(days=7),
            promised_date__lt=as_of,
        )
        .select_related("customer")
    )
    events = []
    for promise in qs:
        ctx = build_promise_context(promise)
        # Force BROKEN in context
        ctx["promise"]["status"] = PaymentPromiseStatus.BROKEN
        events.append(
            {
                "customer_id": promise.customer_id,
                "context": ctx,
                "key": f"promise:{promise.id}:broken",
            }
        )
    return events


def _collect_payment_events(organization, *, days: int, as_of) -> list[dict[str, Any]]:
    from apps.payments.models import Payment

    window_start = as_of - timedelta(days=days)
    qs = (
        Payment.objects.filter(
            organization=organization,
            cancelled_at__isnull=True,
            payment_date__gte=window_start,
            payment_date__lte=as_of,
        )
        .select_related("customer")
    )
    events = []
    for payment in qs:
        customer = payment.customer
        events.append(
            {
                "customer_id": customer.id,
                "context": {
                    "payment": {
                        "id": payment.id,
                        "amount": float(payment.amount),
                    },
                    "customer": {
                        "id": customer.id,
                        "risk_level": customer.risk_status,
                        "risk_status": customer.risk_status,
                        "risk_score": customer.risk_score,
                        "tags": list(customer.tags or []),
                    },
                },
                "key": f"payment:{payment.id}:received",
            }
        )
    return events


def collect_simulation_events(
    organization,
    trigger_type: str,
    *,
    days: int = 30,
    as_of=None,
) -> list[dict[str, Any]]:
    as_of = as_of or timezone.localdate()
    if trigger_type == WorkflowTriggerType.INVOICE_OVERDUE:
        return _collect_invoice_overdue_events(organization, days=days, as_of=as_of)
    if trigger_type == WorkflowTriggerType.PROMISE_BROKEN:
        return _collect_promise_broken_events(organization, days=days, as_of=as_of)
    if trigger_type == WorkflowTriggerType.PAYMENT_RECEIVED:
        return _collect_payment_events(organization, days=days, as_of=as_of)
    # Manual / other: no historical events
    return []


def simulate_workflow(
    workflow: CollectionWorkflow,
    *,
    days: int = 30,
    as_of=None,
) -> dict[str, Any]:
    as_of = as_of or timezone.localdate()
    events = collect_simulation_events(
        workflow.organization,
        workflow.trigger_type,
        days=days,
        as_of=as_of,
    )
    counters = SimulationCounters()
    seen_keys: set[str] = set()
    for event in events:
        key = event["key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        counters.events_evaluated += 1
        dry_run_workflow(
            workflow,
            event["context"],
            customer_id=event.get("customer_id"),
            counters=counters,
            skip_delays=True,
        )

    summary = counters.to_dict()
    summary.update(
        {
            "period_days": days,
            "as_of": as_of.isoformat(),
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "workflow_version": workflow.version,
            "trigger_type": workflow.trigger_type,
            "headline": (
                f"Bu workflow son {days} günlük verilere uygulansaydı: "
                f"{summary['tasks_created']} görev oluşturulurdu, "
                f"{summary['customers_messaged']} müşteriye mesaj gönderilirdi, "
                f"{summary['critical_notifications']} kritik bildirim oluşurdu."
            ),
        }
    )
    return summary
