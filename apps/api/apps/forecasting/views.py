"""Forecast HTTP API (NP-113–115)."""

from __future__ import annotations

from datetime import date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.forecasting.weekly import (
    DEFAULT_FORECAST_WEEKS,
    MAX_FORECAST_WEEKS,
    cash_flow_api_payload,
)
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class CashFlowForecastView(APIView):
    """GET /api/forecast/cash-flow?weeks=13&week_start=YYYY-MM-DD"""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        weeks_raw = request.query_params.get("weeks", str(DEFAULT_FORECAST_WEEKS))
        try:
            weeks = int(weeks_raw)
        except (TypeError, ValueError):
            return Response(
                {"detail": "weeks must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if weeks < 1 or weeks > MAX_FORECAST_WEEKS:
            return Response(
                {"detail": f"weeks must be between 1 and {MAX_FORECAST_WEEKS}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        week_start = None
        week_start_raw = (request.query_params.get("week_start") or "").strip()
        if week_start_raw:
            try:
                week_start = date.fromisoformat(week_start_raw)
            except ValueError:
                return Response(
                    {"detail": "week_start must be YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        payload = cash_flow_api_payload(
            organization.id,
            weeks=weeks,
            week_start=week_start,
            persist=False,
        )
        if week_start is not None and payload.get("detail") is None:
            return Response(
                {"detail": "week_start is outside the forecast horizon."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(payload)
