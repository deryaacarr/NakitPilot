"""Collection workflow definition and execution models (NP-210–214)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.organizations.tenancy import TenantModel
from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowApprovalStatus,
    WorkflowConditionField,
    WorkflowConditionLogic,
    WorkflowConditionOperator,
    WorkflowEdgeHandle,
    WorkflowExecutionStatus,
    WorkflowLifecycleStatus,
    WorkflowLogEvent,
    WorkflowStepType,
    WorkflowTriggerType,
)


class CollectionWorkflow(TenantModel):
    """Named workflow definition scoped to an organization."""

    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    trigger_type = models.CharField(
        max_length=32,
        choices=WorkflowTriggerType.choices,
        db_index=True,
    )
    # NP-216 — Draft / Published / Archived
    status = models.CharField(
        max_length=16,
        choices=WorkflowLifecycleStatus.choices,
        default=WorkflowLifecycleStatus.DRAFT,
        db_index=True,
    )
    # Shared across versions of the same logical workflow.
    workflow_key = models.CharField(max_length=36, db_index=True, default=uuid.uuid4)
    version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_collection_workflows",
    )
    # Back-compat: True iff status == published (kept for existing gates).
    is_active = models.BooleanField(default=False, db_index=True)
    priority = models.PositiveIntegerField(default=100)
    canvas_meta = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_collection_workflows",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("priority", "name", "-version")
        verbose_name = "collection workflow"
        verbose_name_plural = "collection workflows"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "workflow_key", "version"),
                name="uniq_wf_org_key_version",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "trigger_type", "status"),
                name="wf_org_trigger_status_idx",
            ),
            models.Index(
                fields=("organization", "trigger_type", "is_active"),
                name="wf_org_trigger_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} v{self.version} ({self.status})"

    @property
    def is_editable(self) -> bool:
        return self.status == WorkflowLifecycleStatus.DRAFT


class WorkflowStep(TenantModel):
    """Graph node within a workflow (NP-211)."""

    workflow = models.ForeignKey(
        CollectionWorkflow,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    name = models.CharField(max_length=128)
    step_type = models.CharField(
        max_length=16,
        choices=WorkflowStepType.choices,
        default=WorkflowStepType.ACTION,
        db_index=True,
    )
    # Delay / action / expression / trigger filters live here.
    config = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)
    position_x = models.FloatField(default=0)
    position_y = models.FloatField(default=0)
    is_active = models.BooleanField(default=True)
    # Legacy NP-210: stop evaluating later linear steps after match.
    stop_on_match = models.BooleanField(default=False)
    # Stable client key for graph replace (React Flow node id).
    client_key = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "workflow step"
        verbose_name_plural = "workflow steps"
        constraints = [
            models.UniqueConstraint(
                fields=("workflow", "order"),
                name="uniq_wf_step_order",
            )
        ]

    def __str__(self) -> str:
        return f"{self.workflow_id}:{self.order} {self.step_type} {self.name}"


class WorkflowEdge(TenantModel):
    """Directed edge between workflow steps."""

    workflow = models.ForeignKey(
        CollectionWorkflow,
        on_delete=models.CASCADE,
        related_name="edges",
    )
    from_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="out_edges",
    )
    to_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="in_edges",
    )
    source_handle = models.CharField(
        max_length=16,
        choices=WorkflowEdgeHandle.choices,
        default=WorkflowEdgeHandle.NEXT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "workflow edge"
        verbose_name_plural = "workflow edges"
        constraints = [
            models.UniqueConstraint(
                fields=("from_step", "source_handle"),
                name="uniq_wf_edge_from_handle",
            )
        ]

    def __str__(self) -> str:
        return f"{self.from_step_id}-[{self.source_handle}]->{self.to_step_id}"


class WorkflowCondition(TenantModel):
    """Legacy flat condition rows (NP-210); graph steps prefer config.expression."""

    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    field = models.CharField(max_length=64)
    operator = models.CharField(
        max_length=32,
        choices=WorkflowConditionOperator.choices,
        default=WorkflowConditionOperator.GTE,
    )
    value = models.JSONField(default=dict, blank=True)
    logic = models.CharField(
        max_length=8,
        choices=WorkflowConditionLogic.choices,
        default=WorkflowConditionLogic.AND,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "workflow condition"
        verbose_name_plural = "workflow conditions"

    def __str__(self) -> str:
        return f"{self.field} {self.operator} {self.value}"


class WorkflowAction(TenantModel):
    """Legacy action rows; ACTION steps may use config.action_type + config.params."""

    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    action_type = models.CharField(max_length=32, choices=WorkflowActionType.choices)
    params = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "workflow action"
        verbose_name_plural = "workflow actions"

    def __str__(self) -> str:
        return f"{self.action_type}@{self.step_id}"


class WorkflowExecution(TenantModel):
    """One run of a workflow against a trigger entity."""

    workflow = models.ForeignKey(
        CollectionWorkflow,
        on_delete=models.CASCADE,
        related_name="executions",
    )
    trigger_type = models.CharField(
        max_length=32,
        choices=WorkflowTriggerType.choices,
        db_index=True,
    )
    trigger_entity_type = models.CharField(max_length=64)
    trigger_entity_id = models.CharField(max_length=64)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="workflow_executions",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_executions",
    )
    promise = models.ForeignKey(
        "collections.PaymentPromise",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_executions",
    )
    current_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_executions",
    )
    status = models.CharField(
        max_length=16,
        choices=WorkflowExecutionStatus.choices,
        default=WorkflowExecutionStatus.PENDING,
        db_index=True,
    )
    resume_at = models.DateTimeField(null=True, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=255)
    context = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "workflow execution"
        verbose_name_plural = "workflow executions"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"),
                name="uniq_wf_exec_idempotency",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "status", "created_at"),
                name="wf_exec_org_status_idx",
            ),
            models.Index(
                fields=("trigger_entity_type", "trigger_entity_id"),
                name="wf_exec_entity_idx",
            ),
            models.Index(
                fields=("status", "resume_at"),
                name="wf_exec_waiting_resume_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.workflow_id}:{self.idempotency_key} ({self.status})"


class WorkflowExecutionLog(TenantModel):
    """Append-only log lines for a workflow execution."""

    execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_logs",
    )
    action = models.ForeignKey(
        WorkflowAction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_logs",
    )
    event = models.CharField(max_length=32, choices=WorkflowLogEvent.choices)
    message = models.CharField(max_length=255, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = "workflow execution log"
        verbose_name_plural = "workflow execution logs"
        indexes = [
            models.Index(
                fields=("execution", "created_at"),
                name="wf_log_exec_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.execution_id}:{self.event}"


class WorkflowApprovalRequest(TenantModel):
    """Manager approval gate for request_approval actions (NP-213)."""

    execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="approval_requests",
    )
    status = models.CharField(
        max_length=16,
        choices=WorkflowApprovalStatus.choices,
        default=WorkflowApprovalStatus.PENDING,
        db_index=True,
    )
    title = models.CharField(max_length=255, blank=True, default="")
    message = models.TextField(blank=True, default="")
    requested_of = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_approvals_requested",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_approvals_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "workflow approval request"
        verbose_name_plural = "workflow approval requests"

    def __str__(self) -> str:
        return f"approval:{self.execution_id}:{self.status}"


# Silence unused import warnings for field enum used in docs/admin choices elsewhere.
_ = WorkflowConditionField
