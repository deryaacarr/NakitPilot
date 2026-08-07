from django.urls import path

from apps.segments.views import (
    ABTestAssignView,
    ABTestDetailView,
    ABTestListCreateView,
    SegmentDetailView,
    SegmentListCreateView,
    SegmentPreviewView,
    StrategyDetailView,
    StrategyListCreateView,
)

urlpatterns = [
    path("", SegmentListCreateView.as_view(), name="segment-list"),
    path("preview/", SegmentPreviewView.as_view(), name="segment-preview"),
    path("strategies/", StrategyListCreateView.as_view(), name="strategy-list"),
    path(
        "strategies/<int:pk>/",
        StrategyDetailView.as_view(),
        name="strategy-detail",
    ),
    path("ab-tests/", ABTestListCreateView.as_view(), name="ab-test-list"),
    path("ab-tests/<int:pk>/", ABTestDetailView.as_view(), name="ab-test-detail"),
    path(
        "ab-tests/<int:pk>/assign/",
        ABTestAssignView.as_view(),
        name="ab-test-assign",
    ),
    path("<int:pk>/", SegmentDetailView.as_view(), name="segment-detail"),
]
