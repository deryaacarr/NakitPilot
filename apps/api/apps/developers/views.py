from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.developers.catalog import portal_docs_payload
from apps.developers.services import recent_errors, usage_series
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization

_TENANT_PERMS = [
    IsAuthenticated,
    RequireTenantContextPermission,
    HasOrganizationPermission,
]


class DeveloperDocsView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS

    def get(self, request, *args, **kwargs):
        return Response(portal_docs_payload())


class DeveloperUsageView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS

    def get(self, request, *args, **kwargs):
        org = get_request_organization(request)
        days = request.query_params.get("days", "14")
        try:
            days_i = int(days)
        except (TypeError, ValueError):
            days_i = 14
        return Response(usage_series(organization=org, days=days_i))


class DeveloperErrorsView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS

    def get(self, request, *args, **kwargs):
        org = get_request_organization(request)
        limit = request.query_params.get("limit", "25")
        try:
            limit_i = int(limit)
        except (TypeError, ValueError):
            limit_i = 25
        rows = recent_errors(organization=org, limit=limit_i)
        payload = []
        for row in rows:
            item = {
                "source": row["source"],
                "id": row["id"],
                "at": row["at"],
                "title": row["title"],
                "detail": row["detail"],
                "status_code": row.get("status_code"),
            }
            if row["source"] == "api":
                item["api_key_prefix"] = row.get("api_key_prefix", "")
            else:
                item["delivery_public_id"] = row.get("delivery_public_id", "")
            payload.append(item)
        return Response({"results": payload})
