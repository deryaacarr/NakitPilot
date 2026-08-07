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
