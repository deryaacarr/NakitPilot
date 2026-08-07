from django.urls import path

from apps.developers.views import DeveloperDocsView, DeveloperErrorsView, DeveloperUsageView

urlpatterns = [
    path("docs/", DeveloperDocsView.as_view(), name="developer-docs"),
    path("usage/", DeveloperUsageView.as_view(), name="developer-usage"),
    path("errors/", DeveloperErrorsView.as_view(), name="developer-errors"),
]
