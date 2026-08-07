"""DRF authentication via organization API keys (NP-200)."""

from __future__ import annotations

from rest_framework import authentication, exceptions

from apps.api_keys.services import authenticate_api_key, mark_api_key_used


def extract_api_key_from_request(request) -> str | None:
    header = request.META.get("HTTP_X_API_KEY") or request.headers.get("X-Api-Key")
    if header:
        return header.strip()
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token.startswith("npk_"):
            return token
    return None


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """
    Authenticate with `Authorization: Bearer npk_…` or `X-Api-Key: npk_…`.

    Binds `request.auth` to the ApiKey instance and uses `created_by` as user
    when present (required for IsAuthenticated-compatible views).
    """

    keyword = "Bearer"

    def authenticate(self, request):
        raw = extract_api_key_from_request(request)
        if not raw:
            return None
        api_key = authenticate_api_key(raw)
        if api_key is None:
            raise exceptions.AuthenticationFailed("Geçersiz veya iptal edilmiş API anahtarı.")
        user = api_key.created_by
        if user is None or not user.is_active:
            raise exceptions.AuthenticationFailed("API anahtarı bir kullanıcıya bağlı değil.")
        mark_api_key_used(api_key)
        request.api_key = api_key
        # Ensure tenant helpers see the key's organization.
        request.organization = api_key.organization
        user.current_organization = api_key.organization
        try:
            from apps.billing.models import UsageMetric
            from apps.billing.usage import record_usage

            record_usage(api_key.organization_id, UsageMetric.API_REQUESTS, 1)
        except Exception:  # noqa: BLE001
            pass
        return (user, api_key)

    def authenticate_header(self, request):
        # Enables HTTP 401 (not 403) for unauthenticated requests when this
        # authenticator is listed first in DEFAULT_AUTHENTICATION_CLASSES.
        return self.keyword
