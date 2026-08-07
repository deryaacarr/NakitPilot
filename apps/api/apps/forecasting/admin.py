from django.contrib import admin

from apps.forecasting.models import ForecastSnapshot


@admin.register(ForecastSnapshot)
class ForecastSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "week_start",
        "week_index",
        "currency",
        "nominal_amount",
        "expected_amount",
        "optimistic_amount",
        "pessimistic_amount",
        "calculated_at",
    )
    list_filter = ("currency", "organization")
    search_fields = ("run_id",)
    readonly_fields = ("calculated_at",)
