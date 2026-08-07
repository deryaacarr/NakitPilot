from django.urls import path

from apps.api_keys.views import (
    ApiKeyDetailView,
    ApiKeyListCreateView,
    ApiKeyRevokeView,
    ApiKeyScopeListView,
)

urlpatterns = [
    path("scopes/", ApiKeyScopeListView.as_view(), name="api-key-scopes"),
    path("", ApiKeyListCreateView.as_view(), name="api-key-list-create"),
    path("<int:pk>/", ApiKeyDetailView.as_view(), name="api-key-detail"),
    path("<int:pk>/revoke/", ApiKeyRevokeView.as_view(), name="api-key-revoke"),
]
