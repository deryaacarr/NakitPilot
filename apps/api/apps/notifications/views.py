from django.db.models import Q
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import DashboardAlert
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission


class DashboardAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardAlert
        fields = (
            "id",
            "title",
            "body",
            "severity",
            "notification_type",
            "category",
            "entity_type",
            "entity_id",
            "href",
            "is_read",
            "created_at",
        )
        read_only_fields = fields


class DashboardAlertListView(TenantQuerysetMixin, generics.ListAPIView):
    """GET /api/notifications/alerts/ — NP-141 notification center feed."""

    queryset = DashboardAlert.objects.all()
    serializer_class = DashboardAlertSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get_queryset(self):
        user = self.request.user
        return (
            super()
            .get_queryset()
            .filter(Q(created_for__isnull=True) | Q(created_for=user))
            .order_by("-created_at")
        )

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        unread_count = qs.filter(is_read=False).count()
        unread_only = request.query_params.get("unread") in {"1", "true", "True"}
        if unread_only:
            qs = qs.filter(is_read=False)
        try:
            limit = min(int(request.query_params.get("limit", 50)), 200)
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = max(int(request.query_params.get("offset", 0)), 0)
        except (TypeError, ValueError):
            offset = 0
        total = qs.count()
        page = qs[offset : offset + limit]
        return Response(
            {
                "count": total,
                "unread_count": unread_count,
                "results": self.get_serializer(page, many=True).data,
            }
        )


class DashboardAlertMarkReadView(TenantQuerysetMixin, APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.VIEW_REPORTS
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        user = request.user
        try:
            alert = (
                DashboardAlert.objects.for_organization(self.get_current_organization())
                .filter(Q(created_for__isnull=True) | Q(created_for=user))
                .get(pk=pk)
            )
        except DashboardAlert.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        alert.is_read = True
        alert.save(update_fields=["is_read"])
        return Response(DashboardAlertSerializer(alert).data)


class DashboardAlertMarkAllReadView(TenantQuerysetMixin, APIView):
    """POST /api/notifications/alerts/read-all/ — NP-141."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.VIEW_REPORTS
    read_permission = Permission.VIEW_REPORTS

    def post(self, request):
        user = request.user
        updated = (
            DashboardAlert.objects.for_organization(self.get_current_organization())
            .filter(Q(created_for__isnull=True) | Q(created_for=user), is_read=False)
            .update(is_read=True)
        )
        return Response({"updated": updated})
