from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.serializers import InvoiceDetailSerializer, InvoiceSerializer
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _parse_date(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(raw: str) -> Decimal | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


class InvoiceListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = Invoice.objects.select_related("customer", "assigned_user").all()
    serializer_class = InvoiceSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_INVOICE
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = super().get_queryset().select_related("customer", "assigned_user")
        params = self.request.query_params
        today = timezone.localdate()

        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(number__icontains=search)
                | Q(description__icontains=search)
                | Q(customer__name__icontains=search)
                | Q(customer__code__icontains=search)
            )

        # status or multi-status (comma-separated): OPEN,OVERDUE,PARTIALLY_PAID,PAID
        status_value = params.get("status", "").strip()
        if status_value:
            statuses = [s.strip() for s in status_value.split(",") if s.strip()]
            if len(statuses) == 1:
                qs = qs.filter(status=statuses[0])
            elif statuses:
                qs = qs.filter(status__in=statuses)

        customer_id = params.get("customer", "").strip()
        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        assigned = params.get("assigned_user", "").strip()
        if assigned == "me":
            qs = qs.filter(assigned_user=self.request.user)
        elif assigned.isdigit():
            qs = qs.filter(assigned_user_id=int(assigned))

        risk_status = params.get("risk_status", "").strip()
        if risk_status:
            qs = qs.filter(customer__risk_status=risk_status)

        if params.get("promise_today", "").strip().lower() in {"1", "true", "yes"}:
            from apps.collections.models import PaymentPromise, PaymentPromiseStatus

            promise_customers = PaymentPromise.objects.filter(
                organization_id=self.get_current_organization().id,
                status=PaymentPromiseStatus.PENDING,
                promised_date=today,
            ).values_list("customer_id", flat=True)
            qs = qs.filter(customer_id__in=promise_customers)

        remaining_min = _parse_decimal(params.get("remaining_min", ""))
        if remaining_min is not None:
            # Prefer invoices with enough total as a proxy; refine in Python for page
            qs = qs.filter(total_amount__gte=remaining_min)

        currency = params.get("currency", "").strip().upper()
        if currency:
            qs = qs.filter(currency=currency)

        # Tarih aralığı (fatura veya vade)
        invoice_from = _parse_date(params.get("invoice_date_from", ""))
        invoice_to = _parse_date(params.get("invoice_date_to", ""))
        if invoice_from:
            qs = qs.filter(invoice_date__gte=invoice_from)
        if invoice_to:
            qs = qs.filter(invoice_date__lte=invoice_to)

        due_from = _parse_date(params.get("due_date_from", ""))
        due_to = _parse_date(params.get("due_date_to", ""))
        if due_from:
            qs = qs.filter(due_date__gte=due_from)
        if due_to:
            qs = qs.filter(due_date__lte=due_to)

        date_from = _parse_date(params.get("date_from", ""))
        date_to = _parse_date(params.get("date_to", ""))
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)

        # Tutar aralığı
        amount_min = _parse_decimal(params.get("amount_min", ""))
        amount_max = _parse_decimal(params.get("amount_max", ""))
        if amount_min is not None:
            qs = qs.filter(total_amount__gte=amount_min)
        if amount_max is not None:
            qs = qs.filter(total_amount__lte=amount_max)

        # Gecikme günü filtresi (ödenmemiş faturalar: today - due_date)
        overdue_min = params.get("overdue_days_min", "").strip()
        overdue_max = params.get("overdue_days_max", "").strip()
        if overdue_min or overdue_max:
            qs = qs.exclude(
                status__in=[InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]
            )
            if overdue_min.isdigit():
                # today - due_date >= N  ⇒  due_date <= today - N
                qs = qs.filter(due_date__lte=today - timedelta(days=int(overdue_min)))
            if overdue_max.isdigit():
                # today - due_date <= M  ⇒  due_date >= today - M
                qs = qs.filter(due_date__gte=today - timedelta(days=int(overdue_max)))

        ordering = params.get("ordering", "-invoice_date").strip()
        allowed = {
            "invoice_date",
            "-invoice_date",
            "due_date",
            "-due_date",
            "total_amount",
            "-total_amount",
            "number",
            "-number",
            "status",
            "-status",
            "created_at",
            "-created_at",
        }
        if ordering in allowed:
            qs = qs.order_by(ordering)

        return qs

    def perform_create(self, serializer):
        from apps.audit.models import write_audit_log

        super().perform_create(serializer)
        invoice = serializer.instance
        write_audit_log(
            organization=invoice.organization,
            actor=self.request.user,
            action="invoice.create",
            entity_type="Invoice",
            entity_id=invoice.id,
            summary=f"Fatura eklendi: {invoice.number}",
            changes={
                "number": invoice.number,
                "customer_id": invoice.customer_id,
                "total_amount": str(invoice.total_amount),
            },
        )


class InvoiceDetailView(TenantQuerysetMixin, generics.RetrieveUpdateAPIView):
    queryset = Invoice.objects.select_related("customer", "assigned_user").all()
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_INVOICE
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return InvoiceDetailSerializer
        return InvoiceSerializer


class InvoiceCancelView(TenantQuerysetMixin, APIView):
    """POST /api/invoices/{id}/cancel — soft cancel (status=CANCELLED)."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.ADD_INVOICE
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        from apps.audit.models import write_audit_log

        organization = self.get_current_organization()
        try:
            invoice = (
                Invoice.objects.select_related("customer", "assigned_user")
                .for_organization(organization)
                .get(pk=pk)
            )
        except Invoice.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if invoice.status == InvoiceStatus.CANCELLED:
            serializer = InvoiceSerializer(invoice, context={"request": request})
            return Response(
                {"detail": "Fatura zaten iptal edilmiş.", "invoice": serializer.data},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invoice.status == InvoiceStatus.PAID:
            return Response(
                {"detail": "Ödenmiş fatura iptal edilemez."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous = invoice.status
        invoice.cancel()
        write_audit_log(
            organization=organization,
            actor=request.user,
            action="invoice.cancel",
            entity_type="Invoice",
            entity_id=invoice.id,
            summary=f"Fatura iptal edildi: {invoice.number}",
            changes={"previous_status": previous, "status": invoice.status},
        )
        serializer = InvoiceSerializer(invoice, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
