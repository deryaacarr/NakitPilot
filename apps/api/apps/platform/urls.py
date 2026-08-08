from django.urls import path

from apps.platform.views import (
    FeatureFlagCheckView,
    FeatureFlagEvaluateView,
    FeatureFlagListUpsertView,
    ImpersonationEndView,
    ImpersonationStartView,
    ImpersonationStatusView,
    MaintenanceDetailView,
    MaintenanceListCreateView,
    MaintenanceStatusView,
    PlatformOverviewView,
    SupportTicketListCreateView,
)

urlpatterns = [
    path("overview/", PlatformOverviewView.as_view(), name="platform-overview"),
    path("feature-flags/", FeatureFlagListUpsertView.as_view(), name="platform-flags"),
    path("feature-flags/evaluate/", FeatureFlagEvaluateView.as_view(), name="platform-flags-eval"),
    path(
        "feature-flags/<str:key>/check/",
        FeatureFlagCheckView.as_view(),
        name="platform-flag-check",
    ),
    path("maintenance/", MaintenanceListCreateView.as_view(), name="platform-maintenance"),
    path(
        "maintenance/<int:pk>/",
        MaintenanceDetailView.as_view(),
        name="platform-maintenance-detail",
    ),
    path(
        "maintenance/status/",
        MaintenanceStatusView.as_view(),
        name="platform-maintenance-status",
    ),
    path(
        "impersonation/start/",
        ImpersonationStartView.as_view(),
        name="platform-impersonation-start",
    ),
    path(
        "impersonation/end/",
        ImpersonationEndView.as_view(),
        name="platform-impersonation-end",
    ),
    path(
        "impersonation/status/",
        ImpersonationStatusView.as_view(),
        name="platform-impersonation-status",
    ),
    path("support-tickets/", SupportTicketListCreateView.as_view(), name="platform-tickets"),
]
