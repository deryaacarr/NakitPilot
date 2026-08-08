from django.urls import path

from apps.organizations.saved_view_views import (
    SavedTableViewByTokenView,
    SavedTableViewDetailView,
    SavedTableViewListCreateView,
    SavedTableViewSetDefaultView,
)

urlpatterns = [
    path("", SavedTableViewListCreateView.as_view(), name="saved-view-list-create"),
    path("by-token/<str:token>/", SavedTableViewByTokenView.as_view(), name="saved-view-by-token"),
    path("<int:pk>/", SavedTableViewDetailView.as_view(), name="saved-view-detail"),
    path(
        "<int:pk>/set-default/",
        SavedTableViewSetDefaultView.as_view(),
        name="saved-view-set-default",
    ),
]
