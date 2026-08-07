from django.contrib import admin

from apps.governance.models import (
    ApprovalRequest,
    DataAccessEvent,
    DataExportJob,
    DeletionRequest,
    ProcessingInventoryItem,
    RetentionPolicy,
    SSOProviderConfig,
    UserSession,
)


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "action_type", "status", "requested_by", "created_at")
    list_filter = ("status", "action_type")


@admin.register(SSOProviderConfig)
class SSOProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "protocol", "is_enabled")


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "device_label", "ip_address", "last_seen_at", "revoked_at", "is_suspicious")


@admin.register(RetentionPolicy)
class RetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ("organization", "audit_logs_days", "import_files_days", "ai_requests_days")


@admin.register(DataExportJob)
class DataExportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "status", "created_at")


@admin.register(DeletionRequest)
class DeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "target_type", "status", "waiting_until")


@admin.register(DataAccessEvent)
class DataAccessEventAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "resource_type", "resource_id", "created_at")


@admin.register(ProcessingInventoryItem)
class ProcessingInventoryItemAdmin(admin.ModelAdmin):
    list_display = ("field_key", "organization", "data_type", "retention_days")
