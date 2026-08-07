"""Shared mixins for public API v1 views."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from apps.api_keys.authentication import ApiKeyAuthentication
from apps.organizations.tenancy import get_request_organization
from apps.public_api.pagination import PublicAPIKeyThrottle, PublicAPIPagination
from apps.public_api.permissions import HasApiKeyScope, IsApiKeyAuthenticated
from apps.public_api.request_logging import PublicAPIRequestLoggingMixin


class PublicAPIViewMixin(PublicAPIRequestLoggingMixin):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsApiKeyAuthenticated, HasApiKeyScope]
    throttle_classes = [PublicAPIKeyThrottle]
    pagination_class = PublicAPIPagination

    def get_organization(self):
        organization = get_request_organization(self.request)
        if organization is None:
            raise PermissionDenied(detail="Organization context is required.")
        user = self.request.user
        if user is not None:
            user.current_organization = organization
        return organization
