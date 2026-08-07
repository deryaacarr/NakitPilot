from django.urls import path

from apps.health.views import LiveView, ReadyView

urlpatterns = [
    path("live", LiveView.as_view(), name="health-live"),
    path("live/", LiveView.as_view(), name="health-live-slash"),
    path("ready", ReadyView.as_view(), name="health-ready"),
    path("ready/", ReadyView.as_view(), name="health-ready-slash"),
]
