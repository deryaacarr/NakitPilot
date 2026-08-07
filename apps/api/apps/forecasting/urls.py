from django.urls import path

from apps.forecasting.scenario_views import (
    CashGapAlertView,
    ForecastAccuracyView,
    ScenarioRunView,
    ScenarioTypeListView,
    WhatIfView,
)
from apps.forecasting.views import CashFlowForecastView

urlpatterns = [
    path("cash-flow", CashFlowForecastView.as_view(), name="forecast-cash-flow"),
    path("cash-flow/", CashFlowForecastView.as_view(), name="forecast-cash-flow-slash"),
    path("scenarios/types/", ScenarioTypeListView.as_view(), name="scenario-types"),
    path("scenarios/run/", ScenarioRunView.as_view(), name="scenario-run"),
    path("what-if/", WhatIfView.as_view(), name="forecast-what-if"),
    path("cash-gap-alerts/", CashGapAlertView.as_view(), name="cash-gap-alerts"),
    path("accuracy/", ForecastAccuracyView.as_view(), name="forecast-accuracy"),
]
