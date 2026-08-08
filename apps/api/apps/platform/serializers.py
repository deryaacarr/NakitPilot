from rest_framework import serializers

from apps.platform.models import (
    FeatureFlag,
    FeatureFlagKey,
    MaintenanceMode,
    MaintenanceScope,
    MaintenanceWindow,
    SupportTicket,
    SupportTicketStatus,
)


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = (
            "id",
            "key",
            "description",
            "enabled",
            "environments",
            "plan_codes",
            "organization_ids",
            "rollout_percentage",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class FeatureFlagUpsertSerializer(serializers.Serializer):
    key = serializers.ChoiceField(choices=FeatureFlagKey.choices)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    enabled = serializers.BooleanField(required=False, default=False)
    environments = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    plan_codes = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    organization_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    rollout_percentage = serializers.IntegerField(min_value=0, max_value=100, required=False)


class MaintenanceWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceWindow
        fields = (
            "id",
            "scope",
            "mode",
            "organization",
            "module",
            "message",
            "is_active",
            "starts_at",
            "ends_at",
            "created_by",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")


class MaintenanceCreateSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=MaintenanceScope.choices)
    mode = serializers.ChoiceField(choices=MaintenanceMode.choices, default=MaintenanceMode.FULL)
    organization_id = serializers.IntegerField(required=False, allow_null=True)
    module = serializers.CharField(required=False, allow_blank=True, default="")
    message = serializers.CharField(required=False, allow_blank=True, default="")
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, default=True)


class ImpersonationStartSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    organization_id = serializers.IntegerField()
    reason = serializers.CharField(min_length=5)
    duration_minutes = serializers.IntegerField(required=False, min_value=5, max_value=60)
    notify_target = serializers.BooleanField(required=False, default=True)


class SupportTicketSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = SupportTicket
        fields = (
            "id",
            "organization",
            "organization_name",
            "subject",
            "body",
            "status",
            "created_by",
            "assigned_to",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at", "organization_name")


class SupportTicketCreateSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=SupportTicketStatus.choices, required=False, default=SupportTicketStatus.OPEN
    )
