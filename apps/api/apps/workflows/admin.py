from django.contrib import admin

from apps.workflows.models import (
    CollectionWorkflow,
    WorkflowAction,
    WorkflowApprovalRequest,
    WorkflowCondition,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowStep,
)


class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 0
    show_change_link = True
    fields = ("name", "step_type", "order", "client_key", "is_active")


@admin.register(CollectionWorkflow)
class CollectionWorkflowAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "trigger_type", "is_active", "priority", "created_at")
    list_filter = ("trigger_type", "is_active")
    search_fields = ("name",)
    inlines = [WorkflowStepInline]


class WorkflowConditionInline(admin.TabularInline):
    model = WorkflowCondition
    extra = 0


class WorkflowActionInline(admin.TabularInline):
    model = WorkflowAction
    extra = 0


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ("name", "workflow", "step_type", "order", "is_active")
    list_filter = ("step_type", "is_active")
    inlines = [WorkflowConditionInline, WorkflowActionInline]


@admin.register(WorkflowEdge)
class WorkflowEdgeAdmin(admin.ModelAdmin):
    list_display = ("workflow", "from_step", "source_handle", "to_step")


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "workflow",
        "organization",
        "trigger_type",
        "status",
        "resume_at",
        "idempotency_key",
        "created_at",
    )
    list_filter = ("status", "trigger_type")
    search_fields = ("idempotency_key", "trigger_entity_id")


@admin.register(WorkflowExecutionLog)
class WorkflowExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "execution", "event", "message", "created_at")
    list_filter = ("event",)


@admin.register(WorkflowApprovalRequest)
class WorkflowApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "execution", "status", "requested_of", "decided_by", "created_at")
    list_filter = ("status",)
