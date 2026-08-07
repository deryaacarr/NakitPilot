from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.webhooks.delivery import WebhookDeliveryError, manual_resend, process_delivery
from apps.webhooks.models import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint
from apps.webhooks.serializers import (
    WebhookDeliverySerializer,
    WebhookEndpointCreateSerializer,
    WebhookEndpointSerializer,
    WebhookTestSendSerializer,
)
from apps.webhooks.services import WebhookServiceError, create_endpoint

_TENANT_PERMS = [
    IsAuthenticated,
    RequireTenantContextPermission,
    HasOrganizationPermission,
]


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class WebhookEndpointListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    pagination_class = StandardResultsSetPagination
    queryset = WebhookEndpoint.objects.prefetch_related("subscriptions").all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WebhookEndpointCreateSerializer
        return WebhookEndpointSerializer

    def create(self, request, *args, **kwargs):
        serializer = WebhookEndpointCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            endpoint, raw_secret, _subs = create_endpoint(
                organization=self.get_current_organization(),
                name=serializer.validated_data["name"],
                url=serializer.validated_data["url"],
                description=serializer.validated_data.get("description") or "",
                event_types=serializer.validated_data.get("event_types") or [],
                created_by=request.user,
            )
        except WebhookServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        payload = WebhookEndpointSerializer(endpoint).data
        payload["secret"] = raw_secret
        return Response(payload, status=status.HTTP_201_CREATED)


class WebhookEndpointTestSendView(TenantQuerysetMixin, generics.GenericAPIView):
    """Enqueue a synthetic event delivery for portal testing (NP-206)."""

    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    queryset = WebhookEndpoint.objects.prefetch_related("subscriptions").all()

    def post(self, request, *args, **kwargs):
        endpoint = self.get_object()
        serializer = WebhookTestSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_type = serializer.validated_data["event_type"]
        payload = serializer.validated_data.get("payload") or {
            "test": True,
            "message": "NakitPilot webhook test event",
            "endpoint_id": endpoint.id,
            "sent_at": timezone.now().isoformat(),
        }
        event_id = f"test-{endpoint.id}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        from apps.webhooks.models import WebhookDelivery, WebhookSubscription
        from apps.webhooks.retry import DEFAULT_MAX_ATTEMPTS

        WebhookSubscription.objects.get_or_create(
            organization=endpoint.organization,
            endpoint=endpoint,
            event_type=event_type,
            defaults={"is_active": True},
        )

        delivery = WebhookDelivery.objects.create(
            organization=endpoint.organization,
            endpoint=endpoint,
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            status=WebhookDeliveryStatus.PENDING,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            next_attempt_at=timezone.now(),
        )
        process_delivery(delivery.id, force=True)
        delivery.refresh_from_db()
        return Response(
            {"deliveries": [WebhookDeliverySerializer(delivery).data]},
            status=status.HTTP_201_CREATED,
        )


class WebhookDeliveryListView(TenantQuerysetMixin, generics.ListAPIView):
    """List webhook deliveries; default filter shows failed/exhausted for ops UI."""

    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    serializer_class = WebhookDeliverySerializer
    pagination_class = StandardResultsSetPagination
    queryset = WebhookDelivery.objects.select_related("endpoint").prefetch_related(
        "attempts"
    )

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = (self.request.query_params.get("status") or "failed").strip()
        if status_param == "failed":
            qs = qs.filter(
                status__in=[
                    WebhookDeliveryStatus.FAILED,
                    WebhookDeliveryStatus.EXHAUSTED,
                ]
            )
        elif status_param and status_param != "all":
            qs = qs.filter(status=status_param)
        return qs


class WebhookDeliveryDetailView(TenantQuerysetMixin, generics.RetrieveAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    serializer_class = WebhookDeliverySerializer
    queryset = WebhookDelivery.objects.select_related("endpoint").prefetch_related(
        "attempts"
    )


class WebhookDeliveryResendView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    queryset = WebhookDelivery.objects.select_related("endpoint").prefetch_related(
        "attempts"
    )

    def post(self, request, *args, **kwargs):
        delivery = self.get_object()
        try:
            delivery = manual_resend(delivery)
        except WebhookDeliveryError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        delivery.refresh_from_db()
        from django.conf import settings

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            delivery = process_delivery(delivery.id, force=True)
        return Response(WebhookDeliverySerializer(delivery).data, status=status.HTTP_200_OK)
