from django.contrib import admin

from apps.risk.models import RiskModelVersion, RiskPrediction, RiskSnapshot


@admin.register(RiskSnapshot)
class RiskSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "score", "risk_level", "organization", "calculated_at")
    list_filter = ("risk_level", "organization")
    readonly_fields = ("calculated_at",)


@admin.register(RiskPrediction)
class RiskPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "prediction_date",
        "rule_score",
        "model_score",
        "final_score",
        "outcomes_resolved_at",
        "organization",
    )
    list_filter = ("organization", "prediction_date")
    readonly_fields = ("created_at", "outcomes_resolved_at")
    raw_id_fields = ("customer", "snapshot", "model_version")


@admin.register(RiskModelVersion)
class RiskModelVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "version",
        "algorithm",
        "status",
        "target_label",
        "trained_at",
        "published_at",
        "organization",
    )
    list_filter = ("status", "algorithm", "organization")
    readonly_fields = ("created_at", "updated_at", "trained_at", "published_at")
