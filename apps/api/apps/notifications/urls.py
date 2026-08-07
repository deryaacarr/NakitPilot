from django.urls import path

from apps.notifications.views import (
    DashboardAlertListView,
    DashboardAlertMarkAllReadView,
    DashboardAlertMarkReadView,
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
]
