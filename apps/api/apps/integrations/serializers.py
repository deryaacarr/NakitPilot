from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.integrations.connectors import get as get_connector
from apps.integrations.connectors import known_providers
from apps.integrations.models import ConnectionStatus, IntegrationConnection, IntegrationCredential
from apps.integrations.services import (
    connection_has_credentials,
    set_connection_credentials,
)


SENSITIVE_RESPONSE_KEYS = frozenset(
    {
        "api_key",
        "api_secret",
        "secret",
        "password",
        "access_token",
        "refresh_token",
        "token",
        "encrypted_payload",
        "credentials",
    }
)


class IntegrationConnectionSerializer(serializers.ModelSerializer):
    has_credentials = serializers.SerializerMethodField()
    key_hint = serializers.SerializerMethodField()

    class Meta:
        model = IntegrationConnection
        fields = (
            "id",
            "organization",
            "provider",
            "status",
            "external_company_id",
            "external_company_name",
            "settings_json",
            "last_sync_at",
            "last_successful_sync_at",
            "next_sync_at",
            "sync_frequency",
            "last_error",
            "has_credentials",
            "key_hint",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "last_sync_at",
            "last_successful_sync_at",
            "next_sync_at",
            "last_error",
            "has_credentials",
            "key_hint",
            "created_at",
            "updated_at",
        )

    def get_has_credentials(self, obj: IntegrationConnection) -> bool:
        if hasattr(obj, "_has_credentials"):
            return bool(obj._has_credentials)
        return connection_has_credentials(obj)

    def get_key_hint(self, obj: IntegrationConnection) -> str:
        try:
            credential = obj.credential
        except IntegrationCredential.DoesNotExist:
            return ""
        return credential.key_hint or ""

    def validate_provider(self, value: str) -> str:
        if value not in known_providers():
            raise serializers.ValidationError(f"Unknown integration provider: {value}")
        return value

    def validate_external_company_id(self, value: str) -> str:
        return (value or "").strip()

    def validate_settings_json(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("settings_json must be an object.")
        return value

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "A connection for this provider and external company already exists."
                    ]
                }
            ) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "A connection for this provider and external company already exists."
                    ]
                }
            ) from exc

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key in SENSITIVE_RESPONSE_KEYS:
            data.pop(key, None)
        return data


class IntegrationCredentialWriteSerializer(serializers.Serializer):
    """Accept credentials on write only; never echo secrets back."""

    credentials = serializers.DictField(
        child=serializers.CharField(allow_blank=False, trim_whitespace=True),
        write_only=True,
        allow_empty=False,
    )

    def validate_credentials(self, value: dict) -> dict:
        connection: IntegrationConnection = self.context["connection"]
        connector_cls = get_connector(connection.provider)
        try:
            connector_cls.validate_credentials(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    @transaction.atomic
    def save(self, **kwargs):
        connection: IntegrationConnection = self.context["connection"]
        credential = set_connection_credentials(connection, self.validated_data["credentials"])
        if connection.status == ConnectionStatus.DRAFT:
            connection.status = ConnectionStatus.CONNECTED
            connection.save(update_fields=["status", "updated_at"])
        return credential


class IntegrationCredentialStatusSerializer(serializers.Serializer):
    has_credentials = serializers.BooleanField()
    key_hint = serializers.CharField(allow_blank=True)
    rotated_at = serializers.DateTimeField(allow_null=True)


class ProviderSerializer(serializers.Serializer):
    provider = serializers.CharField()
    display_name = serializers.CharField()


class SelectCompanySerializer(serializers.Serializer):
    external_company_id = serializers.CharField(max_length=128)
    external_company_name = serializers.CharField(max_length=255, required=False, allow_blank=True)


class SyncSettingsSerializer(serializers.Serializer):
    sync_frequency = serializers.ChoiceField(choices=["manual", "hourly", "daily"])
    settings_json = serializers.DictField(required=False)


class StartSyncSerializer(serializers.Serializer):
    job_type = serializers.ChoiceField(
        choices=["initial", "manual", "full"],
        default="manual",
        required=False,
    )


class SyncJobSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    job_type = serializers.CharField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)
    stats_json = serializers.DictField()
    error_message = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class CompanyOptionSerializer(serializers.Serializer):
    external_id = serializers.CharField()
    name = serializers.CharField()
    tax_number = serializers.CharField(allow_blank=True)

class SyncConflictSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.integrations.models import SyncConflict as SyncConflictModel

        model = SyncConflictModel
        fields = (
            "id",
            "connection",
            "job",
            "entity_type",
            "conflict_type",
            "status",
            "external_id",
            "internal_model",
            "internal_id",
            "message",
            "source_payload",
            "local_snapshot",
            "resolution",
            "resolution_detail",
            "resolved_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ResolveConflictSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(
        choices=["use_source", "keep_local", "merge", "skip_field_forever"]
    )
    field = serializers.CharField(required=False, allow_blank=True, default="")

