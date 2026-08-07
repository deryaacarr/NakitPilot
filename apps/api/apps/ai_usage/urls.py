from django.urls import path

from apps.ai_usage.views import AIUsageLimitsView, AIUsageSummaryView

urlpatterns = [
    path("summary/", AIUsageSummaryView.as_view(), name="ai-usage-summary"),
    path("limits/", AIUsageLimitsView.as_view(), name="ai-usage-limits"),
]
