"""Dashboard HTTP API (NP-120–124)."""

from __future__ import annotations

from datetime import date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.performance import DateRangeError, performance_report, resolve_date_range
from apps.dashboard.services import (
    aging_report,
    dashboard_overview,
    dashboard_summary,
    today_call_list,
)
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


def _parse_date(raw: str | None, field: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise DateRangeError(f"{field} must be YYYY-MM-DD.") from exc


def _range_from_request(request) -> dict:
    preset = (request.query_params.get("range") or "week").strip().lower()
    date_from = _parse_date(request.query_params.get("from"), "from")
    date_to = _parse_date(request.query_params.get("to"), "to")
    return resolve_date_range(preset=preset, date_from=date_from, date_to=date_to)


class _DashboardBase(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS


class DashboardOverviewView(_DashboardBase):
    """GET /api/dashboard/?range=week|today|month|last_30|custom&from=&to="""

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            rng = _range_from_request(request)
        except DateRangeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            dashboard_overview(
                organization.id,
                preset=rng["preset"],
                date_from=rng["date_from"],
                date_to=rng["date_to"],
            )
        )


class DashboardSummaryView(_DashboardBase):
    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            rng = _range_from_request(request)
        except DateRangeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            dashboard_summary(
                organization.id,
                as_of=rng["as_of"],
                date_from=rng["date_from"],
                date_to=rng["date_to"],
            )
        )


class DashboardAgingView(_DashboardBase):
    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            rng = _range_from_request(request)
        except DateRangeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(aging_report(organization.id, as_of=rng["as_of"]))


class DashboardCallListView(_DashboardBase):
    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            rng = _range_from_request(request)
        except DateRangeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(today_call_list(organization.id, as_of=rng["as_of"], limit=10))


class DashboardPerformanceView(_DashboardBase):
    """GET /api/dashboard/performance/ — NP-123."""

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            rng = _range_from_request(request)
        except DateRangeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            performance_report(
                organization.id,
                date_from=rng["date_from"],
                date_to=rng["date_to"],
            )
        )
