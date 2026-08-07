from django.urls import path

from apps.dashboard.views import (
    DashboardAgingView,
    DashboardCallListView,
    DashboardOverviewView,
    DashboardPerformanceView,
    DashboardSummaryView,
)

urlpatterns = [
    path("", DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("aging/", DashboardAgingView.as_view(), name="dashboard-aging"),
    path("call-list/", DashboardCallListView.as_view(), name="dashboard-call-list"),
    path("performance/", DashboardPerformanceView.as_view(), name="dashboard-performance"),
]
