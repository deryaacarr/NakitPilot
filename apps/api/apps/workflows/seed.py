"""Seed example collection workflows as a graph (NP-210/211)."""

from __future__ import annotations

from django.db import transaction

from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowEdgeHandle,
    WorkflowLifecycleStatus,
    WorkflowStepType,
    WorkflowTriggerType,
)
from apps.workflows.models import (
    CollectionWorkflow,
    WorkflowEdge,
    WorkflowStep,
)
from apps.workflows.versioning import new_workflow_key


@transaction.atomic
def seed_default_collection_workflows(*, organization, created_by=None) -> list[CollectionWorkflow]:
    """Create overdue tier + broken-promise graph workflows if missing."""
    created: list[CollectionWorkflow] = []

    overdue, overdue_new = CollectionWorkflow.objects.get_or_create(
        organization=organization,
        name="Gecikmiş fatura tahsilat",
        defaults={
            "description": "7 / 14 / 30 gün gecikme basamakları",
            "trigger_type": WorkflowTriggerType.INVOICE_OVERDUE,
            "status": WorkflowLifecycleStatus.PUBLISHED,
            "workflow_key": new_workflow_key(),
            "version": 1,
            "is_active": True,
            "priority": 10,
            "created_by": created_by,
            "canvas_meta": {"viewport": {"x": 0, "y": 0, "zoom": 1}},
        },
    )
    if overdue_new:
        _seed_overdue_graph(organization, overdue)
        created.append(overdue)

    promise, promise_new = CollectionWorkflow.objects.get_or_create(
        organization=organization,
        name="Ödeme sözü bozulması",
        defaults={
            "description": "Kritik görev + risk yeniden hesaplama",
            "trigger_type": WorkflowTriggerType.PROMISE_BROKEN,
            "status": WorkflowLifecycleStatus.PUBLISHED,
            "workflow_key": new_workflow_key(),
            "version": 1,
            "is_active": True,
            "priority": 5,
            "created_by": created_by,
            "canvas_meta": {"viewport": {"x": 0, "y": 0, "zoom": 1}},
        },
    )
    if promise_new:
        _seed_promise_graph(organization, promise)
        created.append(promise)

    return created


def _edge(organization, workflow, frm: WorkflowStep, to: WorkflowStep, handle: str = WorkflowEdgeHandle.NEXT):
    WorkflowEdge.objects.create(
        organization=organization,
        workflow=workflow,
        from_step=frm,
        to_step=to,
        source_handle=handle,
    )


def _seed_overdue_graph(organization, workflow: CollectionWorkflow) -> None:
    trigger = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Fatura gecikti",
        step_type=WorkflowStepType.TRIGGER,
        order=0,
        position_x=80,
        position_y=200,
        client_key="trigger",
        config={},
    )

    b7 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="7–13 gün mü?",
        step_type=WorkflowStepType.BRANCH,
        order=1,
        position_x=280,
        position_y=80,
        client_key="branch-7",
        config={
            "expression": {
                "all": [
                    {"field": "invoice.overdue_days", "operator": "gte", "value": 7},
                    {"field": "invoice.overdue_days", "operator": "lt", "value": 14},
                ]
            }
        },
    )
    a7 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="E-posta görevi",
        step_type=WorkflowStepType.ACTION,
        order=2,
        position_x=520,
        position_y=40,
        client_key="action-email",
        config={
            "action_type": WorkflowActionType.CREATE_TASK,
            "params": {
                "task_type": "EMAIL",
                "priority": "MEDIUM",
                "title": "Gecikmiş fatura e-posta takibi",
                "source": "OVERDUE_INVOICE",
            },
        },
    )
    stop7 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Dur",
        step_type=WorkflowStepType.STOP,
        order=3,
        position_x=760,
        position_y=40,
        client_key="stop-7",
    )

    b14 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="14–29 gün mü?",
        step_type=WorkflowStepType.BRANCH,
        order=4,
        position_x=280,
        position_y=220,
        client_key="branch-14",
        config={
            "expression": {
                "all": [
                    {"field": "invoice.overdue_days", "operator": "gte", "value": 14},
                    {"field": "invoice.overdue_days", "operator": "lt", "value": 30},
                ]
            }
        },
    )
    a14 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Telefon görevi",
        step_type=WorkflowStepType.ACTION,
        order=5,
        position_x=520,
        position_y=180,
        client_key="action-call",
        config={
            "action_type": WorkflowActionType.CREATE_TASK,
            "params": {
                "task_type": "CALL",
                "priority": "HIGH",
                "title": "Gecikmiş fatura telefon araması",
                "source": "OVERDUE_INVOICE",
            },
        },
    )
    stop14 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Dur",
        step_type=WorkflowStepType.STOP,
        order=6,
        position_x=760,
        position_y=180,
        client_key="stop-14",
    )

    b30 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="30+ gün mü?",
        step_type=WorkflowStepType.BRANCH,
        order=7,
        position_x=280,
        position_y=380,
        client_key="branch-30",
        config={
            "expression": {
                "all": [
                    {"field": "invoice.overdue_days", "operator": "gte", "value": 30},
                ]
            }
        },
    )
    a30 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Kritik takip + finans",
        step_type=WorkflowStepType.ACTION,
        order=8,
        position_x=520,
        position_y=340,
        client_key="action-30-task",
        config={
            "action_type": WorkflowActionType.CREATE_TASK,
            "params": {
                "task_type": "FOLLOW_UP",
                "priority": "CRITICAL",
                "title": "30+ gün gecikmiş fatura",
                "source": "OVERDUE_INVOICE",
            },
        },
    )
    n30 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Finans bildirimi",
        step_type=WorkflowStepType.ACTION,
        order=9,
        position_x=760,
        position_y=340,
        client_key="action-30-notify",
        config={
            "action_type": WorkflowActionType.NOTIFY,
            "params": {
                "severity": "critical",
                "notification_type": "invoice_overdue_escalation",
                "target": "finance_managers",
                "title": "30+ gün gecikmiş fatura",
            },
        },
    )
    stop30 = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Dur",
        step_type=WorkflowStepType.STOP,
        order=10,
        position_x=1000,
        position_y=340,
        client_key="stop-30",
    )
    stop_end = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Uygun değil",
        step_type=WorkflowStepType.STOP,
        order=11,
        position_x=520,
        position_y=480,
        client_key="stop-miss",
    )

    _edge(organization, workflow, trigger, b7)
    _edge(organization, workflow, b7, a7, WorkflowEdgeHandle.TRUE)
    _edge(organization, workflow, b7, b14, WorkflowEdgeHandle.FALSE)
    _edge(organization, workflow, a7, stop7)
    _edge(organization, workflow, b14, a14, WorkflowEdgeHandle.TRUE)
    _edge(organization, workflow, b14, b30, WorkflowEdgeHandle.FALSE)
    _edge(organization, workflow, a14, stop14)
    _edge(organization, workflow, b30, a30, WorkflowEdgeHandle.TRUE)
    _edge(organization, workflow, b30, stop_end, WorkflowEdgeHandle.FALSE)
    _edge(organization, workflow, a30, n30)
    _edge(organization, workflow, n30, stop30)


