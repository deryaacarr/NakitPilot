"""Public REST API v1 endpoints (NP-201 / NP-202)."""

from __future__ import annotations

from datetime import date

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.forecasting.weekly import (
    DEFAULT_FORECAST_WEEKS,
    MAX_FORECAST_WEEKS,
    cash_flow_api_payload,
)
from apps.invoices.models import Invoice
from apps.public_api.audit import audit_public_write
from apps.public_api.idempotency import run_idempotent
from apps.public_api.mixins import PublicAPIViewMixin
from apps.public_api.serializers import (
    PublicCustomerSerializer,
    PublicInvoiceSerializer,
    PublicPaymentCreateSerializer,
    PublicPaymentSerializer,
)
from apps.risk.models import RiskSnapshot
from apps.risk.services import calculate_customer_risk

IDEMPOTENCY_KEY_PARAM = OpenApiParameter(
    name="Idempotency-Key",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description=(
        "Client-generated unique key (e.g. external-system-payment-1842). "
        "Retries with the same key and body return the original response without "
        "creating a duplicate record."
    ),
)


@extend_schema_view(
    get=extend_schema(tags=["customers"], summary="List customers"),
    post=extend_schema(
        tags=["customers"],
        summary="Create customer",
        parameters=[IDEMPOTENCY_KEY_PARAM],
    ),
)
class CustomerListCreateView(PublicAPIViewMixin, generics.ListCreateAPIView):
    serializer_class = PublicCustomerSerializer
    read_scopes = ["customers:read"]
    write_scopes = ["customers:write"]

    def get_queryset(self):
        org = self.get_organization()
        qs = Customer.objects.filter(organization=org).order_by("name", "id")
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(tax_number__icontains=search)
                | Q(email__icontains=search)
            )
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["organization"] = self.get_organization()
        return ctx

    def create(self, request, *args, **kwargs):
        org = self.get_organization()

        def execute():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        return run_idempotent(
            request=request,
            organization=org,
            endpoint="POST /api/v1/customers",
            payload=request.data,
            execute=execute,
        )

    def perform_create(self, serializer):
        org = self.get_organization()
        customer = serializer.save(organization=org)
        audit_public_write(
            self.request,
            action="customer.create",
            entity_type="Customer",
            entity_id=customer.id,
            summary=f"Public API: müşteri oluşturuldu ({customer.name})",
            changes={"code": customer.code, "name": customer.name},
        )


@extend_schema_view(
    get=extend_schema(tags=["invoices"], summary="List invoices"),
    post=extend_schema(
        tags=["invoices"],
        summary="Create invoice",
        parameters=[IDEMPOTENCY_KEY_PARAM],
    ),
)
class InvoiceListCreateView(PublicAPIViewMixin, generics.ListCreateAPIView):
    serializer_class = PublicInvoiceSerializer
    read_scopes = ["invoices:read"]
    write_scopes = ["invoices:write"]

    def get_queryset(self):
        org = self.get_organization()
        qs = Invoice.objects.filter(organization=org).select_related("customer").order_by(
            "-invoice_date", "-id"
        )
        customer = (self.request.query_params.get("customer") or "").strip()
        if customer:
            qs = qs.filter(customer_id=customer)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["organization"] = self.get_organization()
        return ctx

    def create(self, request, *args, **kwargs):
        org = self.get_organization()

        def execute():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        return run_idempotent(
            request=request,
            organization=org,
            endpoint="POST /api/v1/invoices",
            payload=request.data,
            execute=execute,
        )

    def perform_create(self, serializer):
        org = self.get_organization()
        invoice = serializer.save(organization=org)
        audit_public_write(
            self.request,
            action="invoice.create",
            entity_type="Invoice",
            entity_id=invoice.id,
            summary=f"Public API: fatura oluşturuldu ({invoice.number})",
            changes={
                "number": invoice.number,
                "customer_id": invoice.customer_id,
                "total_amount": str(invoice.total_amount),
            },
        )


@extend_schema(
    tags=["payments"],
    summary="Create payment",
    parameters=[IDEMPOTENCY_KEY_PARAM],
)
class PaymentCreateView(PublicAPIViewMixin, generics.CreateAPIView):
    serializer_class = PublicPaymentCreateSerializer
    write_scopes = ["payments:write"]
    read_scopes = ["payments:write"]  # unused; POST only

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["organization"] = self.get_organization()
        return ctx

    def create(self, request, *args, **kwargs):
        org = self.get_organization()

        def execute():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            payment = serializer.save()
            audit_public_write(
                request,
                action="payment.create",
                entity_type="Payment",
                entity_id=payment.id,
                summary=f"Public API: ödeme kaydı ({payment.amount} {payment.currency})",
                changes={
                    "amount": str(payment.amount),
                    "customer_id": payment.customer_id,
                },
            )
            return Response(
                PublicPaymentSerializer(payment).data,
                status=status.HTTP_201_CREATED,
            )

        return run_idempotent(
            request=request,
            organization=org,
            endpoint="POST /api/v1/payments",
            payload=request.data,
            execute=execute,
        )


@extend_schema(tags=["risk"], summary="Get customer risk")
class CustomerRiskView(PublicAPIViewMixin, APIView):
    read_scopes = ["risk:read"]
    write_scopes = ["risk:read"]

    def get(self, request, pk: int):
        org = self.get_organization()
        customer = get_object_or_404(Customer.objects.filter(organization=org), pk=pk)
        snapshot = (
            RiskSnapshot.objects.filter(customer=customer)
            .order_by("-calculated_at", "-id")
            .first()
        )
        if snapshot is None or customer.risk_score is None:
            result = calculate_customer_risk(customer.pk)
            snapshot = (
                RiskSnapshot.objects.filter(customer_id=customer.pk)
                .order_by("-calculated_at", "-id")
                .first()
            )
            payload = {
                "customer_id": customer.pk,
                "score": result["score"],
                "level": result["level"],
                "reasons": result.get("reasons") or [],
                "calculated_at": snapshot.calculated_at if snapshot else None,
            }
        else:
            payload = {
                "customer_id": customer.pk,
                "score": snapshot.score,
                "level": snapshot.risk_level,
                "reasons": (snapshot.score_details or {}).get("reasons") or [],
                "calculated_at": snapshot.calculated_at,
            }
        return Response(payload)


@extend_schema(tags=["forecast"], summary="Cash-flow forecast")
class CashFlowForecastView(PublicAPIViewMixin, APIView):
    read_scopes = ["forecast:read"]
    write_scopes = ["forecast:read"]

    def get(self, request):
        organization = self.get_organization()
        weeks_raw = request.query_params.get("weeks", str(DEFAULT_FORECAST_WEEKS))
        try:
            weeks = int(weeks_raw)
        except (TypeError, ValueError):
            return Response(
                {"detail": "weeks must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if weeks < 1 or weeks > MAX_FORECAST_WEEKS:
            return Response(
                {"detail": f"weeks must be between 1 and {MAX_FORECAST_WEEKS}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        week_start = None
        week_start_raw = (request.query_params.get("week_start") or "").strip()
        if week_start_raw:
            try:
                week_start = date.fromisoformat(week_start_raw)
            except ValueError:
                return Response(
                    {"detail": "week_start must be YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        payload = cash_flow_api_payload(
            organization.id,
            weeks=weeks,
            week_start=week_start,
            persist=False,
        )
        if week_start is not None and payload.get("detail") is None:
            return Response(
                {"detail": "week_start is outside the forecast horizon."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(payload)
