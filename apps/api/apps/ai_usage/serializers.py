from rest_framework import serializers

from apps.ai_usage.models import AIPackage, AIUsageLimitConfig


class AIUsageLimitConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIUsageLimitConfig
        fields = (
            "id",
            "organization",
            "package",
            "package_monthly_tokens",
            "daily_user_tokens",
            "org_budget_monthly",
            "max_input_chars",
            "cache_ttl_seconds",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class AIUsagePackageUpdateSerializer(serializers.Serializer):
    package = serializers.ChoiceField(choices=AIPackage.choices)
