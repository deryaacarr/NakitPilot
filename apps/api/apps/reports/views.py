from pathlib import Path

from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.reports.exports import (
    collect_report_rows,
    create_export_job,
    enqueue_export_job,
)
from apps.reports.models import ExportJob, ExportJobStatus, ReportType
from apps.reports.serializers import ExportCreateSerializer, ExportJobSerializer


class ReportPreviewView(TenantQuerysetMixin, APIView):
    """GET /api/reports/<report_type>/ — JSON preview (max 500 rows)."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    REPORT_MAP = {
        "overdue-receivables": ReportType.OVERDUE_RECEIVABLES,
        "collection-activity": ReportType.COLLECTION_ACTIVITY,
        "customer-risk": ReportType.CUSTOMER_RISK,
        "dispute-resolution": ReportType.DISPUTE_RESOLUTION,
    }

    def get(self, request, report_slug: str):
        report_type = self.REPORT_MAP.get(report_slug)
        if not report_type:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        filters = {k: v for k, v in request.query_params.items()}
        rows = collect_report_rows(self.get_current_organization(), report_type, filters)
        return Response({"count": len(rows), "results": rows[:500]})


class ExportJobListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    """GET/POST /api/reports/exports/"""

    queryset = ExportJob.objects.select_related("requested_by").all()
    serializer_class = ExportJobSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def create(self, request, *args, **kwargs):
        ser = ExportCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        organization = self.get_current_organization()
        job = create_export_job(
            organization=organization,
            report_type=ser.validated_data["report_type"],
            filters=ser.validated_data.get("filters") or {},
            requested_by=request.user,
        )
        job = enqueue_export_job(job)
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ExportJobDetailView(TenantQuerysetMixin, generics.RetrieveAPIView):
    queryset = ExportJob.objects.select_related("requested_by").all()
    serializer_class = ExportJobSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS


class ExportJobDownloadView(TenantQuerysetMixin, APIView):
    """GET /api/reports/exports/<id>/download/"""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request, pk: int):
        organization = self.get_current_organization()
        try:
            job = ExportJob.objects.for_organization(organization).get(pk=pk)
        except ExportJob.DoesNotExist as exc:
            raise Http404() from exc

        if job.status == ExportJobStatus.EXPIRED or (
            job.expires_at and job.expires_at <= timezone.now()
        ):
            if job.status != ExportJobStatus.EXPIRED:
                job.status = ExportJobStatus.EXPIRED
                job.save(update_fields=["status", "updated_at"])
            return Response(
                {"code": "expired", "detail": "Dışa aktarma süresi doldu."},
                status=status.HTTP_410_GONE,
            )

        if job.status == ExportJobStatus.PREPARING:
            return Response(
                {"code": "preparing", "detail": "Rapor hazırlanıyor."},
                status=status.HTTP_409_CONFLICT,
            )
        if job.status == ExportJobStatus.FAILED:
            return Response(
                {"code": "failed", "detail": job.error_message or "Rapor oluşturulamadı."},
                status=status.HTTP_409_CONFLICT,
            )
        if not job.is_downloadable:
            return Response(
                {"code": "not_ready", "detail": "Dosya indirilemiyor."},
                status=status.HTTP_409_CONFLICT,
            )

        path = Path(job.stored_path)
        if not path.is_file():
            return Response(
                {"code": "missing_file", "detail": "Dosya bulunamadı."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            path.open("rb"),
            as_attachment=True,
            filename=job.original_filename or path.name,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
