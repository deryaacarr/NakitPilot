from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.payments.models import Payment
from apps.payments.serializers import (
    PaymentAllocationsUpdateSerializer,
    PaymentCancelSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
)
from apps.payments.services import PaymentValidationError, cancel_payment


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class PaymentListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    """GET/POST /api/payments/ — NP-070 (+071/072 on create)."""

    queryset = Payment.objects.select_related("customer", "recorded_by", "cancelled_by").prefetch_related(
        "allocations__invoice"
    )
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_PAYMENT
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PaymentCreateSerializer
        return PaymentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        customer = params.get("customer", "").strip()
        if customer:
            qs = qs.filter(customer_id=customer)
        include_cancelled = params.get("include_cancelled", "").lower() in {"1", "true", "yes"}
        if not include_cancelled:
            qs = qs.filter(cancelled_at__isnull=True)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["organization"] = self.get_current_organization()
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(
            PaymentSerializer(payment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentDetailView(TenantQuerysetMixin, generics.RetrieveAPIView):
    """GET /api/payments/{id}/ — NP-070."""

    queryset = Payment.objects.select_related("customer", "recorded_by", "cancelled_by").prefetch_related(
        "allocations__invoice"
    )
    serializer_class = PaymentSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_PAYMENT


class PaymentAllocationsView(TenantQuerysetMixin, APIView):
    """PUT /api/payments/{id}/allocations/ — NP-071/072 redistribute."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.ADD_PAYMENT
    read_permission = Permission.VIEW_REPORTS

    def put(self, request, pk: int):
        try:
            payment = (
                Payment.objects.for_organization(self.get_current_organization())
                .select_related("customer")
                .get(pk=pk)
            )
        except Payment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = PaymentAllocationsUpdateSerializer(
            data=request.data,
            context={"request": request, "payment": payment},
        )
        ser.is_valid(raise_exception=True)
        payment = ser.save()
        return Response(PaymentSerializer(payment).data)


class PaymentCancelView(TenantQuerysetMixin, APIView):
    """POST /api/payments/{id}/cancel/ — NP-074 soft cancel."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.ADD_PAYMENT
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        try:
            payment = Payment.objects.for_organization(self.get_current_organization()).get(pk=pk)
        except Payment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = PaymentCancelSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        try:
            payment = cancel_payment(
                payment,
                user=request.user,
                reason=ser.validated_data.get("reason", ""),
            )
        except PaymentValidationError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(PaymentSerializer(payment).data)
