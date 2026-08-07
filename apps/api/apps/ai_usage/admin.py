from django.contrib import admin

from apps.ai_usage.models import AIUsageEvent, AIUsageLimitConfig


@admin.register(AIUsageEvent)
class AIUsageEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "user",
        "feature",
        "input_tokens",
        "output_tokens",
        "estimated_cost",
        "model",
        "cache_hit",
        "created_at",
    )
    list_filter = ("feature", "model", "cache_hit", "truncated")
    search_fields = ("feature", "model")
    readonly_fields = ("created_at",)


@admin.register(AIUsageLimitConfig)
class AIUsageLimitConfigAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "package",
        "package_monthly_tokens",
        "daily_user_tokens",
        "org_budget_monthly",
        "is_active",
    )
