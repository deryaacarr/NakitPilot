"""EPIC 35 — legal case APIs + lawyer portal."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import FileResponse
from pathlib import Path
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.legal.criteria import evaluate_legal_handoff_criteria
from apps.legal.models import LegalCase
from apps.legal.package import generate_legal_package
from apps.legal.serializers import (
    LegalActivityCreateSerializer,
    LegalCaseCreateSerializer,
    LegalCaseHandoffSerializer,
    LegalCaseListSerializer,
    LegalCaseSerializer,
    LegalCaseStatusSerializer,
    LawyerCaseSerializer,
)
from apps.legal.services import approve_legal_case, create_legal_case, handoff_to_lawyer
from apps.legal.workflow import (
    LegalWorkflowError,
    add_activity,
    store_legal_document,
    transition_legal_case,
)
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.models import Role
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization

User = get_user_model()


def _is_external_lawyer(request) -> bool:
    membership = getattr(request, "membership", None)
    return bool(membership and membership.role == Role.EXTERNAL_LAWYER)


class LegalCaseListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = LegalCase.objects.select_related("customer", "assigned_lawyer").all()
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_LEGAL

    def get_permissions(self):
        # Lawyers use MANAGE_LEGAL for both read/write on portal endpoints;
        # list uses VIEW_REPORTS for staff — override for lawyers.
        if _is_external_lawyer(self.request):
            self.read_permission = Permission.MANAGE_LEGAL
            self.write_permission = Permission.MANAGE_LEGAL
        return super().get_permissions()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LegalCaseCreateSerializer
        if _is_external_lawyer(self.request):
            return LawyerCaseSerializer
        return LegalCaseListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_external_lawyer(self.request):
            return qs.filter(assigned_lawyer=self.request.user)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        if _is_external_lawyer(request):
            ser = LawyerCaseSerializer(qs, many=True)
            return Response({"count": qs.count(), "results": ser.data})
        page = self.paginate_queryset(qs)
        ser = LegalCaseListSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response({"count": qs.count(), "results": ser.data})

    def create(self, request, *args, **kwargs):
        if _is_external_lawyer(request):
            return Response(
                {"detail": "Avukat yeni dosya oluşturamaz."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = LegalCaseCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = get_request_organization(request)
        try:
            customer = Customer.objects.get(
                pk=ser.validated_data["customer"], organization=org
            )
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Müşteri bulunamadı."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            case = create_legal_case(
                organization=org,
                customer=customer,
                created_by=request.user,
                title=ser.validated_data.get("title") or "",
                notes=ser.validated_data.get("notes") or "",
                invoice_ids=ser.validated_data.get("invoice_ids"),
            )
        except LegalWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            LegalCaseSerializer(case).data, status=status.HTTP_201_CREATED
        )


class LegalCaseDetailView(TenantQuerysetMixin, generics.RetrieveAPIView):
    queryset = LegalCase.objects.select_related("customer", "assigned_lawyer").prefetch_related(
        "case_invoices__invoice",
        "activities",
        "documents",
        "status_history",
    )
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get_permissions(self):
        if _is_external_lawyer(self.request):
            self.read_permission = Permission.MANAGE_LEGAL
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_external_lawyer(self.request):
            return qs.filter(assigned_lawyer=self.request.user)
        return qs

    def retrieve(self, request, *args, **kwargs):
        case = self.get_object()
        if _is_external_lawyer(request):
            return Response(LawyerCaseSerializer(case).data)
        return Response(LegalCaseSerializer(case).data)


class LegalCriteriaView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request, customer_id: int):
        org = get_request_organization(request)
        try:
            customer = Customer.objects.get(pk=customer_id, organization=org)
        except Customer.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = evaluate_legal_handoff_criteria(customer, organization=org)
        return Response(data)


class LegalCaseApproveView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_LEGAL

    def post(self, request, pk: int):
        org = get_request_organization(request)
        try:
            case = LegalCase.objects.get(pk=pk, organization=org)
        except LegalCase.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            case = approve_legal_case(case, approved_by=request.user)
        except LegalWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(LegalCaseSerializer(case).data)


class LegalCaseHandoffView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_LEGAL

    def post(self, request, pk: int):
        if _is_external_lawyer(request):
            return Response(status=status.HTTP_403_FORBIDDEN)
        ser = LegalCaseHandoffSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = get_request_organization(request)
        try:
            case = LegalCase.objects.get(pk=pk, organization=org)
            lawyer = User.objects.get(pk=ser.validated_data["lawyer_id"])
        except (LegalCase.DoesNotExist, User.DoesNotExist):
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            case = handoff_to_lawyer(
                case,
                lawyer=lawyer,
                changed_by=request.user,
                note=ser.validated_data.get("note") or "",
            )
        except LegalWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(LegalCaseSerializer(case).data)


class LegalCaseStatusView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_LEGAL

    def post(self, request, pk: int):
        ser = LegalCaseStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = get_request_organization(request)
        qs = LegalCase.objects.filter(organization=org, pk=pk)
        if _is_external_lawyer(request):
            qs = qs.filter(assigned_lawyer=request.user)
        case = qs.first()
        if case is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            case = transition_legal_case(
                case,
                to_status=ser.validated_data["status"],
                changed_by=request.user,
                note=ser.validated_data.get("note") or "",
            )
        except LegalWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _is_external_lawyer(request):
            return Response(LawyerCaseSerializer(case).data)
        return Response(LegalCaseSerializer(case).data)


class LegalCasePackageView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_LEGAL

    def post(self, request, pk: int):
        if _is_external_lawyer(request):
            return Response(
                {"detail": "Paket üretimi yalnızca iç ekip içindir."},
                status=status.HTTP_403_FORBIDDEN,
            )
        org = get_request_organization(request)
        try:
            case = LegalCase.objects.get(pk=pk, organization=org)
        except LegalCase.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        path = generate_legal_package(case)
        return Response(
            {
                "package_path": str(path),
                "package_generated_at": case.package_generated_at,
                "download_url": f"/api/legal/cases/{case.id}/package/download/",
            }
        )


class LegalCasePackageDownloadView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_LEGAL

    def get(self, request, pk: int):
        if _is_external_lawyer(request):
            return Response(status=status.HTTP_403_FORBIDDEN)
        org = get_request_organization(request)
        try:
            case = LegalCase.objects.get(pk=pk, organization=org)
        except LegalCase.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not case.package_path:
            return Response(
                {"detail": "Paket henüz üretilmedi."},
                status=status.HTTP_404_NOT_FOUND,
            )
        path = Path(case.package_path)
        if not path.is_file():
            return Response(
                {"detail": "Paket dosyası bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(
            path.open("rb"),
            as_attachment=True,
            filename=path.name,
            content_type="application/zip",
        )


class LegalCaseActivityCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_LEGAL

    def post(self, request, pk: int):
        ser = LegalActivityCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = get_request_organization(request)
        qs = LegalCase.objects.filter(organization=org, pk=pk)
        if _is_external_lawyer(request):
            qs = qs.filter(assigned_lawyer=request.user)
        case = qs.first()
        if case is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        activity = add_activity(
            case,
            summary=ser.validated_data["summary"],
            notes=ser.validated_data.get("notes") or "",
            created_by=request.user,
            is_lawyer_visible=True,
        )
        from apps.legal.serializers import LegalCaseActivitySerializer

        return Response(
            LegalCaseActivitySerializer(activity).data,
            status=status.HTTP_201_CREATED,
        )


class LegalCaseDocumentUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_LEGAL

    def post(self, request, pk: int):
        org = get_request_organization(request)
        qs = LegalCase.objects.filter(organization=org, pk=pk)
        if _is_external_lawyer(request):
            qs = qs.filter(assigned_lawyer=request.user)
        case = qs.first()
        if case is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response(
                {"detail": "file alanı zorunlu."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            doc = store_legal_document(
                case,
                uploaded_file=uploaded,
                uploaded_by=request.user,
                notes=request.data.get("notes") or "",
            )
        except LegalWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.legal.serializers import LegalCaseDocumentSerializer

        return Response(
            LegalCaseDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )
