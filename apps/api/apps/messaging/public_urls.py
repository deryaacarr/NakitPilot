from django.urls import path

from apps.messaging.views import (
    EmailBounceWebhookView,
    EmailClickRedirectView,
    EmailOpenPixelView,
)

urlpatterns = [
    path(
        "o/<str:token>.gif",
        EmailOpenPixelView.as_view(),
        name="email-open-pixel",
    ),
    path(
        "c/<str:token>/",
        EmailClickRedirectView.as_view(),
        name="email-click-redirect",
    ),
    path(
        "bounce/",
        EmailBounceWebhookView.as_view(),
        name="email-bounce-webhook",
    ),
]
