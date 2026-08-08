"""Impersonation guards + maintenance mode (NP-361 / NP-363)."""

from __future__ import annotations

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from apps.platform.impersonation import get_active_session_from_token, is_sensitive_write
from apps.platform.maintenance import maintenance_state


class PlatformGuardMiddleware(MiddlewareMixin):
    """
    Runs after TenantMiddleware so request.user / organization are available.

    - Attaches request.impersonation_session when JWT has impersonation claims
    - Blocks sensitive financial writes during impersonation
    - Enforces maintenance FULL / READ_ONLY
    """

    def process_request(self, request):
        request.impersonation_session = None
        auth = getattr(request, "auth", None)
        # JWTAuthentication may not have run yet on Django middleware path —
        # TenantMiddleware already authenticated JWT onto request.user/auth.
        session = get_active_session_from_token(auth)
        if session is not None:
            request.impersonation_session = session
            # Ensure org header matches the session organization
            request.organization = session.organization
            request.organization_id_claimed = session.organization_id
            if hasattr(request.user, "current_organization"):
                request.user.current_organization = session.organization

        path = request.path or ""
        method = (request.method or "GET").upper()

        # Platform staff management endpoints bypass maintenance
        if path.startswith("/api/platform/"):
            if session is not None and is_sensitive_write(path, method):
                # platform write endpoints are staff-only; impersonation tokens
                # should not hit them for mutations except end.
                pass
            return None

        # Impersonation sensitive write block
        if session is not None and is_sensitive_write(path, method):
            return JsonResponse(
                {
                    "detail": (
                        "Impersonation sırasında hassas finansal / yazma işlemleri engellenir."
                    ),
                    "code": "impersonation_write_blocked",
                    "session_id": str(session.id),
                },
                status=403,
            )

        state = maintenance_state(
            organization=getattr(request, "organization", None),
            path=path,
        )
        if state is None:
            return None

        if state["mode"] == "FULL":
            # Allow health / status / auth
            if path.startswith("/api/health") or path.startswith("/health") or path.startswith(
                "/api/ops/status"
            ):
                return None
            if path.startswith("/api/auth/"):
                return None
            return JsonResponse(
                {
                    "detail": state["message"],
                    "code": "maintenance_full",
                    "maintenance": state,
                },
                status=503,
            )

        # READ_ONLY — block mutations
        if state["mode"] == "READ_ONLY" and method in {"POST", "PUT", "PATCH", "DELETE"}:
            if path.startswith("/api/auth/") or path.startswith("/api/health"):
                return None
            return JsonResponse(
                {
                    "detail": state["message"] or "Sistem şu an salt okunur modda.",
                    "code": "maintenance_read_only",
                    "maintenance": state,
                },
                status=503,
            )
        return None

    def process_response(self, request, response):
        session = getattr(request, "impersonation_session", None)
        if session is not None:
            response["X-Impersonation"] = "1"
            response["X-Impersonation-Session"] = str(session.id)
            response["X-Impersonation-Expires"] = session.expires_at.isoformat()
        return response
