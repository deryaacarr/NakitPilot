from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "entity_type", "entity_id", "actor", "organization", "created_at")
    list_filter = ("action", "entity_type", "organization")
    search_fields = ("entity_id", "summary")
    readonly_fields = ("created_at",)
