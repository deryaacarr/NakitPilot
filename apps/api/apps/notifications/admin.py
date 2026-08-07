from django.contrib import admin

from apps.notifications.models import DashboardAlert


@admin.register(DashboardAlert)
class DashboardAlertAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "notification_type",
        "severity",
        "category",
        "is_read",
        "organization",
        "created_at",
    )
    list_filter = ("notification_type", "severity", "category", "is_read", "organization")
    search_fields = ("title", "body", "href")
