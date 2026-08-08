from django.db.models import Q
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.grouping import enrich_alert, importance_group
from apps.notifications.models import (
    AlertSeverity,
    DashboardAlert,
    NotificationPreference,
)
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class DashboardAlertSerializer(serializers.ModelSerializer):
    customer_id = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    importance_group = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

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
            "customer_id",
            "customer_name",
            "importance_group",
            "actions",
        )
        read_only_fields = fields

    def _enrich(self, obj: DashboardAlert) -> dict:
        cache = self.context.setdefault("_alert_enrich", {})
        if obj.id not in cache:
            cache[obj.id] = enrich_alert(obj)
        return cache[obj.id]

    def get_customer_id(self, obj: DashboardAlert):
        return self._enrich(obj)["customer_id"]

    def get_customer_name(self, obj: DashboardAlert):
        return self._enrich(obj)["customer_name"]

    def get_importance_group(self, obj: DashboardAlert):
        return self._enrich(obj)["importance_group"]

    def get_actions(self, obj: DashboardAlert):
        return self._enrich(obj)["actions"]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            "muted_types",
            "mute_info",
            "mute_system",
            "group_by_customer",
            "updated_at",
        )
        read_only_fields = ("updated_at",)


class DashboardAlertListView(TenantQuerysetMixin, generics.ListAPIView):
    """GET /api/notifications/alerts/ — NP-141 + NP-460/462."""

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

        prefs = (
            NotificationPreference.objects.for_organization(self.get_current_organization())
            .filter(user=request.user)
            .first()
        )
        alerts = list(qs[:500])
        if prefs:
            muted = set(prefs.muted_types or [])
            filtered = []
            for alert in alerts:
                group = importance_group(
                    severity=alert.severity,
                    notification_type=alert.notification_type,
                )
                # NP-462 — critical never filtered out.
                if group == "critical":
                    filtered.append(alert)
                    continue
                if alert.notification_type in muted:
                    continue
                if prefs.mute_info and group == "info":
                    continue
                if prefs.mute_system and group == "system":
                    continue
                filtered.append(alert)
            alerts = filtered

        try:
            limit = min(int(request.query_params.get("limit", 50)), 200)
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = max(int(request.query_params.get("offset", 0)), 0)
        except (TypeError, ValueError):
            offset = 0
        total = len(alerts)
        page = alerts[offset : offset + limit]
        return Response(
            {
                "count": total,
                "unread_count": unread_count,
                "group_by_customer": bool(prefs.group_by_customer) if prefs else True,
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
    """POST /api/notifications/alerts/read-all/ — skips CRITICAL (NP-462)."""

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
            .exclude(severity=AlertSeverity.CRITICAL)
            .update(is_read=True)
        )
        return Response({"updated": updated, "critical_preserved": True})


class NotificationPreferenceView(TenantQuerysetMixin, APIView):
    """GET/PATCH /api/notifications/preferences/ — NP-462."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        org = self.get_current_organization()
        pref, _ = NotificationPreference.objects.get_or_create(
            organization=org,
            user=request.user,
        )
        return Response(NotificationPreferenceSerializer(pref).data)

    def patch(self, request):
        org = self.get_current_organization()
        pref, _ = NotificationPreference.objects.get_or_create(
            organization=org,
            user=request.user,
        )
        ser = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        pref = ser.save()
        # Never allow muting critical types.
        muted = [
            t
            for t in (pref.muted_types or [])
            if t not in {"PROMISE_BROKEN", "CRITICAL_CUSTOMER"}
        ]
        if muted != (pref.muted_types or []):
            pref.muted_types = muted
            pref.save(update_fields=["muted_types", "updated_at"])
        return Response(NotificationPreferenceSerializer(pref).data)


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
