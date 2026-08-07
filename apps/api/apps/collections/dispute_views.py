"""NP-250–254 — dispute HTTP API (workflow, attachments, resolve)."""

from __future__ import annotations

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.collections.dispute_serializers import DisputeSerializer
from apps.collections.dispute_workflow import (
    DisputeWorkflowError,
    add_dispute_attachment,
    serialize_attachment,
    transition_dispute,
)
from apps.collections.models import (
    DISPUTE_ACTIVE_STATUSES,
    Dispute,
    DisputeAttachment,
    DisputeAttachmentKind,
    DisputeCategory,
    DisputeStatus,
)
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class DisputeListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = Dispute.objects.select_related(
        "customer", "invoice", "assigned_user"
    ).all()
    serializer_class = DisputeSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        invoice_id = self.request.query_params.get("invoice_id")
        if invoice_id:
            qs = qs.filter(invoice_id=invoice_id)
        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        open_only = (self.request.query_params.get("open") or "").strip().lower()
        if open_only in {"1", "true", "yes"}:
            qs = qs.filter(status__in=DISPUTE_ACTIVE_STATUSES)
        return qs

    def perform_create(self, serializer):
        organization = get_request_organization(self.request)
        customer = serializer.validated_data["customer"]
        if customer.organization_id != organization.id:
            raise ValidationError({"customer": "Müşteri bu organizasyona ait değil."})
        invoice = serializer.validated_data.get("invoice")
        if invoice is not None and invoice.organization_id != organization.id:
            raise ValidationError({"invoice": "Fatura bu organizasyona ait değil."})
        serializer.save(organization=organization, created_by=self.request.user)


class DisputeDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Dispute.objects.select_related(
        "customer", "invoice", "assigned_user"
    ).prefetch_related("attachments", "status_events").all()
    serializer_class = DisputeSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def perform_update(self, serializer):
        instance = self.get_object()
        previous_status = instance.status
        new_status = serializer.validated_data.pop("status", None)
        note = self.request.data.get("transition_note") or ""
        resolution_note = serializer.validated_data.get("resolution_note")
        serializer.save()
        if new_status and new_status != previous_status:
            try:
                transition_dispute(
                    instance,
                    to_status=new_status,
                    actor=self.request.user,
                    note=str(note),
                    resolution_note=(resolution_note or instance.resolution_note or ""),
                )
            except DisputeWorkflowError as exc:
                raise ValidationError({"status": exc.message}) from exc


class DisputeCategoryListView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        return Response(
            {"results": [{"value": c.value, "label": c.label} for c in DisputeCategory]}
        )


class DisputeStatusListView(APIView):
    """NP-251 — workflow status catalog."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        return Response(
            {
                "results": [{"value": s.value, "label": s.label} for s in DisputeStatus],
                "active": sorted(DISPUTE_ACTIVE_STATUSES),
            }
        )


class DisputeTransitionView(APIView):
    """POST /api/disputes/{id}/transition/ — NP-251."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        dispute = Dispute.objects.for_organization(organization).filter(pk=pk).first()
        if dispute is None:
            return Response({"detail": "Not found."}, status=404)
        try:
            dispute = transition_dispute(
                dispute,
                to_status=request.data.get("status") or "",
                actor=request.user,
                note=(request.data.get("note") or "").strip(),
                resolution_note=(request.data.get("resolution_note") or "").strip(),
            )
        except DisputeWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(DisputeSerializer(dispute).data)


class DisputeResolveView(APIView):
    """POST /api/disputes/{id}/resolve/"""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        dispute = Dispute.objects.for_organization(organization).filter(pk=pk).first()
        if dispute is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        status_value = (request.data.get("status") or DisputeStatus.RESOLVED).strip().upper()
        if status_value not in {
            DisputeStatus.RESOLVED,
            DisputeStatus.REJECTED,
            DisputeStatus.CANCELLED,
        }:
            return Response(
                {"detail": "status must be RESOLVED, REJECTED or CANCELLED."},
                status=400,
            )
        try:
            dispute = transition_dispute(
                dispute,
                to_status=status_value,
                actor=request.user,
                note=(request.data.get("note") or "").strip(),
                resolution_note=(request.data.get("resolution_note") or "").strip(),
            )
        except DisputeWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(DisputeSerializer(dispute).data)


class DisputeAttachmentListCreateView(APIView):
    """GET/POST /api/disputes/{id}/attachments/ — NP-253."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        dispute = Dispute.objects.for_organization(organization).filter(pk=pk).first()
        if dispute is None:
            return Response({"detail": "Not found."}, status=404)
        rows = [
            serialize_attachment(a)
            for a in dispute.attachments.all().order_by("-created_at")
        ]
        return Response({"results": rows})

    def post(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        dispute = Dispute.objects.for_organization(organization).filter(pk=pk).first()
        if dispute is None:
            return Response({"detail": "Not found."}, status=404)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "file required"}, status=400)
        content = upload.read()
        try:
            att = add_dispute_attachment(
                dispute,
                kind=request.data.get("kind") or DisputeAttachmentKind.PDF,
                filename=upload.name,
                content=content,
                actor=request.user,
                notes=(request.data.get("notes") or "").strip(),
                content_type=getattr(upload, "content_type", "") or "",
            )
        except DisputeWorkflowError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serialize_attachment(att), status=status.HTTP_201_CREATED)


class DisputeAttachmentKindListView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        return Response(
            {
                "results": [
                    {"value": k.value, "label": k.label} for k in DisputeAttachmentKind
                ]
            }
        )


class DisputeAttachmentDeleteView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def delete(self, request, pk: int, attachment_id: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        att = (
            DisputeAttachment.objects.for_organization(organization)
            .filter(pk=attachment_id, dispute_id=pk)
            .first()
        )
        if att is None:
            return Response({"detail": "Not found."}, status=404)
        att.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
