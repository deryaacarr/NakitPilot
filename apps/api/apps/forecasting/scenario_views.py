"""NP-272–275 forecast scenario / what-if / accuracy / cash-gap APIs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.subscription_service import Feature, can_use
from apps.forecasting.accuracy import forecast_accuracy_report
from apps.forecasting.cash_alerts import evaluate_cash_gap_rules
from apps.forecasting.scenarios import ScenarioType, run_scenario
from apps.forecasting.whatif import what_if_customer_late_payment
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class ScenarioTypeListView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        return Response(
            {
                "results": [
                    {"value": t, "label": ScenarioType.LABELS[t]} for t in ScenarioType.ALL
                ]
            }
        )


class ScenarioRunView(APIView):
    """POST /api/forecast/scenarios/run/ — NP-272."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        entitlement = can_use(organization, Feature.FORECAST_SCENARIOS)
        # Starter can still run BASE; advanced scenarios gated
        stype = (request.data.get("scenario_type") or ScenarioType.BASE).upper()
        if stype not in (ScenarioType.BASE,) and not entitlement.allowed:
            return Response(
                {
                    "detail": entitlement.reason or "Senaryo özelliği paketinizde yok.",
                    "code": "entitlement_denied",
                    "feature": Feature.FORECAST_SCENARIOS,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        weeks = int(request.data.get("weeks") or 13)
        starting = request.data.get("starting_cash")
        result = run_scenario(
            organization.id,
            scenario_type=stype,
            variables=request.data.get("variables"),
            weeks=weeks,
            starting_cash=Decimal(str(starting)) if starting is not None else None,
        )
        return Response(result)


class WhatIfView(APIView):
    """POST /api/forecast/what-if/ — NP-273."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        entitlement = can_use(organization, Feature.WHAT_IF_ANALYSIS)
        if not entitlement.allowed:
            return Response(
                {
                    "detail": entitlement.reason,
                    "code": "entitlement_denied",
                    "feature": Feature.WHAT_IF_ANALYSIS,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        customer_id = request.data.get("customer_id")
        if not customer_id:
            return Response({"detail": "customer_id required"}, status=400)
        delay_days = int(request.data.get("delay_days") or 30)
        amount = request.data.get("amount")
        try:
            result = what_if_customer_late_payment(
                organization.id,
                customer_id=int(customer_id),
                delay_days=delay_days,
                amount=Decimal(str(amount)) if amount is not None else None,
                weeks=int(request.data.get("weeks") or 13),
            )
        except ValueError:
            return Response({"detail": "Müşteri bulunamadı."}, status=404)
        return Response(result)


class CashGapAlertView(APIView):
    """GET/POST /api/forecast/cash-gap-alerts/ — NP-274."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        return self._run(request, create_alerts=False)

    def post(self, request):
        return self._run(request, create_alerts=True)

    def _run(self, request, *, create_alerts: bool):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        min_safe = request.query_params.get("min_safe_balance") or request.data.get(
            "min_safe_balance"
        )
        result = evaluate_cash_gap_rules(
            organization.id,
            weeks=int(
                request.query_params.get("weeks")
                or request.data.get("weeks")
                or 13
            ),
            min_safe_balance=Decimal(str(min_safe)) if min_safe else None,
            create_alerts=create_alerts,
        )
        return Response(result)


class ForecastAccuracyView(APIView):
    """GET /api/forecast/accuracy/ — NP-275."""

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
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        result = forecast_accuracy_report(
            organization.id,
            date_from=date.fromisoformat(date_from) if date_from else None,
            date_to=date.fromisoformat(date_to) if date_to else None,
        )
        return Response(result)
