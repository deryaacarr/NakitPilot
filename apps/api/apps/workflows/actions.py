"""Workflow action registry (NP-213)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowApprovalStatus,
    WorkflowExecutionStatus,
    WorkflowLogEvent,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class ActionResult:
    ok: bool = True
    waiting: bool = False
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class ActionError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _log(execution, step, event: str, message: str = "", payload: dict | None = None):
    from apps.workflows.models import WorkflowExecutionLog

    WorkflowExecutionLog.objects.create(
        organization=execution.organization,
        execution=execution,
        step=step,
        event=event,
        message=(message or "")[:255],
        payload=payload or {},
    )


def _resolve_finance_managers(organization):
    from apps.organizations.models import Membership, Role

    return list(
        User.objects.filter(
            id__in=Membership.objects.filter(
                organization=organization,
                role=Role.FINANCE_MANAGER,
                is_active=True,
            ).values_list("user_id", flat=True),
            is_active=True,
        )
    )


def action_create_task(execution, step, params: dict, context: dict) -> ActionResult:
    from apps.collections.models import CollectionTaskSource, CollectionTaskType
    from apps.collections.services import create_task

    task_type = params.get("task_type") or CollectionTaskType.CALL
    source = params.get("source") or CollectionTaskSource.MANUAL
    due = timezone.localdate()
    if params.get("due_in_days") is not None:
        due = due + timedelta(days=int(params["due_in_days"]))

    assigned_to = None
    if params.get("assigned_to_id"):
        assigned_to = User.objects.filter(pk=params["assigned_to_id"]).first()

    task = create_task(
        organization=execution.organization,
        customer=execution.customer,
        due_date=due,
        title=params.get("title") or f"Workflow — {execution.customer.name}",
        description=params.get("description") or "",
        task_type=task_type,
        assigned_to=assigned_to,
        invoice=execution.invoice,
        related_promise=execution.promise,
        source=source,
    )
    return ActionResult(ok=True, message="task_created", payload={"task_id": task.id})


def action_assign_user(execution, step, params: dict, context: dict) -> ActionResult:
    from apps.collections.models import CollectionTask, CollectionTaskStatus

    user_id = params.get("user_id") or params.get("assigned_to_id")
    if not user_id:
        raise ActionError("user_id required")
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        raise ActionError("user_not_found")

    target = params.get("target") or "customer"
    if target == "customer":
        execution.customer.assigned_user = user
        execution.customer.save(update_fields=["assigned_user", "updated_at"])
        return ActionResult(ok=True, payload={"assigned_user_id": user.id, "target": "customer"})

    task_id = params.get("task_id")
    qs = CollectionTask.objects.filter(
        organization=execution.organization,
        customer=execution.customer,
        status__in=[CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS],
    )
    if task_id:
        qs = qs.filter(pk=task_id)
    updated = qs.update(assigned_to=user)
    return ActionResult(ok=True, payload={"assigned_user_id": user.id, "tasks_updated": updated})


def action_notify(execution, step, params: dict, context: dict) -> ActionResult:
    from apps.notifications.models import AlertSeverity, create_dashboard_alert

    target = (params.get("target") or "assignee").lower()
    title = params.get("title") or f"Workflow: {execution.workflow.name}"
    body = params.get("body") or params.get("message") or ""
    severity = params.get("severity") or AlertSeverity.WARNING
    ntype = params.get("notification_type") or "WORKFLOW"

    recipients = []
    if target == "assignee" and execution.customer.assigned_user_id:
        recipients = [execution.customer.assigned_user]
    elif target == "finance_managers":
        recipients = _resolve_finance_managers(execution.organization)
    elif target == "user" and params.get("user_id"):
        u = User.objects.filter(pk=params["user_id"]).first()
        recipients = [u] if u else []
    else:
        recipients = [None]  # org-wide alert

    created_ids = []
    for recipient in recipients or [None]:
        alert = create_dashboard_alert(
            organization=execution.organization,
            title=title,
            body=body,
            severity=severity,
            notification_type=ntype,
            category="workflow",
            entity_type="WorkflowExecution",
            entity_id=execution.id,
            created_for=recipient,
        )
        created_ids.append(alert.id)
    return ActionResult(ok=True, payload={"alert_ids": created_ids})


def action_prepare_email(execution, step, params: dict, context: dict) -> ActionResult:
    from apps.messaging.models import MessageTemplate
    from apps.messaging.services import preview_template

    template_id = params.get("template_id")
    if not template_id:
        subject = params.get("subject") or ""
        body = params.get("body") or ""
        draft = {"subject": subject, "body": body, "queued": False}
        context.setdefault("email_drafts", []).append(draft)
        execution.context = {**(execution.context or {}), **context}
        execution.save(update_fields=["context", "updated_at"])
        return ActionResult(ok=True, message="email_prepared", payload=draft)

    template = MessageTemplate.objects.filter(
        pk=template_id, organization=execution.organization
    ).first()
    if template is None:
        raise ActionError("template_not_found")
    preview = preview_template(
        template,
        customer_id=execution.customer_id,
        invoice_id=execution.invoice_id,
    )
    draft = {
        "template_id": template.id,
        "subject": preview.get("subject"),
        "body": preview.get("body"),
        "queued": False,
    }
    drafts = list((execution.context or {}).get("email_drafts") or [])
    drafts.append(draft)
    execution.context = {**(execution.context or {}), "email_drafts": drafts}
    execution.save(update_fields=["context", "updated_at"])
    return ActionResult(ok=True, message="email_prepared", payload=draft)


def action_send_email(execution, step, params: dict, context: dict) -> ActionResult:
    """Prepare outbound email; queue only after explicit approval unless auto_approve."""
    prepared = action_prepare_email(execution, step, params, context)
    if not prepared.ok:
        return prepared
    from apps.messaging.email_service import approve_outbound_email, create_email_draft

    template_id = params.get("template_id")
    auto_approve = bool(params.get("auto_approve", False))
    try:
        email = create_email_draft(
            organization=execution.organization,
            customer_id=execution.customer_id,
            template_id=template_id,
            invoice_id=execution.invoice_id,
            subject=prepared.payload.get("subject") or "",
            body=prepared.payload.get("body") or "",
            require_approval=not auto_approve,
        )
    except Exception as exc:  # noqa: BLE001
        raise ActionError(str(exc)) from exc

    payload = {
        "outbound_email_id": email.id,
        "status": email.status,
        "queued": False,
        "sent": False,
        "requires_approval": not auto_approve,
    }
    if auto_approve:
        approve_outbound_email(email, actor=None, confirmed=True, queue_send=True)
        email.refresh_from_db()
        payload["status"] = email.status
        payload["queued"] = email.status in {"QUEUED", "SENDING", "SENT"}
        payload["sent"] = email.status == "SENT"
    return ActionResult(ok=True, message="email_queued", payload=payload)


def action_recalculate_risk(execution, step, params: dict, context: dict) -> ActionResult:
    from apps.risk.services import calculate_customer_risk

    result = calculate_customer_risk(execution.customer_id)
    payload = result if isinstance(result, dict) else {"result": str(result)}
    return ActionResult(ok=True, message="risk_recalculated", payload=payload)


def action_add_tag(execution, step, params: dict, context: dict) -> ActionResult:
    tag = (params.get("tag") or "").strip()
    if not tag:
        raise ActionError("tag required")
    customer = execution.customer
    tags = list(customer.tags or [])
    if tag not in tags:
        tags.append(tag)
        customer.tags = tags
        customer.save(update_fields=["tags", "updated_at"])
    return ActionResult(ok=True, payload={"tags": tags})


def action_change_assignee(execution, step, params: dict, context: dict) -> ActionResult:
    return action_assign_user(
        execution,
        step,
        {**params, "target": "customer"},
        context,
    )


def action_trigger_webhook(execution, step, params: dict, context: dict) -> ActionResult:
    from apps.webhooks.delivery import enqueue_event

    event_type = params.get("event_type") or "workflow.triggered"
    event_id = params.get("event_id") or f"wf-exec-{execution.id}-{step.id}"
    payload = params.get("payload") or {
        "execution_id": execution.id,
        "workflow_id": execution.workflow_id,
        "customer_id": execution.customer_id,
        "context": execution.context,
    }
    deliveries = enqueue_event(
        organization=execution.organization,
        event_type=event_type,
        event_id=str(event_id),
        payload=payload,
        process_async=True,
    )
    return ActionResult(
        ok=True,
        payload={"delivery_ids": [d.id for d in deliveries], "event_type": event_type},
    )


def action_request_approval(execution, step, params: dict, context: dict) -> ActionResult:
    from apps.organizations.models import Membership, Role
    from apps.workflows.models import WorkflowApprovalRequest

    requested_of = None
    if params.get("user_id"):
        requested_of = User.objects.filter(pk=params["user_id"]).first()
    else:
        # Prefer finance manager / owner
        mid = (
            Membership.objects.filter(
                organization=execution.organization,
                role__in=[Role.FINANCE_MANAGER, Role.OWNER, Role.ADMIN],
                is_active=True,
            )
            .order_by("id")
            .values_list("user_id", flat=True)
            .first()
        )
        if mid:
            requested_of = User.objects.filter(pk=mid).first()

    approval = WorkflowApprovalRequest.objects.create(
        organization=execution.organization,
        execution=execution,
        step=step,
        status=WorkflowApprovalStatus.PENDING,
        title=params.get("title") or f"Onay: {execution.workflow.name}",
        message=params.get("message") or params.get("body") or "",
        requested_of=requested_of,
    )
    execution.status = WorkflowExecutionStatus.WAITING
    execution.current_step = step
    execution.resume_at = None  # waits for human decision
    execution.save(update_fields=["status", "current_step", "resume_at", "updated_at"])
    _log(
        execution,
        step,
        WorkflowLogEvent.APPROVAL_REQUESTED,
        "approval requested",
        {"approval_id": approval.id},
    )
    return ActionResult(
        ok=True,
        waiting=True,
        message="approval_requested",
        payload={"approval_id": approval.id},
    )


ACTION_HANDLERS: dict[str, Callable[..., ActionResult]] = {
    WorkflowActionType.CREATE_TASK: action_create_task,
    WorkflowActionType.ASSIGN_USER: action_assign_user,
    WorkflowActionType.NOTIFY: action_notify,
    WorkflowActionType.PREPARE_EMAIL: action_prepare_email,
    WorkflowActionType.SEND_EMAIL: action_send_email,
    WorkflowActionType.RECALCULATE_RISK: action_recalculate_risk,
    WorkflowActionType.ADD_TAG: action_add_tag,
    WorkflowActionType.CHANGE_ASSIGNEE: action_change_assignee,
    WorkflowActionType.TRIGGER_WEBHOOK: action_trigger_webhook,
    WorkflowActionType.REQUEST_APPROVAL: action_request_approval,
}


def run_action(execution, step, *, action_type: str | None = None, params: dict | None = None) -> ActionResult:
    cfg = step.config or {}
    atype = action_type or cfg.get("action_type")
    apars = params if params is not None else (cfg.get("params") or {})

    # Legacy WorkflowAction rows
    if not atype:
        legacy = step.actions.order_by("order", "id").first()
        if legacy:
            atype = legacy.action_type
            apars = legacy.params or {}

    if not atype:
        raise ActionError("action_type missing")

    handler = ACTION_HANDLERS.get(atype)
    if handler is None:
        raise ActionError(f"unknown_action:{atype}")

    on_error = (cfg.get("on_error") or "fail").lower()
    try:
        result = handler(execution, step, apars or {}, dict(execution.context or {}))
        _log(
            execution,
            step,
            WorkflowLogEvent.ACTION_OK if result.ok else WorkflowLogEvent.ACTION_FAIL,
            result.message,
            result.payload,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        msg = getattr(exc, "message", str(exc))
        _log(execution, step, WorkflowLogEvent.ACTION_FAIL, msg, {"error": msg})
        if on_error == "continue":
            return ActionResult(ok=False, message=msg)
        raise
