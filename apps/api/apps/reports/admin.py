from django.contrib import admin

from apps.reports.models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "report_type",
        "status",
        "row_count",
        "organization",
        "requested_by",
        "created_at",
        "expires_at",
    )
    list_filter = ("report_type", "status", "organization")
    search_fields = ("original_filename", "error_message")
    readonly_fields = ("created_at", "updated_at", "completed_at", "celery_task_id")
