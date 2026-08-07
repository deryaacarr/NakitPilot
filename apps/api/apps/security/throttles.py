"""NP-151 scoped DRF throttles."""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)


def _rate_for(scope: str) -> str | None:
    rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES") or {}
    return rates.get(scope)


class _SettingsRateThrottle(SimpleRateThrottle):
    """SimpleRateThrottle that reads rates from Django settings (not class snapshot)."""

    def get_rate(self):
        return _rate_for(self.scope)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request) or "anonymous"
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view):
        """Fail open if cache backend is unavailable (e.g. Redis down locally)."""
        try:
            return super().allow_request(request, view)
        except Exception:  # noqa: BLE001 — auth must not 500 when cache is down
            logger.warning("throttle cache unavailable; allowing request scope=%s", self.scope)
            return True


class AuthLoginThrottle(_SettingsRateThrottle):
    scope = "auth_login"


class AuthRefreshThrottle(_SettingsRateThrottle):
    scope = "auth_refresh"


class ImportUploadThrottle(_SettingsRateThrottle):
    scope = "import_upload"
