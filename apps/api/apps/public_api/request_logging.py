"""Record public API requests for the developer portal (NP-206)."""

from __future__ import annotations

import logging
import time

from apps.api_keys.models import ApiKey, ApiRequestLog
from apps.organizations.tenancy import get_request_organization

logger = logging.getLogger(__name__)


def log_public_api_request(request, response, *, duration_ms: int | None = None) -> None:
    try:
        organization = get_request_organization(request)
        if organization is None:
            return
        api_key = request.auth if isinstance(getattr(request, "auth", None), ApiKey) else None
        path = (getattr(request, "path", "") or "")[:512]
        method = (getattr(request, "method", "") or "GET")[:16]
        status_code = int(getattr(response, "status_code", 0) or 0)
        detail = ""
        if status_code >= 400:
            data = getattr(response, "data", None)
            if isinstance(data, dict):
                detail = str(data.get("detail") or data.get("code") or "")[:255]
            elif data is not None:
                detail = str(data)[:255]
        ApiRequestLog.objects.create(
            organization=organization,
            api_key=api_key,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            error_detail=detail,
        )
    except Exception:  # noqa: BLE001 — never break the API response
        logger.exception("failed to write ApiRequestLog")


class PublicAPIRequestLoggingMixin:
    """Attach to public API views to populate usage graphs."""

    def initial(self, request, *args, **kwargs):
        self._api_request_started = time.perf_counter()
        return super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        started = getattr(self, "_api_request_started", None)
        duration_ms = None
        if started is not None:
            duration_ms = int((time.perf_counter() - started) * 1000)
        log_public_api_request(request, response, duration_ms=duration_ms)
        return response
