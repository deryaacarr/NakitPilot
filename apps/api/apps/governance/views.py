"""EPIC 30/31 governance API."""

from __future__ import annotations

from pathlib import Path

from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.subscription_service import Feature, can_use
from apps.governance.access import access_report, record_access
from apps.governance.approvals import ApprovalError, decide_approval, request_approval
from apps.governance.deletion import DeletionError, cancel_deletion, process_due_deletions, request_deletion
from apps.governance.exports import ALLOWED_DATASETS, run_export_job
from apps.governance.inventory import inventory_as_list
from apps.governance.masking import mask_email_display, mask_phone_display, mask_tax_display
from apps.governance.models import (
    ApprovalRequest,
    ApprovalStatus,
    DataAccessAction,
    DataExportJob,
    DataExportStatus,
    DeletionRequest,
)
from apps.governance.retention import apply_retention_purge, ensure_retention_policy, policy_as_dict
from apps.governance.sessions import list_sessions, revoke_all_sessions, revoke_session
from apps.governance.sso import SSOError, list_providers, sso_login_options, upsert_provider
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class ApprovalListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        org = get_request_organization(request)
        qs = ApprovalRequest.objects.filter(organization=org).order_by("-created_at")[:50]
        return Response(
            {
                "results": [
                    {
                        "id": a.id,
                        "action_type": a.action_type,
                        "status": a.status,
                        "requested_by": a.requested_by_id,
                        "reason": a.reason,
                        "payload": a.payload,
                        "created_at": a.created_at.isoformat(),
                        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                    }
                    for a in qs
                ]
            }
        )

    def post(self, request):
        org = get_request_organization(request)
        action_type = (request.data.get("action_type") or "").strip()
        if not action_type:
            return Response({"detail": "action_type required"}, status=400)
        a = request_approval(
            org,
            action_type=action_type,
            requested_by=request.user,
            payload=request.data.get("payload") or {},
            reason=request.data.get("reason") or "",
        )
        return Response({"id": a.id, "status": a.status, "action_type": a.action_type}, status=201)


class ApprovalDecideView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request, pk: int):
        org = get_request_organization(request)
        a = ApprovalRequest.objects.filter(organization=org, pk=pk).first()
        if a is None:
            return Response({"detail": "Not found"}, status=404)
        try:
            decide_approval(
                a,
                decided_by=request.user,
                approve=bool(request.data.get("approve", True)),
                note=request.data.get("note") or "",
            )
        except ApprovalError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=400)
        return Response({"id": a.id, "status": a.status})


class SSOProviderView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        org = get_request_organization(request)
        return Response({"results": list_providers(org)})

    def post(self, request):
        org = get_request_organization(request)
        try:
            p = upsert_provider(
                org,
                protocol=request.data.get("protocol") or "",
                name=(request.data.get("name") or "").strip() or "SSO",
                is_enabled=bool(request.data.get("is_enabled")),
                issuer_url=request.data.get("issuer_url") or "",
                client_id=request.data.get("client_id") or "",
                metadata_url=request.data.get("metadata_url") or "",
                entity_id=request.data.get("entity_id") or "",
                acs_url=request.data.get("acs_url") or "",
                domains=request.data.get("domains") or [],
            )
        except SSOError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=403 if exc.code == "entitlement_denied" else 400)
        return Response({"id": p.id, "protocol": p.protocol, "name": p.name, "is_enabled": p.is_enabled}, status=201)


class SSODiscoverView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        domain = (request.query_params.get("domain") or "").strip()
        return Response({"results": sso_login_options(domain)})


