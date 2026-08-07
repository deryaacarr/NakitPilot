"""Public API pagination + throttling (NP-201)."""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination

from apps.security.throttles import _SettingsRateThrottle


class PublicAPIPagination(PageNumberPagination):
    """Stable pagination contract for /api/v1/*."""

    page_size = 20
    page_size_query_param = "page_size"
    page_query_param = "page"
    max_page_size = 100


class PublicAPIKeyThrottle(_SettingsRateThrottle):
    """Per-API-key rate limit for the public REST surface."""

    scope = "public_api"

    def get_cache_key(self, request, view):
        api_key = getattr(request, "auth", None)
        if api_key is not None and getattr(api_key, "pk", None) is not None:
            ident = f"apikey-{api_key.pk}"
        elif request.user and request.user.is_authenticated:
            ident = f"user-{request.user.pk}"
        else:
            ident = self.get_ident(request) or "anonymous"
        return self.cache_format % {"scope": self.scope, "ident": ident}
