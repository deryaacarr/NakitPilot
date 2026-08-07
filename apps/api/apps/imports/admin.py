from django.contrib import admin

from apps.imports.models import ImportError, ImportJob


class ImportErrorInline(admin.TabularInline):
    model = ImportError
    extra = 0
    readonly_fields = (
        "row_number",
        "field_name",
        "raw_value",
        "error_message",
        "kind",
        "created_at",
    )


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "import_type",
        "status",
        "duplicate_policy",
        "organization",
        "successful_rows",
        "failed_rows",
        "skipped_duplicates",
        "created_at",
    )
    list_filter = ("status", "import_type", "duplicate_policy", "organization")
    search_fields = ("original_filename", "file_hash", "celery_task_id")
    readonly_fields = ("file_hash", "stored_path", "celery_task_id", "created_at", "updated_at")
    inlines = [ImportErrorInline]


@admin.register(ImportError)
class ImportErrorAdmin(admin.ModelAdmin):
    list_display = ("job", "row_number", "field_name", "kind", "error_message", "organization")
    list_filter = ("organization", "kind")
