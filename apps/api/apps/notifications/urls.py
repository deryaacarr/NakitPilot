from django.urls import path

from apps.notifications.views import (
    DashboardAlertListView,
    DashboardAlertMarkAllReadView,
    DashboardAlertMarkReadView,
    NotificationPreferenceView,
    PushSubscribeView,
    PushUnsubscribeView,
    PushVapidPublicKeyView,
)

urlpatterns = [
    path("alerts/", DashboardAlertListView.as_view(), name="dashboard-alert-list"),
    path(
        "alerts/read-all/",
        DashboardAlertMarkAllReadView.as_view(),
        name="dashboard-alert-mark-all-read",
    ),
    path(
        "alerts/<int:pk>/read/",
        DashboardAlertMarkReadView.as_view(),
        name="dashboard-alert-mark-read",
    ),
    path(
        "preferences/",
        NotificationPreferenceView.as_view(),
        name="notification-preferences",
    ),
    path("push/subscribe/", PushSubscribeView.as_view(), name="push-subscribe"),
    path("push/unsubscribe/", PushUnsubscribeView.as_view(), name="push-unsubscribe"),
    path("push/vapid-public-key/", PushVapidPublicKeyView.as_view(), name="push-vapid-key"),
]