class SSOStartView(APIView):
    """NP-304 — stub start endpoint (redirect URL for IdP)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, protocol: str):
        org_id = request.query_params.get("org")
        return Response(
            {
                "protocol": protocol.upper(),
                "organization_id": org_id,
                "status": "stub",
                "detail": "SSO başlatma uç noktası yapılandırıldı; IdP yönlendirmesi entegrasyonla tamamlanır.",
                "supported": ["SAML", "OIDC", "GOOGLE_WORKSPACE", "MICROSOFT_ENTRA"],
            }
        )


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"results": list_sessions(request.user)})


class SessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        ok = revoke_session(request.user, pk)
        if not ok:
            return Response({"detail": "Not found"}, status=404)
        return Response({"revoked": True})


class SessionRevokeAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = revoke_all_sessions(request.user)
        return Response({"revoked_count": count})


class RetentionPolicyView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        org = get_request_organization(request)
        if not can_use(org, Feature.DATA_GOVERNANCE).allowed:
            return Response({"detail": "Veri yönetişimi bu pakette yok."}, status=403)
        return Response(policy_as_dict(ensure_retention_policy(org)))

    def patch(self, request):
        org = get_request_organization(request)
        if not can_use(org, Feature.DATA_GOVERNANCE).allowed:
            return Response({"detail": "Veri yönetişimi bu pakette yok."}, status=403)
        policy = ensure_retention_policy(org)
        for field in (
            "activity_logs_days",
            "audit_logs_days",
            "import_files_days",
            "failed_webhook_bodies_days",
            "ai_requests_days",
            "deleted_user_data_days",
        ):
            if field in request.data:
                setattr(policy, field, int(request.data[field]))
        policy.save()
        return Response(policy_as_dict(policy))


class RetentionPurgeView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        org = get_request_organization(request)
        return Response({"deleted": apply_retention_purge(org)})


class DataExportView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        org = get_request_organization(request)
        jobs = DataExportJob.objects.filter(organization=org).order_by("-created_at")[:20]
        return Response(
            {
                "results": [
                    {
                        "id": j.id,
                        "datasets": j.datasets,
                        "status": j.status,
                        "row_counts": j.row_counts,
                        "created_at": j.created_at.isoformat(),
                        "expires_at": j.expires_at.isoformat() if j.expires_at else None,
                    }
                    for j in jobs
                ]
            }
        )

    def post(self, request):
        org = get_request_organization(request)
        if not can_use(org, Feature.DATA_GOVERNANCE).allowed:
            return Response({"detail": "Veri dışa aktarma bu pakette yok."}, status=403)
        datasets = request.data.get("datasets") or list(ALLOWED_DATASETS)
        datasets = [d for d in datasets if d in ALLOWED_DATASETS]
        if not datasets:
            return Response({"detail": "datasets required"}, status=400)
        job = DataExportJob.objects.create(
            organization=org,
            requested_by=request.user,
            datasets=datasets,
            status=DataExportStatus.PENDING,
        )
        job = run_export_job(job)
        record_access(
            org,
            actor=request.user,
            action=DataAccessAction.EXPORT_DATA,
            resource_type="data_export",
            resource_id=job.id,
            summary="Organizasyon veri dışa aktarma",
            metadata={"datasets": datasets},
        )
        return Response(
            {
                "id": job.id,
                "status": job.status,
                "row_counts": job.row_counts,
                "download": f"/api/governance/exports/{job.id}/download/",
            },
            status=201,
        )


class DataExportDownloadView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS

    def get(self, request, pk: int):
        org = get_request_organization(request)
        job = DataExportJob.objects.filter(organization=org, pk=pk).first()
        if job is None or job.status != DataExportStatus.READY or not job.file_path:
            raise Http404
        path = Path(job.file_path)
        if not path.exists():
            raise Http404
        return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)


class DeletionRequestView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        org = get_request_organization(request)
        rows = DeletionRequest.objects.filter(organization=org).order_by("-created_at")[:20]
        return Response(
            {
                "results": [
                    {
                        "id": r.id,
                        "target_type": r.target_type,
                        "target_id": r.target_id,
                        "status": r.status,
                        "waiting_until": r.waiting_until.isoformat() if r.waiting_until else None,
                        "completion_report": r.completion_report,
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in rows
                ]
            }
        )

    def post(self, request):
        org = get_request_organization(request)
        try:
            req = request_deletion(
                org,
                target_type=request.data.get("target_type") or "organization",
                target_id=str(request.data.get("target_id") or org.pk),
                requested_by=request.user,
                reason=request.data.get("reason") or "",
            )
        except DeletionError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=400)
        return Response(
            {
                "id": req.id,
                "status": req.status,
                "waiting_until": req.waiting_until.isoformat() if req.waiting_until else None,
            },
            status=201,
        )


class DeletionCancelView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request, pk: int):
        org = get_request_organization(request)
        req = DeletionRequest.objects.filter(organization=org, pk=pk).first()
        if req is None:
            return Response({"detail": "Not found"}, status=404)
        try:
            cancel_deletion(req)
        except DeletionError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=400)
        return Response({"id": req.id, "status": req.status})


class DeletionProcessView(APIView):
    permission_classes = [IsAuthenticated]
    # staff-only process for cron simulation
    def post(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Staff only"}, status=403)
        return Response({"results": process_due_deletions()})


class MaskPreviewView(APIView):
    """NP-313 — preview masking formats."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {
                "phone": mask_phone_display(request.data.get("phone") or ""),
                "email": mask_email_display(request.data.get("email") or ""),
                "tax_number": mask_tax_display(request.data.get("tax_number") or ""),
            }
        )


class AccessReportView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        org = get_request_organization(request)
        return Response({"results": access_report(org)})

    def post(self, request):
        org = get_request_organization(request)
        event = record_access(
            org,
            actor=request.user,
            action=request.data.get("action") or DataAccessAction.VIEW_CUSTOMER,
            resource_type=request.data.get("resource_type") or "customer",
            resource_id=request.data.get("resource_id") or "",
            summary=request.data.get("summary") or "",
            metadata=request.data.get("metadata") if isinstance(request.data.get("metadata"), dict) else {},
        )
        return Response({"id": event.id}, status=201)


class ProcessingInventoryView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        org = get_request_organization(request)
        if not can_use(org, Feature.DATA_GOVERNANCE).allowed:
            return Response({"detail": "Veri envanteri bu pakette yok."}, status=403)
        return Response({"results": inventory_as_list(org)})
