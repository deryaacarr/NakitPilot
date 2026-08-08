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


class PushSubscribeView(APIView):
    """POST /api/notifications/push/subscribe/ — NP-344."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def post(self, request):
        from apps.notifications.models import PushSubscription
        from apps.organizations.tenancy import get_request_organization

        org = get_request_organization(request)
        endpoint = (request.data.get("endpoint") or "").strip()
        keys = request.data.get("keys") or {}
        p256dh = (keys.get("p256dh") or request.data.get("p256dh") or "").strip()
        auth = (keys.get("auth") or request.data.get("auth") or "").strip()
        if not endpoint or not p256dh or not auth:
            return Response(
                {"detail": "endpoint, keys.p256dh ve keys.auth zorunlu."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sub, _created = PushSubscription.objects.update_or_create(
            organization=org,
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:255],
                "is_active": True,
            },
        )
        return Response({"id": sub.id, "endpoint": sub.endpoint, "active": sub.is_active})


class PushUnsubscribeView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.VIEW_REPORTS
    read_permission = Permission.VIEW_REPORTS

    def post(self, request):
        from apps.notifications.models import PushSubscription
        from apps.organizations.tenancy import get_request_organization

        org = get_request_organization(request)
        endpoint = (request.data.get("endpoint") or "").strip()
        updated = PushSubscription.objects.filter(
            organization=org, user=request.user, endpoint=endpoint
        ).update(is_active=False)
        return Response({"updated": updated})


class PushVapidPublicKeyView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        from apps.notifications.push import vapid_public_key

        return Response({"public_key": vapid_public_key()})
