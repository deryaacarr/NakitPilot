from django.urls import path

from apps.webhooks.views import (
    WebhookDeliveryDetailView,
    WebhookDeliveryListView,
    WebhookDeliveryResendView,
    WebhookEndpointListCreateView,
    WebhookEndpointTestSendView,
)

urlpatterns = [
    path(
        "endpoints/",
        WebhookEndpointListCreateView.as_view(),
        name="webhook-endpoint-list-create",
    ),
    path(
        "endpoints/<int:pk>/test/",
        WebhookEndpointTestSendView.as_view(),
        name="webhook-endpoint-test",
    ),
    path(
        "deliveries/",
        WebhookDeliveryListView.as_view(),
        name="webhook-delivery-list",
    ),
    path(
        "deliveries/<int:pk>/",
        WebhookDeliveryDetailView.as_view(),
        name="webhook-delivery-detail",
    ),
    path(
        "deliveries/<int:pk>/resend/",
        WebhookDeliveryResendView.as_view(),
        name="webhook-delivery-resend",
    ),
]
