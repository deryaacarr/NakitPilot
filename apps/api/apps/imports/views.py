from django.db import IntegrityError
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import write_audit_log
from apps.imports.models import DuplicatePolicy, ImportJob, ImportJobStatus, ImportType
from apps.imports.schema import CANONICAL_COLUMNS, FIELD_LABELS, REQUIRED_FIELDS, suggest_mapping
from apps.imports.serializers import (
    ColumnMappingSerializer,
    CommitImportSerializer,
    ImportJobSerializer,
)
from apps.imports.services import (
    UploadValidationError,
    build_errors_workbook,
    build_invoice_template_bytes,
    ensure_required_headers_present,
    file_sha256,
    preview_import,
    read_tabular_file,
    store_upload,
    validate_upload_file,
)
from apps.imports.tasks import process_import_job_task
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization
from apps.security.throttles import ImportUploadThrottle


class InvoiceImportTemplateView(APIView):
    """GET /api/imports/invoices/template/ — NP-060 sample Excel."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        content = build_invoice_template_bytes()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="nakitpilot_fatura_sablonu.xlsx"'
        return response


class InvoiceImportUploadView(TenantQuerysetMixin, APIView):
    """POST /api/imports/invoices/upload — NP-061 / NP-152."""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.ADD_INVOICE
    read_permission = Permission.VIEW_REPORTS
    throttle_classes = [ImportUploadThrottle]

    def post(self, request):
        organization = self.get_current_organization()
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"code": "missing_file", "detail": "Dosya gerekli (field: file)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content = upload.read()
        try:
            filename = validate_upload_file(
                filename=upload.name,
                size=upload.size,
                content_type=getattr(upload, "content_type", "") or "",
                content=content,
            )
            digest = file_sha256(content)
            if (
                ImportJob.objects.filter(organization=organization, file_hash=digest)
                .exclude(status=ImportJobStatus.CANCELLED)
                .exists()
            ):
                raise UploadValidationError(
                    "Aynı dosya daha önce yüklendi.",
                    "duplicate_file",
                )

            stored_path = store_upload(
                organization_id=organization.id,
                filename=filename,
                content=content,
            )
            headers, rows = read_tabular_file(stored_path)
            ensure_required_headers_present(headers)
            mapping = suggest_mapping(headers)
        except UploadValidationError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job = ImportJob(
            organization=organization,
            import_type=ImportType.INVOICES,
            status=ImportJobStatus.PENDING,
            original_filename=filename,
            stored_path=stored_path,
            content_type=getattr(upload, "content_type", "") or "",
            file_size=len(content),
            file_hash=digest,
            headers=headers,
            column_mapping=mapping,
            total_rows=len(rows),
            uploaded_by=request.user,
        )
        try:
            job.save()
        except IntegrityError:
            return Response(
                {"code": "duplicate_file", "detail": "Aynı dosya daha önce yüklendi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        write_audit_log(
            organization=organization,
            actor=request.user,
            action="import.upload",
            entity_type="ImportJob",
            entity_id=job.id,
            summary=f"İçe aktarma dosyası yüklendi: {filename}",
            changes={
                "original_filename": filename,
                "file_size": job.file_size,
                "file_hash": digest,
            },
        )

        serializer = ImportJobSerializer(job)
        unmapped_required = [f for f in REQUIRED_FIELDS if not mapping.get(f)]
        return Response(
            {
                "job": serializer.data,
                "suggested_mapping": mapping,
                "unmapped_required": unmapped_required,
                "canonical_fields": [
                    {"key": k, "label": FIELD_LABELS[k], "required": k in REQUIRED_FIELDS}
                    for k in CANONICAL_COLUMNS
                ],
            },
            status=status.HTTP_201_CREATED,
        )


class ImportJobDetailView(TenantQuerysetMixin, generics.RetrieveAPIView):
    queryset = ImportJob.objects.select_related("uploaded_by").all()
    serializer_class = ImportJobSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_INVOICE


class ImportMappingView(TenantQuerysetMixin, APIView):
    """PATCH /api/imports/{id}/mapping/ — NP-062."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.ADD_INVOICE
    read_permission = Permission.VIEW_REPORTS

    def patch(self, request, pk: int):
        organization = get_request_organization(request) or self.get_current_organization()
        try:
            job = ImportJob.objects.for_organization(organization).get(pk=pk)
        except ImportJob.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if job.status in {
            ImportJobStatus.PROCESSING,
            ImportJobStatus.COMPLETED,
            ImportJobStatus.FAILED,
        }:
            return Response(
                {"code": "invalid_status", "detail": "Bu aşamada eşleme değiştirilemez."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ColumnMappingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mapping = serializer.validated_data["column_mapping"]

        headers_set = set(job.headers)
        for canonical, source in mapping.items():
            if source and source not in headers_set:
                return Response(
                    {
                        "code": "unknown_header",
                        "detail": f"'{source}' dosya başlıklarında yok ({canonical}).",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        job.column_mapping = mapping
        job.status = ImportJobStatus.PENDING
        job.save(update_fields=["column_mapping", "status", "updated_at"])
        unmapped_required = [f for f in REQUIRED_FIELDS if not mapping.get(f)]
        return Response(
            {
                "job": ImportJobSerializer(job).data,
                "unmapped_required": unmapped_required,
            }
        )


class ImportPreviewView(TenantQuerysetMixin, APIView):
    """POST /api/imports/{id}/preview/ — NP-063/064 (no DB write of customers/invoices)."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.ADD_INVOICE
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        organization = self.get_current_organization()
        try:
            job = ImportJob.objects.for_organization(organization).get(pk=pk)
        except ImportJob.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if job.status in {
            ImportJobStatus.PROCESSING,
            ImportJobStatus.COMPLETED,
        }:
            return Response(
                {"code": "invalid_status", "detail": "İşlem tamamlandı veya sürüyor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mapping = job.column_mapping
        if isinstance(request.data, dict) and request.data.get("column_mapping"):
            ser = ColumnMappingSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            mapping = ser.validated_data["column_mapping"]
            job.column_mapping = mapping

        if isinstance(request.data, dict) and request.data.get("duplicate_policy"):
            policy = str(request.data["duplicate_policy"]).upper()
            if policy in DuplicatePolicy.values:
                job.duplicate_policy = policy

        job.status = ImportJobStatus.VALIDATING
        job.save(update_fields=["column_mapping", "duplicate_policy", "status", "updated_at"])

        try:
            result = preview_import(job, mapping=mapping)
        except UploadValidationError as exc:
            job.status = ImportJobStatus.FAILED
            job.error_message = exc.message
            job.save(update_fields=["status", "error_message", "updated_at"])
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        summary = result["summary"]
        job.preview_summary = summary
        job.preview_errors = result["errors"]
        job.total_rows = summary["total_rows"]
        job.valid_rows = summary["valid_rows"]
        job.invalid_rows = summary["invalid_rows"]
        job.status = ImportJobStatus.READY
        job.error_message = ""
        job.save(
            update_fields=[
                "column_mapping",
                "duplicate_policy",
                "preview_summary",
                "preview_errors",
                "total_rows",
                "valid_rows",
                "invalid_rows",
                "status",
                "error_message",
                "updated_at",
            ]
        )

        return Response(
            {
                "job": ImportJobSerializer(job).data,
                "summary": summary,
                "errors": result["errors"],
                "mapping": result["mapping"],
            }
        )


class ImportCommitView(TenantQuerysetMixin, APIView):
    """POST /api/imports/{id}/commit/ — NP-066 enqueue Celery processing."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.ADD_INVOICE
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        organization = self.get_current_organization()
        try:
            job = ImportJob.objects.for_organization(organization).get(pk=pk)
        except ImportJob.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if job.status != ImportJobStatus.READY:
            return Response(
                {
                    "code": "invalid_status",
                    "detail": "Yalnızca READY durumundaki işler başlatılabilir.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = CommitImportSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        policy = ser.validated_data.get("duplicate_policy")
        if policy:
            job.duplicate_policy = policy

        job.status = ImportJobStatus.PROCESSING
        job.save(update_fields=["duplicate_policy", "status", "updated_at"])

        async_result = process_import_job_task.delay(job.id)
        job.celery_task_id = async_result.id or ""
        job.save(update_fields=["celery_task_id", "updated_at"])

        write_audit_log(
            organization=organization,
            actor=request.user,
            action="import.commit",
            entity_type="ImportJob",
            entity_id=job.id,
            summary=f"İçe aktarma başlatıldı: {job.original_filename}",
            changes={
                "duplicate_policy": job.duplicate_policy,
                "celery_task_id": job.celery_task_id,
            },
        )

        return Response(
            {
                "job": ImportJobSerializer(job).data,
                "task_id": job.celery_task_id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ImportErrorsExportView(TenantQuerysetMixin, APIView):
    """GET /api/imports/{id}/errors/export/ — NP-067 Excel download."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.ADD_INVOICE

    def get(self, request, pk: int):
        organization = self.get_current_organization()
        try:
            job = ImportJob.objects.for_organization(organization).get(pk=pk)
        except ImportJob.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        content = build_errors_workbook(job)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="import_{job.id}_hatalar.xlsx"'
        )
        return response


class CanonicalImportFieldsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "fields": [
                    {
                        "key": key,
                        "label": FIELD_LABELS[key],
                        "required": key in REQUIRED_FIELDS,
                    }
                    for key in CANONICAL_COLUMNS
                ]
            }
        )
