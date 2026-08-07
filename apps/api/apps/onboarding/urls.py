from django.urls import path

from apps.onboarding.views import (
    AnalyticsEventView,
    GuidanceView,
    OnboardingProgressView,
    OnboardingStateView,
    SampleDataView,
)

urlpatterns = [
    path("", OnboardingStateView.as_view(), name="onboarding-state"),
    path("progress/", OnboardingProgressView.as_view(), name="onboarding-progress"),
    path("sample-data/", SampleDataView.as_view(), name="onboarding-sample-data"),
    path("guidance/", GuidanceView.as_view(), name="onboarding-guidance"),
    path("events/", AnalyticsEventView.as_view(), name="onboarding-events"),
]
