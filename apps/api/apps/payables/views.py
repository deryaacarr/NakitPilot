"""NP-270 payables API."""

from __future__ import annotations

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization
from apps.payables.models import (
    BankAccount,
    ExpectedExpense,
    ExpenseCategory,
    Payable,
    RecurringExpense,
)
from apps.payables.serializers import (
    BankAccountSerializer,
    ExpectedExpenseSerializer,
    ExpenseCategorySerializer,
    PayableSerializer,
    RecurringExpenseSerializer,
)
from apps.payables.services import expected_outflows_by_week, net_cash_summary


class BankAccountListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS


class BankAccountDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS


class ExpenseCategoryListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS


class PayableListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = Payable.objects.select_related("category").all()
    serializer_class = PayableSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_PAYMENT

    def perform_create(self, serializer):
        org = get_request_organization(self.request)
        serializer.save(organization=org, created_by=self.request.user)


class PayableDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Payable.objects.all()
    serializer_class = PayableSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_PAYMENT


class RecurringExpenseListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = RecurringExpense.objects.all()
    serializer_class = RecurringExpenseSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS


class RecurringExpenseDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = RecurringExpense.objects.all()
    serializer_class = RecurringExpenseSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS


class ExpectedExpenseListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = ExpectedExpense.objects.all()
    serializer_class = ExpectedExpenseSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_PAYMENT


class ExpectedExpenseDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ExpectedExpense.objects.all()
    serializer_class = ExpectedExpenseSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_PAYMENT


class NetCashView(APIView):
    """GET /api/payables/net-cash/ — tahsilat − ödemeler."""

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
        weeks = int(request.query_params.get("weeks") or 13)
        weeks = max(1, min(weeks, 26))
        # Optional: pull forecast expected collections
        collections = None
        if (request.query_params.get("include_forecast") or "").lower() in {
            "1",
            "true",
        }:
            try:
                from apps.forecasting.weekly import cash_flow_api_payload

                forecast = cash_flow_api_payload(organization.id, weeks=weeks)
                collections = forecast.get("weeks") or forecast.get("results") or []
            except Exception:  # noqa: BLE001
                collections = None
        if collections is None:
            data = {
                "outflows": expected_outflows_by_week(organization, weeks=weeks),
                **net_cash_summary(organization, weeks=weeks),
            }
        else:
            data = net_cash_summary(
                organization, expected_collections=collections, weeks=weeks
            )
        return Response(data)
