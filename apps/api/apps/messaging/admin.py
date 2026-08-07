from django.contrib import admin

from apps.messaging.models import (
    InboundWhatsApp,
    MessageTemplate,
    OutboundWhatsApp,
    WhatsAppApprovedTemplate,
    WhatsAppOptOut,
)


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "channel", "is_default", "organization", "created_at")
    list_filter = ("channel", "is_default", "organization")
    search_fields = ("name", "subject", "body")


@admin.register(WhatsAppApprovedTemplate)
class WhatsAppApprovedTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "language_code", "status", "organization")
    list_filter = ("status", "organization")
    search_fields = ("name", "body")


@admin.register(OutboundWhatsApp)
class OutboundWhatsAppAdmin(admin.ModelAdmin):
    list_display = ("id", "to_phone", "status", "is_automatic", "customer", "sent_at")
    list_filter = ("status", "is_automatic")


@admin.register(InboundWhatsApp)
class InboundWhatsAppAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "from_phone",
        "customer",
        "classification",
        "classification_confirmed",
        "received_at",
    )
    list_filter = ("classification_confirmed", "opt_out_detected")


@admin.register(WhatsAppOptOut)
class WhatsAppOptOutAdmin(admin.ModelAdmin):
    list_display = ("id", "phone", "customer", "is_active", "opted_out_at")
    list_filter = ("is_active",)
