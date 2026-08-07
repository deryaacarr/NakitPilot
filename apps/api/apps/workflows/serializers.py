"""Workflow API serializers (NP-211)."""

from rest_framework import serializers

from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowApprovalStatus,
    WorkflowConditionField,
    WorkflowConditionOperator,
    WorkflowLifecycleStatus,
    WorkflowStepType,
    WorkflowTriggerType,
)
from apps.workflows.models import (
    CollectionWorkflow,
    WorkflowApprovalRequest,
    WorkflowExecution,
)
from apps.workflows.services import serialize_graph


class CollectionWorkflowSerializer(serializers.ModelSerializer):
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = CollectionWorkflow
        fields = (
            "id",
            "name",
            "description",
            "trigger_type",
            "status",
            "workflow_key",
            "version",
            "published_at",
            "is_active",
            "priority",
            "canvas_meta",
            "step_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "workflow_key",
            "version",
            "published_at",
            "is_active",
            "created_at",
            "updated_at",
            "step_count",
        )

    def get_step_count(self, obj):
        return obj.steps.count()


class CollectionWorkflowCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    trigger_type = serializers.ChoiceField(choices=WorkflowTriggerType.choices)
    priority = serializers.IntegerField(required=False, default=100)


class WorkflowGraphSerializer(serializers.Serializer):
    steps = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    edges = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    canvas_meta = serializers.DictField(required=False)


class WorkflowDetailSerializer(CollectionWorkflowSerializer):
    graph = serializers.SerializerMethodField()

    class Meta(CollectionWorkflowSerializer.Meta):
        fields = CollectionWorkflowSerializer.Meta.fields + ("graph",)

    def get_graph(self, obj):
        return serialize_graph(obj)


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowExecution
        fields = (
            "id",
            "workflow",
            "trigger_type",
            "trigger_entity_type",
            "trigger_entity_id",
            "customer",
            "invoice",
            "promise",
            "current_step",
            "status",
            "resume_at",
            "idempotency_key",
            "context",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        )


class WorkflowTestRunSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    context = serializers.DictField(required=False, default=dict)
    invoice_id = serializers.IntegerField(required=False, allow_null=True)
    promise_id = serializers.IntegerField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, default="")


class WorkflowApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowApprovalRequest
        fields = (
            "id",
            "execution",
            "step",
            "status",
            "title",
            "message",
            "requested_of",
            "decided_by",
            "decided_at",
            "decision_note",
            "created_at",
        )


class WorkflowApprovalDecideSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "rejected"])
    note = serializers.CharField(required=False, allow_blank=True, default="")


class OrganizationHolidaySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    date = serializers.DateField()
    name = serializers.CharField(required=False, allow_blank=True, default="")


def workflow_meta_payload() -> dict:
    preferred_ops = {
        "equals",
        "not_equals",
        "greater_than",
        "less_than",
        "contains",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
        "gte",
        "lte",
        "eq",
        "ne",
        "gt",
        "lt",
    }
    return {
        "triggers": [{"value": v, "label": str(l)} for v, l in WorkflowTriggerType.choices],
        "step_types": [{"value": v, "label": str(l)} for v, l in WorkflowStepType.choices],
        "action_types": [{"value": v, "label": str(l)} for v, l in WorkflowActionType.choices],
        "operators": [
            {"value": v, "label": str(l)}
            for v, l in WorkflowConditionOperator.choices
            if v in preferred_ops
        ],
        "fields": [{"value": v, "label": str(l)} for v, l in WorkflowConditionField.choices],
        "edge_handles": ["next", "true", "false"],
        "delay_units": ["business_days", "days", "hours"],
        "approval_statuses": [v for v, _ in WorkflowApprovalStatus.choices],
        "lifecycle_statuses": [
            {"value": v, "label": str(l)} for v, l in WorkflowLifecycleStatus.choices
        ],
    }


class WorkflowSimulateSerializer(serializers.Serializer):
    days = serializers.IntegerField(required=False, default=30, min_value=1, max_value=365)
