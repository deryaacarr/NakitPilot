"""Payment promise API views (NP-090–094)."""

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.collections.models import PaymentPromise
from apps.collections.promise_serializers import (
    PaymentPromiseCancelSerializer,
    PaymentPromiseCreateSerializer,
    PaymentPromiseSerializer,
    PaymentPromiseUpdateSerializer,
)
from apps.collections.promises import promises_calendar
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class PaymentPromiseListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    """GET/POST /api/payment-promises/ — NP-090."""

    queryset = PaymentPromise.objects.select_related("customer", "invoice", "created_by")
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PaymentPromiseCreateSerializer
        return PaymentPromiseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if customer := params.get("customer", "").strip():
            qs = qs.filter(customer_id=customer)
        if status_value := params.get("status", "").strip():
            qs = qs.filter(status=status_value)
        if date_from := params.get("promised_date_from", "").strip():
            qs = qs.filter(promised_date__gte=date_from)
        if date_to := params.get("promised_date_to", "").strip():
            qs = qs.filter(promised_date__lte=date_to)
        include_cancelled = params.get("include_cancelled", "").lower() in {"1", "true"}
        if not include_cancelled:
            qs = qs.exclude(status="CANCELLED")
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["organization"] = self.get_current_organization()
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        promise = serializer.save()
        data = PaymentPromiseSerializer(promise).data
        warnings = serializer.context.get("warnings") or {}
        if warnings:
            return Response(
                {"promise": data, "warnings": warnings},
                status=status.HTTP_201_CREATED,
            )
        return Response(data, status=status.HTTP_201_CREATED)


class PaymentPromiseDetailView(TenantQuerysetMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/payment-promises/{id}/ — NP-090."""

    queryset = PaymentPromise.objects.select_related("customer", "invoice", "created_by")
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return PaymentPromiseUpdateSerializer
        return PaymentPromiseSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        promise = serializer.save()
        data = PaymentPromiseSerializer(promise).data
        warnings = serializer.context.get("warnings") or {}
        if warnings:
            return Response({"promise": data, "warnings": warnings})
        return Response(data)


class PaymentPromiseCancelView(TenantQuerysetMixin, APIView):
    """POST /api/payment-promises/{id}/cancel/ — NP-090."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_COLLECTION_TASK
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        try:
            promise = PaymentPromise.objects.for_organization(
                self.get_current_organization()
            ).get(pk=pk)
        except PaymentPromise.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = PaymentPromiseCancelSerializer(
            data=request.data or {},
            context={"request": request, "promise": promise},
        )
        ser.is_valid(raise_exception=True)
        promise = ser.save()
        return Response(PaymentPromiseSerializer(promise).data)


class PaymentPromiseCalendarView(TenantQuerysetMixin, APIView):
    """GET /api/payment-promises/calendar/ — NP-094."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        board = promises_calendar(organization=self.get_current_organization())
        return Response(
            {
                "today": PaymentPromiseSerializer(board["today"], many=True).data,
                "upcoming": PaymentPromiseSerializer(board["upcoming"], many=True).data,
                "broken": PaymentPromiseSerializer(board["broken"], many=True).data,
                "fulfilled": PaymentPromiseSerializer(board["fulfilled"], many=True).data,
            }
        )
