from django.db.models import OuterRef, Prefetch, Q, Subquery
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.features import extract_customer_features
from apps.customers.models import Customer, CustomerContact
from apps.customers.serializers import (
    CustomerContactSerializer,
    CustomerDetailSerializer,
    CustomerSerializer,
)
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CustomerListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = Customer.objects.select_related("assigned_user").all()
    serializer_class = CustomerSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_CUSTOMER
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = super().get_queryset().select_related("assigned_user")
        primary_name = (
            CustomerContact.objects.filter(customer_id=OuterRef("pk"), is_primary=True)
            .order_by("id")
            .values("full_name")[:1]
        )
        qs = qs.annotate(primary_contact_name_anno=Subquery(primary_name))

        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(tax_number__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )

        risk_status = params.get("risk_status", "").strip()
        if risk_status:
            qs = qs.filter(risk_status=risk_status)

        assigned_user = params.get("assigned_user", "").strip()
        if assigned_user:
            if assigned_user in {"null", "none", "0"}:
                qs = qs.filter(assigned_user__isnull=True)
            else:
                qs = qs.filter(assigned_user_id=assigned_user)

        city = params.get("city", "").strip()
        if city:
            qs = qs.filter(city__iexact=city)

        sector = params.get("sector", "").strip()
        if sector:
            qs = qs.filter(sector__iexact=sector)

        is_active = params.get("is_active", "").strip().lower()
        if is_active in {"true", "1", "yes"}:
            qs = qs.filter(is_active=True)
        elif is_active in {"false", "0", "no"}:
            qs = qs.filter(is_active=False)

        has_overdue = params.get("has_overdue", "").strip().lower()
        if has_overdue in {"true", "1", "yes"}:
            # Fatura modülü gelene kadar açık gecikme yok → boş sonuç
            qs = qs.none()

        ordering = params.get("ordering", "name").strip()
        allowed = {
            "name",
            "-name",
            "code",
            "-code",
            "risk_status",
            "-risk_status",
            "last_contact_at",
            "-last_contact_at",
            "created_at",
            "-created_at",
        }
        if ordering in allowed:
            qs = qs.order_by(ordering)

        # NP-301 — resource-scoped customer visibility
        membership = getattr(self.request, "membership", None)
        if membership is not None:
            from apps.organizations.resource_scope import filter_customers_for_membership

            qs = filter_customers_for_membership(membership, qs)

        return qs

    def perform_create(self, serializer):
        from apps.audit.models import write_audit_log

        super().perform_create(serializer)
        customer = serializer.instance
        write_audit_log(
            organization=customer.organization,
            actor=self.request.user,
            action="customer.create",
            entity_type="Customer",
            entity_id=customer.id,
            summary=f"Müşteri oluşturuldu: {customer.name}",
            changes={"code": customer.code, "name": customer.name},
        )


class CustomerDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Customer.objects.select_related("assigned_user").all()
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_CUSTOMER
    http_method_names = ["get", "patch", "put", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CustomerDetailSerializer
        return CustomerSerializer

    def get_queryset(self):
        qs = super().get_queryset().select_related("assigned_user")
        if self.request.method == "GET":
            qs = qs.prefetch_related(
                Prefetch(
                    "contacts",
                    queryset=CustomerContact.objects.order_by("-is_primary", "full_name"),
                )
            )
        membership = getattr(self.request, "membership", None)
        if membership is not None:
            from apps.organizations.resource_scope import filter_customers_for_membership

            qs = filter_customers_for_membership(membership, qs)
        return qs

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        membership = getattr(request, "membership", None)
        if membership is not None and isinstance(response.data, dict):
            from apps.organizations.resource_scope import mask_customer_payload

            response.data = mask_customer_payload(dict(response.data), membership)
        try:
            from apps.governance.access import record_access
            from apps.governance.models import DataAccessAction

            org = getattr(request, "organization", None)
            if org is not None:
                record_access(
                    org,
                    actor=request.user,
                    action=DataAccessAction.VIEW_CUSTOMER,
                    resource_type="customer",
                    resource_id=kwargs.get("pk"),
                    summary="Müşteri detayı görüntülendi",
                )
        except Exception:  # noqa: BLE001
            pass
        return response

    def perform_update(self, serializer):
        from apps.audit.models import write_audit_log

        before = {
            "name": serializer.instance.name,
            "code": serializer.instance.code,
            "is_active": serializer.instance.is_active,
        }
        super().perform_update(serializer)
        customer = serializer.instance
        write_audit_log(
            organization=customer.organization,
            actor=self.request.user,
            action="customer.update",
            entity_type="Customer",
            entity_id=customer.id,
            summary=f"Müşteri güncellendi: {customer.name}",
            changes={
                "before": before,
                "after": {
                    "name": customer.name,
                    "code": customer.code,
                    "is_active": customer.is_active,
                },
            },
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        serializer = CustomerSerializer(instance, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerFeaturesView(APIView):
    """GET /api/customers/{id}/features/ — NP-220 feature vector."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=403)
        customer = Customer.objects.filter(pk=pk, organization=organization).first()
        if customer is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(extract_customer_features(customer))


class CustomerFinancialSummaryView(APIView):
    """GET /api/customers/{id}/financial-summary/ — NP-413 charts + insights."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request, pk: int):
        from apps.customers.financial_summary import customer_financial_summary

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=403)
        customer = Customer.objects.filter(pk=pk, organization=organization).first()
        if customer is None:
            return Response({"detail": "Not found."}, status=404)
        months = request.query_params.get("months") or "12"
        try:
            months_n = max(3, min(24, int(months)))
        except ValueError:
            months_n = 12
        return Response(customer_financial_summary(customer, months=months_n))


class CustomerContactListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = CustomerContactSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_CUSTOMER

    def get_customer(self) -> Customer:
        organization = self.get_current_organization()
        try:
            return Customer.objects.get(
                pk=self.kwargs["customer_id"],
                organization=organization,
            )
        except Customer.DoesNotExist as exc:
            from rest_framework.exceptions import NotFound

            raise NotFound() from exc

    def get_queryset(self):
        customer = self.get_customer()
        return CustomerContact.objects.filter(
            customer=customer,
            organization=self.get_current_organization(),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["customer"] = self.get_customer()
        return context


class CustomerContactDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerContactSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_CUSTOMER
    http_method_names = ["get", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        organization = self.get_current_organization()
        return CustomerContact.objects.filter(
            organization=organization,
            customer_id=self.kwargs["customer_id"],
            customer__organization=organization,
        )
