"""Resolve and bind the active organization for each request."""

from __future__ import annotations

from apps.organizations.services import get_active_membership

ORGANIZATION_HEADER = "HTTP_X_ORGANIZATION_ID"


def _authenticate_jwt(request) -> None:
    """Authenticate Bearer JWT early so tenant binding works for API requests."""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return
    token = auth_header[7:].strip()
    # Organization API keys use npk_… — handled separately.
    if token.startswith("npk_"):
        return
    if getattr(request.user, "is_authenticated", False):
        return
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication

        result = JWTAuthentication().authenticate(request)
    except Exception:
        return
    if result is not None:
        request.user, request.auth = result


def _authenticate_api_key(request) -> bool:
    """
    Authenticate organization API keys (NP-200) and bind tenant from the key.

    Returns True when an API key authenticated the request.
    """
    if getattr(request.user, "is_authenticated", False):
        return False
    try:
        from apps.api_keys.authentication import ApiKeyAuthentication
    except Exception:
        return False
    try:
        result = ApiKeyAuthentication().authenticate(request)
    except Exception:
        return False
    if result is None:
        return False
    request.user, request.auth = result
    return True


def _parse_organization_id(request) -> int | None:
    raw = request.META.get(ORGANIZATION_HEADER)
    if raw in (None, ""):
        raw = request.GET.get("organization_id")
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class TenantMiddleware:
    """
    Bind `request.organization`, `request.membership`, and
    `request.user.current_organization` for the active tenant.

    Tenant context comes from `X-Organization-Id` (preferred) or
    `organization_id` query param. Without a valid membership the
    organization context stays unset and tenant views must deny access.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _authenticate_jwt(request)
        api_key_auth = _authenticate_api_key(request)

        request.organization = None
        request.membership = None
        request.organization_id_claimed = _parse_organization_id(request)

        user = getattr(request, "user", None)

        if api_key_auth and getattr(request, "auth", None) is not None:
            org = getattr(request.auth, "organization", None)
            if org is not None:
                if (
                    request.organization_id_claimed is not None
                    and request.organization_id_claimed != org.pk
                ):
                    if user is not None:
                        user.current_organization = None
                else:
                    request.organization = org
                    if user is not None:
                        user.current_organization = org
                        request.membership = get_active_membership(user, org.pk)
        elif user is not None and getattr(user, "is_authenticated", False):
            membership = None
            if request.organization_id_claimed is not None:
                membership = get_active_membership(user, request.organization_id_claimed)
            if membership is not None:
                request.membership = membership
                request.organization = membership.organization
                user.current_organization = membership.organization
            else:
                user.current_organization = None
        elif user is not None:
            user.current_organization = None

        try:
            from config.sentry import set_request_sentry_scope

            set_request_sentry_scope(request)
        except Exception:
            pass

        return self.get_response(request)