def _seed_promise_graph(organization, workflow: CollectionWorkflow) -> None:
    trigger = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Ödeme sözü bozuldu",
        step_type=WorkflowStepType.TRIGGER,
        order=0,
        position_x=80,
        position_y=160,
        client_key="trigger",
    )
    cond = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Durum BROKEN mı?",
        step_type=WorkflowStepType.CONDITION,
        order=1,
        position_x=280,
        position_y=160,
        client_key="cond-broken",
        config={
            "expression": {
                "all": [
                    {"field": "promise.status", "operator": "equals", "value": "BROKEN"},
                ]
            }
        },
    )
    task = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Kritik görev",
        step_type=WorkflowStepType.ACTION,
        order=2,
        position_x=500,
        position_y=80,
        client_key="action-task",
        config={
            "action_type": WorkflowActionType.CREATE_TASK,
            "params": {
                "task_type": "CALL",
                "priority": "CRITICAL",
                "title": "Ödeme sözü bozuldu — kritik takip",
                "source": "BROKEN_PROMISE",
            },
        },
    )
    risk = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Risk hesapla",
        step_type=WorkflowStepType.ACTION,
        order=3,
        position_x=720,
        position_y=80,
        client_key="action-risk",
        config={"action_type": WorkflowActionType.RECALCULATE_RISK, "params": {}},
    )
    notify = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Bildirim",
        step_type=WorkflowStepType.ACTION,
        order=4,
        position_x=940,
        position_y=80,
        client_key="action-notify",
        config={
            "action_type": WorkflowActionType.NOTIFY,
            "params": {
                "severity": "critical",
                "notification_type": "promise_broken",
                "target": "assignee",
                "title": "Ödeme sözü bozuldu",
            },
        },
    )
    stop_ok = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Dur",
        step_type=WorkflowStepType.STOP,
        order=5,
        position_x=1160,
        position_y=80,
        client_key="stop",
    )
    stop_miss = WorkflowStep.objects.create(
        organization=organization,
        workflow=workflow,
        name="Atla",
        step_type=WorkflowStepType.STOP,
        order=6,
        position_x=500,
        position_y=260,
        client_key="stop-miss",
    )

    _edge(organization, workflow, trigger, cond)
    _edge(organization, workflow, cond, task, WorkflowEdgeHandle.NEXT)
    _edge(organization, workflow, cond, stop_miss, WorkflowEdgeHandle.FALSE)
    _edge(organization, workflow, task, risk)
    _edge(organization, workflow, risk, notify)
    _edge(organization, workflow, notify, stop_ok)
