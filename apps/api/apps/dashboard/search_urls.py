from django.urls import path

from apps.dashboard.search import GlobalSearchView

urlpatterns = [
    path("", GlobalSearchView.as_view(), name="global-search"),
]
