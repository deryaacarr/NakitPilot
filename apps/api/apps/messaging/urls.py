from django.urls import path

from apps.messaging.views import (
    EmailProviderConfigView,
    MessageGenerateView,
    MessageTemplateCopyView,
    MessageTemplateDetailView,
    MessageTemplateListCreateView,
    MessageTemplatePreviewView,
    MessageToneListView,
    OutboundEmailApproveView,
    OutboundEmailDetailView,
    OutboundEmailListCreateView,
    OutboundEmailPreviewView,
)
from apps.messaging.whatsapp_views import (
    WhatsAppBulkSendView,
    WhatsAppClassificationOptionsView,
    WhatsAppClassifyView,
    WhatsAppInboundListCreateView,
    WhatsAppOptOutListView,
    WhatsAppOutboundDetailView,
    WhatsAppOutboundListView,
    WhatsAppProviderConfigView,
    WhatsAppSendView,
    WhatsAppStatusUpdateView,
    WhatsAppTemplateDetailView,
    WhatsAppTemplateListCreateView,
)

urlpatterns = [
    path("", MessageTemplateListCreateView.as_view(), name="message-template-list"),
    path("tones/", MessageToneListView.as_view(), name="message-tone-list"),
    path("generate/", MessageGenerateView.as_view(), name="message-generate"),
    path("emails/", OutboundEmailListCreateView.as_view(), name="outbound-email-list"),
    path(
        "emails/<int:pk>/",
        OutboundEmailDetailView.as_view(),
        name="outbound-email-detail",
    ),
    path(
        "emails/<int:pk>/preview/",
        OutboundEmailPreviewView.as_view(),
        name="outbound-email-preview",
    ),
    path(
        "emails/<int:pk>/approve/",
        OutboundEmailApproveView.as_view(),
        name="outbound-email-approve",
    ),
    path(
        "email-provider/",
        EmailProviderConfigView.as_view(),
        name="email-provider-config",
    ),
    # NP-242 / NP-245 WhatsApp
    path(
        "whatsapp/templates/",
        WhatsAppTemplateListCreateView.as_view(),
        name="whatsapp-template-list",
    ),
    path(
        "whatsapp/templates/<int:pk>/",
        WhatsAppTemplateDetailView.as_view(),
        name="whatsapp-template-detail",
    ),
    path("whatsapp/send/", WhatsAppSendView.as_view(), name="whatsapp-send"),
    path(
        "whatsapp/bulk-send/",
        WhatsAppBulkSendView.as_view(),
        name="whatsapp-bulk-send",
    ),
    path(
        "whatsapp/messages/",
        WhatsAppOutboundListView.as_view(),
        name="whatsapp-outbound-list",
    ),
    path(
        "whatsapp/messages/<int:pk>/",
        WhatsAppOutboundDetailView.as_view(),
        name="whatsapp-outbound-detail",
    ),
    path(
        "whatsapp/messages/<int:pk>/status/",
        WhatsAppStatusUpdateView.as_view(),
        name="whatsapp-status-update",
    ),
    path(
        "whatsapp/inbound/",
        WhatsAppInboundListCreateView.as_view(),
        name="whatsapp-inbound-list",
    ),
    path(
        "whatsapp/inbound/<int:pk>/classify/",
        WhatsAppClassifyView.as_view(),
        name="whatsapp-classify",
    ),
    path(
        "whatsapp/classifications/",
        WhatsAppClassificationOptionsView.as_view(),
        name="whatsapp-classification-options",
    ),
    path(
        "whatsapp/opt-outs/",
        WhatsAppOptOutListView.as_view(),
        name="whatsapp-opt-outs",
    ),
    path(
        "whatsapp/provider/",
        WhatsAppProviderConfigView.as_view(),
        name="whatsapp-provider-config",
    ),
    path("<int:pk>/", MessageTemplateDetailView.as_view(), name="message-template-detail"),
    path(
        "<int:pk>/preview/",
        MessageTemplatePreviewView.as_view(),
        name="message-template-preview",
    ),
    path(
        "<int:pk>/copy/",
        MessageTemplateCopyView.as_view(),
        name="message-template-copy",
    ),
]
