from rest_framework import serializers

from apps.webhooks.events import ALL_EVENT_TYPES
from apps.webhooks.models import WebhookAttempt, WebhookDelivery, WebhookEndpoint, WebhookSubscription


class WebhookAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookAttempt
        fields = (
            "id",
            "attempt_number",
            "request_url",
            "response_status",
            "response_body",
            "error_message",
            "duration_ms",
            "success",
            "created_at",
        )
        read_only_fields = fields


class WebhookDeliverySerializer(serializers.ModelSerializer):
    endpoint_name = serializers.CharField(source="endpoint.name", read_only=True)
    endpoint_url = serializers.URLField(source="endpoint.url", read_only=True)
    attempts = WebhookAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = (
            "id",
            "public_id",
            "endpoint",
            "endpoint_name",
            "endpoint_url",
            "event_type",
            "event_id",
            "payload",
            "status",
            "attempt_count",
            "max_attempts",
            "next_attempt_at",
            "last_error",
            "created_at",
            "updated_at",
            "completed_at",
            "attempts",
        )
        read_only_fields = fields


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ("id", "event_type", "is_active", "created_at")
        read_only_fields = fields


class WebhookEndpointSerializer(serializers.ModelSerializer):
    subscriptions = WebhookSubscriptionSerializer(many=True, read_only=True)

    class Meta:
        model = WebhookEndpoint
        fields = (
            "id",
            "name",
            "url",
            "description",
            "secret_hint",
            "is_active",
            "consecutive_failures",
            "last_success_at",
            "last_failure_at",
            "created_at",
            "updated_at",
            "subscriptions",
        )
        read_only_fields = fields


class WebhookEndpointCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    url = serializers.URLField(max_length=2048)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    event_types = serializers.ListField(
        child=serializers.ChoiceField(choices=[(e, e) for e in ALL_EVENT_TYPES]),
        required=False,
        default=list,
    )


class WebhookTestSendSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=[(e, e) for e in ALL_EVENT_TYPES])
    payload = serializers.DictField(required=False)
