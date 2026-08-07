"""Workflow execution engine (NP-211–214)."""

from __future__ import annotations

import logging
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.workflows.actions import ActionError, run_action
from apps.workflows.business_days import compute_resume_at
from apps.workflows.condition_engine import evaluate_expression, evaluate_step_conditions
from apps.workflows.enums import (
    WorkflowEdgeHandle,
    WorkflowExecutionStatus,
    WorkflowLogEvent,
    WorkflowStepType,
    WorkflowTriggerType,
)
from apps.workflows.models import (
    CollectionWorkflow,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


def _log(execution, step, event: str, message: str = "", payload: dict | None = None):
    WorkflowExecutionLog.objects.create(
        organization=execution.organization,
        execution=execution,
        step=step,
        event=event,
        message=(message or "")[:255],
        payload=payload or {},
    )


def org_has_active_workflow(organization, trigger_type: str) -> bool:
    from apps.workflows.enums import WorkflowLifecycleStatus

    return CollectionWorkflow.objects.filter(
        organization=organization,
        trigger_type=trigger_type,
        status=WorkflowLifecycleStatus.PUBLISHED,
        is_active=True,
    ).exists()


def _trigger_step(workflow: CollectionWorkflow) -> WorkflowStep | None:
    return (
        workflow.steps.filter(step_type=WorkflowStepType.TRIGGER, is_active=True)
        .order_by("order", "id")
        .first()
    )


def _next_step(step: WorkflowStep, handle: str = WorkflowEdgeHandle.NEXT) -> WorkflowStep | None:
    edge = (
        WorkflowEdge.objects.filter(from_step=step, source_handle=handle)
        .select_related("to_step")
        .first()
    )
    if edge and edge.to_step.is_active:
        return edge.to_step
    # Fallback: linear order for legacy seed without edges
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


def _fail(execution: WorkflowExecution, message: str, step=None):
    execution.status = WorkflowExecutionStatus.FAILED
    execution.error_message = message[:2000]
    execution.completed_at = timezone.now()
    execution.save(
        update_fields=["status", "error_message", "completed_at", "updated_at"]
    )
    _log(execution, step, WorkflowLogEvent.FAILED, message)


def _succeed(execution: WorkflowExecution, step=None):
    execution.status = WorkflowExecutionStatus.SUCCEEDED
    execution.completed_at = timezone.now()
    execution.current_step = None
    execution.resume_at = None
    execution.save(
        update_fields=[
            "status",
            "completed_at",
            "current_step",
            "resume_at",
            "updated_at",
        ]
    )
    _log(execution, step, WorkflowLogEvent.COMPLETED, "completed")


def _run_from_step(execution: WorkflowExecution, step: WorkflowStep | None, *, max_steps: int = 100):
    context = dict(execution.context or {})
    visited = 0
    current = step

    while current is not None and visited < max_steps:
        visited += 1
        execution.current_step = current
        execution.status = WorkflowExecutionStatus.RUNNING
        execution.save(update_fields=["current_step", "status", "updated_at"])

        stype = current.step_type

        if stype == WorkflowStepType.TRIGGER:
            current = _next_step(current, WorkflowEdgeHandle.NEXT)
            continue

        if stype == WorkflowStepType.STOP:
            _succeed(execution, current)
            return execution

        if stype in {WorkflowStepType.CONDITION, WorkflowStepType.BRANCH}:
            matched = evaluate_step_conditions(current, context)
            _log(
                execution,
                current,
                WorkflowLogEvent.CONDITION_MATCH if matched else WorkflowLogEvent.CONDITION_MISS,
                "matched" if matched else "missed",
            )
            if stype == WorkflowStepType.BRANCH:
                handle = WorkflowEdgeHandle.TRUE if matched else WorkflowEdgeHandle.FALSE
                _log(
                    execution,
                    current,
                    WorkflowLogEvent.BRANCH_TAKEN,
                    handle,
                    {"handle": handle},
                )
                current = _next_step(current, handle)
                continue
            # CONDITION: true → next; false → false edge or stop
            if matched:
                if current.stop_on_match:
                    # run next then stop after action chain? For graph, stop_on_match means
                    # follow next then STOP if no further — keep following next.
                    pass
                current = _next_step(current, WorkflowEdgeHandle.NEXT)
            else:
                alt = _next_step(current, WorkflowEdgeHandle.FALSE)
                if alt is None:
                    _succeed(execution, current)
                    return execution
                current = alt
            continue

        if stype == WorkflowStepType.DELAY:
            cfg = current.config or {}
            amount = int(cfg.get("amount") or 0)
            unit = cfg.get("unit") or "business_days"
            if amount <= 0:
                current = _next_step(current, WorkflowEdgeHandle.NEXT)
                continue
            resume_at = compute_resume_at(
                amount=amount,
                unit=unit,
                organization=execution.organization,
            )
            execution.status = WorkflowExecutionStatus.WAITING
            execution.resume_at = resume_at
            execution.current_step = current
            execution.save(
                update_fields=["status", "resume_at", "current_step", "updated_at"]
            )
            _log(
                execution,
                current,
                WorkflowLogEvent.DELAY_SCHEDULED,
                f"resume_at={resume_at.isoformat()}",
                {"resume_at": resume_at.isoformat(), "amount": amount, "unit": unit},
            )
            return execution

        if stype == WorkflowStepType.ACTION:
            # Multiple legacy actions on step
            legacy_actions = list(current.actions.order_by("order", "id"))
            try:
                if legacy_actions and not (current.config or {}).get("action_type"):
                    for la in legacy_actions:
                        result = run_action(
                            execution,
                            current,
                            action_type=la.action_type,
                            params=la.params or {},
                        )
                        if result.waiting:
                            return execution
                else:
                    result = run_action(execution, current)
                    if result.waiting:
                        return execution
            except ActionError as exc:
                _fail(execution, exc.message, current)
                return execution
            except Exception as exc:  # noqa: BLE001
                _fail(execution, str(exc), current)
                return execution
            current = _next_step(current, WorkflowEdgeHandle.NEXT)
            continue

        _log(execution, current, WorkflowLogEvent.STEP_SKIPPED, f"unknown_type:{stype}")
        current = _next_step(current, WorkflowEdgeHandle.NEXT)

    if visited >= max_steps:
        _fail(execution, "max_steps_exceeded", current)
    elif execution.status == WorkflowExecutionStatus.RUNNING:
        _succeed(execution, current)
    return execution


@transaction.atomic
def run_workflow(
    workflow: CollectionWorkflow,
    *,
    customer,
    context: dict[str, Any] | None = None,
    idempotency_key: str,
    trigger_entity_type: str = "",
    trigger_entity_id: str = "",
    invoice=None,
    promise=None,
) -> WorkflowExecution:
    existing = WorkflowExecution.objects.filter(
        organization=workflow.organization,
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        return existing

    # NP-325 — prevent duplicate concurrent execution for same idempotency key
    from django.core.cache import cache

    from apps.ops.locks import lock_key

    wf_lock = lock_key(
        "workflow_execution",
        workflow.organization_id,
        workflow.pk,
        idempotency_key,
    )
    if not cache.add(wf_lock, "1", timeout=600):
        existing = WorkflowExecution.objects.filter(
            organization=workflow.organization,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            return existing

    trigger = _trigger_step(workflow)
    # Legacy workflows without trigger node: start at first step
    start = trigger or workflow.steps.filter(is_active=True).order_by("order", "id").first()

    try:
        execution = WorkflowExecution.objects.create(
            organization=workflow.organization,
            workflow=workflow,
            trigger_type=workflow.trigger_type,
            trigger_entity_type=trigger_entity_type or workflow.trigger_type,
            trigger_entity_id=str(trigger_entity_id or ""),
            customer=customer,
            invoice=invoice,
            promise=promise,
            status=WorkflowExecutionStatus.RUNNING,
            idempotency_key=idempotency_key,
            context=context or {},
            started_at=timezone.now(),
            current_step=start,
        )
    except IntegrityError:
        return WorkflowExecution.objects.get(
            organization=workflow.organization,
            idempotency_key=idempotency_key,
        )

    _log(execution, start, WorkflowLogEvent.STARTED, "started")
    return _run_from_step(execution, start)


def resume_execution(execution: WorkflowExecution) -> WorkflowExecution:
    if execution.status != WorkflowExecutionStatus.WAITING:
        return execution
    step = execution.current_step
    _log(execution, step, WorkflowLogEvent.DELAY_RESUMED, "resumed")
    # After delay/approval, advance to next
    nxt = _next_step(step, WorkflowEdgeHandle.NEXT) if step else None
    execution.status = WorkflowExecutionStatus.RUNNING
    execution.resume_at = None
    execution.save(update_fields=["status", "resume_at", "updated_at"])
    return _run_from_step(execution, nxt)


def dispatch_trigger(
    organization,
    trigger_type: str,
    *,
    customer,
    context: dict[str, Any] | None = None,
    idempotency_key: str,
    trigger_entity_type: str = "",
    trigger_entity_id: str = "",
    invoice=None,
    promise=None,
) -> list[WorkflowExecution]:
    from apps.workflows.enums import WorkflowLifecycleStatus

    workflows = list(
        CollectionWorkflow.objects.filter(
            organization=organization,
            trigger_type=trigger_type,
            is_active=True,
            status=WorkflowLifecycleStatus.PUBLISHED,
        ).order_by("priority", "id")
    )
    results = []
    for wf in workflows:
        key = f"{idempotency_key}:wf:{wf.id}"
        results.append(
            run_workflow(
                wf,
                customer=customer,
                context=context,
                idempotency_key=key,
                trigger_entity_type=trigger_entity_type,
                trigger_entity_id=trigger_entity_id,
                invoice=invoice,
                promise=promise,
            )
        )
    return results


def process_due_resumes(*, limit: int = 100) -> dict[str, int]:
    now = timezone.now()
    qs = (
        WorkflowExecution.objects.filter(
            status=WorkflowExecutionStatus.WAITING,
            resume_at__isnull=False,
            resume_at__lte=now,
        )
        .select_related("workflow", "customer", "current_step", "organization")
        .order_by("resume_at")[:limit]
    )
    processed = 0
    for execution in qs:
        try:
            resume_execution(execution)
            processed += 1
        except Exception:  # noqa: BLE001
            logger.exception("workflow resume failed id=%s", execution.id)
    return {"due": processed, "processed": processed}


def build_invoice_overdue_context(invoice, *, as_of=None) -> dict[str, Any]:
    today = as_of or timezone.localdate()
    overdue_days = max((today - invoice.due_date).days, 0)
    customer = invoice.customer
    return {
        "invoice": {
            "id": invoice.id,
            "status": invoice.status,
            "overdue_days": overdue_days,
            "remaining_amount": float(invoice.remaining_amount()),
            "number": invoice.number,
        },
        "customer": {
            "id": customer.id,
            "risk_level": customer.risk_status,
            "risk_status": customer.risk_status,
            "risk_score": customer.risk_score,
            "tags": list(customer.tags or []),
            "credit_limit": float(customer.credit_limit or 0),
        },
    }


def build_promise_context(promise) -> dict[str, Any]:
    customer = promise.customer
    return {
        "promise": {
            "id": promise.id,
            "status": promise.status,
            "amount": float(promise.amount),
        },
        "customer": {
            "id": customer.id,
            "risk_level": customer.risk_status,
            "risk_status": customer.risk_status,
            "risk_score": customer.risk_score,
            "tags": list(customer.tags or []),
        },
    }
