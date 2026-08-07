"""NP-280 / NP-281 billing API."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import PlanCode, SubscriptionPlan, SubscriptionStatus
from apps.billing.subscription_service import (
    can_use,
    ensure_default_plans,
    ensure_subscription,
    get_active_subscription,
    get_entitlements,
)
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class PlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ensure_default_plans()
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return Response(
            {
                "results": [
                    {
                        "id": p.id,
                        "code": p.code,
                        "name": p.name,
                        "description": p.description,
                        "price_monthly": str(p.price_monthly),
                        "price_yearly": str(p.price_yearly),
                        "entitlements": p.entitlements,
                    }
                    for p in plans
                ]
            }
        )


class SubscriptionMeView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        sub = ensure_subscription(organization)
        return Response(
            {
                "id": sub.id,
                "status": sub.status,
                "plan": {
                    "code": sub.plan.code,
                    "name": sub.plan.name,
                    "price_monthly": str(sub.plan.price_monthly),
                },
                "seats": sub.seats,
                "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
                "current_period_end": (
                    sub.current_period_end.isoformat() if sub.current_period_end else None
                ),
                "entitlements": get_entitlements(organization),
            }
        )

    def post(self, request):
        """Change plan (simple upgrade/downgrade for MVP)."""
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ensure_default_plans()
        code = (request.data.get("plan_code") or "").strip().upper()
        if code not in PlanCode.values:
            return Response({"detail": "Invalid plan_code"}, status=400)
        plan = SubscriptionPlan.objects.get(code=code)
        sub = ensure_subscription(organization)
        sub.plan = plan
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=["plan", "status", "updated_at"])
        return Response(
            {
                "id": sub.id,
                "status": sub.status,
                "plan": {"code": plan.code, "name": plan.name},
                "entitlements": get_entitlements(organization),
            }
        )


class EntitlementCheckView(APIView):
    """GET/POST /api/billing/can-use/?feature=advanced_workflows"""

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
        feature = (request.query_params.get("feature") or "").strip()
        if not feature:
            return Response({"detail": "feature required"}, status=400)
        quantity = int(request.query_params.get("quantity") or 1)
        result = can_use(organization, feature, quantity=quantity)
        return Response(result.as_dict())

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        feature = (request.data.get("feature") or "").strip()
        quantity = int(request.data.get("quantity") or 1)
        result = can_use(organization, feature, quantity=quantity)
        return Response(
            result.as_dict(),
            status=status.HTTP_200_OK if result.allowed else status.HTTP_403_FORBIDDEN,
        )
