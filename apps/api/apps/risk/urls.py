from django.urls import path

from apps.risk.views import (
    RiskModelListView,
    RiskModelPublishView,
    RiskModelTrainView,
    RiskMonitoringDashboardView,
    RiskPredictionListView,
    RiskResolveOutcomesView,
)

urlpatterns = [
    path("models/", RiskModelListView.as_view(), name="risk-model-list"),
    path("models/train/", RiskModelTrainView.as_view(), name="risk-model-train"),
    path(
        "models/<int:pk>/publish/",
        RiskModelPublishView.as_view(),
        name="risk-model-publish",
    ),
    path("predictions/", RiskPredictionListView.as_view(), name="risk-prediction-list"),
    path(
        "predictions/resolve-outcomes/",
        RiskResolveOutcomesView.as_view(),
        name="risk-resolve-outcomes",
    ),
    path("monitoring/", RiskMonitoringDashboardView.as_view(), name="risk-monitoring"),
]
