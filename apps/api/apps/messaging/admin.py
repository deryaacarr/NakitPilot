from django.contrib import admin

from apps.messaging.models import MessageTemplate


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "channel", "is_default", "organization", "created_at")
    list_filter = ("channel", "is_default", "organization")
    search_fields = ("name", "subject", "body")
