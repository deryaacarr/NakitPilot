from django.urls import path

from apps.forecasting.views import CashFlowForecastView

urlpatterns = [
    path("cash-flow", CashFlowForecastView.as_view(), name="forecast-cash-flow"),
    path("cash-flow/", CashFlowForecastView.as_view(), name="forecast-cash-flow-slash"),
]
