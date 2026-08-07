"""NP-235 AI usage / cost-control HTTP API."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_usage.serializers import (
    AIUsageLimitConfigSerializer,
    AIUsagePackageUpdateSerializer,
)
from apps.ai_usage.services import (
    apply_package_defaults,
    get_or_create_limit_config,
    usage_summary,
)
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class AIUsageSummaryView(APIView):
    """GET /api/ai-usage/summary/ — current package usage + limits."""

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
        return Response(usage_summary(organization, user=request.user))


class AIUsageLimitsView(APIView):
    """GET/PATCH /api/ai-usage/limits/ — org limit config (settings)."""

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
        config = get_or_create_limit_config(organization)
        return Response(AIUsageLimitConfigSerializer(config).data)

    def patch(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        config = get_or_create_limit_config(organization)

        if "package" in request.data and len(request.data) == 1:
            ser = AIUsagePackageUpdateSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            config = apply_package_defaults(config, ser.validated_data["package"])
            return Response(AIUsageLimitConfigSerializer(config).data)

        ser = AIUsageLimitConfigSerializer(config, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_200_OK)
