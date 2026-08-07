from django.urls import path

from apps.ops.views import (
    AlertEvaluateView,
    AlertEventsView,
    AlertRulesView,
    ArchiveView,
    BusinessMetricsView,
    LoadTestView,
    RefreshReadModelView,
    RunbookDetailView,
    RunbookListView,
    StatusPageView,
    TechnicalMetricsView,
)

urlpatterns = [
    path("metrics/technical/", TechnicalMetricsView.as_view(), name="ops-tech-metrics"),
    path("metrics/business/", BusinessMetricsView.as_view(), name="ops-biz-metrics"),
    path("alerts/rules/", AlertRulesView.as_view(), name="ops-alert-rules"),
    path("alerts/evaluate/", AlertEvaluateView.as_view(), name="ops-alert-evaluate"),
    path("alerts/events/", AlertEventsView.as_view(), name="ops-alert-events"),
    path("status/", StatusPageView.as_view(), name="ops-status"),
    path("archive/", ArchiveView.as_view(), name="ops-archive"),
    path("loadtest/", LoadTestView.as_view(), name="ops-loadtest"),
    path("read-models/refresh/", RefreshReadModelView.as_view(), name="ops-readmodel-refresh"),
    path("runbooks/", RunbookListView.as_view(), name="ops-runbooks"),
    path("runbooks/<str:key>/", RunbookDetailView.as_view(), name="ops-runbook-detail"),
]
