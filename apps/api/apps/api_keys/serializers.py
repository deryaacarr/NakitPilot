from rest_framework import serializers

from apps.api_keys.models import ApiKey
from apps.api_keys.scopes import AVAILABLE_SCOPES


class ApiKeySerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    display_prefix = serializers.CharField(read_only=True)
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ApiKey
        fields = (
            "id",
            "name",
            "display_prefix",
            "prefix",
            "scopes",
            "is_active",
            "last_used_at",
            "revoked_at",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_created_by_email(self, obj: ApiKey) -> str:
        if obj.created_by_id and obj.created_by:
            return obj.created_by.email
        return ""


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=[(s, s) for s in AVAILABLE_SCOPES]),
        allow_empty=False,
    )
