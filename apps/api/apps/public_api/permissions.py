"""API key scope permissions for the public API (NP-201)."""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.api_keys.models import ApiKey


class IsApiKeyAuthenticated(BasePermission):
    """Require authentication via an active organization API key."""

    message = "Public API requires a valid API key (Authorization: Bearer npk_… or X-Api-Key)."

    def has_permission(self, request, view) -> bool:
        api_key = getattr(request, "auth", None)
        if not isinstance(api_key, ApiKey):
            return False
        if api_key.revoked_at is not None:
            return False
        return True


class HasApiKeyScope(BasePermission):
    """
    Enforce scopes declared on the view.

    Set `required_scopes` (list/str), or `read_scopes` / `write_scopes`.
    """

    message = "API anahtarında gerekli yetki alanı yok."

    def has_permission(self, request, view) -> bool:
        api_key = getattr(request, "auth", None)
        if not isinstance(api_key, ApiKey):
            self.message = "Public API requires a valid API key."
            return False
        if api_key.revoked_at is not None:
            return False

        scopes = getattr(view, "required_scopes", None)
        if scopes is None:
            if request.method in SAFE_METHODS:
                scopes = getattr(view, "read_scopes", [])
            else:
                scopes = getattr(view, "write_scopes", [])
        if isinstance(scopes, str):
            scopes = [scopes]
        scopes = list(scopes or [])
        if not scopes:
            return False
        return any(api_key.has_scope(scope) for scope in scopes)
