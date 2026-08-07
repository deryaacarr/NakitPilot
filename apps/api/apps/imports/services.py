"""Import preview + Celery commit orchestration."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook

from apps.customers.models import Customer
from apps.imports.models import (
    DuplicatePolicy,
    ImportError,
    ImportErrorKind,
    ImportJob,
    ImportJobStatus,
)
from apps.imports.schema import REQUIRED_FIELDS, suggest_mapping
from apps.imports.services_io import (  # noqa: F401
    UploadValidationError,
    build_invoice_template_bytes,
    ensure_required_headers_present,
    file_sha256,
    read_tabular_file,
    sanitize_filename,
    store_upload,
    validate_upload_file,
)
from apps.imports.validation import validate_all_rows
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.services import compute_invoice_status

ZERO = Decimal("0.00")


def preview_import(
    job: ImportJob,
    *,
    mapping: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Validate rows without writing customers/invoices (NP-063/064/065)."""
    mapping = mapping or job.column_mapping or suggest_mapping(job.headers)
    missing_required = [f for f in REQUIRED_FIELDS if not mapping.get(f)]
    if missing_required:
        raise UploadValidationError(
            f"Eşlenmemiş zorunlu alanlar: {', '.join(missing_required)}",
            "incomplete_mapping",
        )

    _headers, rows = read_tabular_file(job.stored_path)
    validated = validate_all_rows(rows=rows, mapping=mapping, organization=job.organization)

    errors: list[dict[str, Any]] = []
    new_customers = 0
    new_invoices = 0
    likely_duplicates = 0
    seen_new_codes: set[str] = set()
    seen_new_names: set[str] = set()

    for row in validated:
        for issue in row.issues:
            if issue.kind == "VALIDATION" or (
                issue.kind == "DUPLICATE" and job.duplicate_policy == DuplicatePolicy.SKIP
            ):
                errors.append(
                    {
                        "row_number": issue.row_number,
                        "field_name": issue.field_name,
                        "raw_value": issue.raw_value,
                        "error_message": issue.error_message,
                        "kind": issue.kind,
                    }
                )

        if row.has_validation_errors:
            continue

        if row.is_duplicate:
            likely_duplicates += 1
            if job.duplicate_policy == DuplicatePolicy.SKIP:
                continue
            if job.duplicate_policy == DuplicatePolicy.CREATE:
                new_invoices += 1
            continue

        new_invoices += 1
        if row.existing_customer is None:
            key_code = row.customer_code
            key_name = row.customer_name.casefold()
            already = (key_code and key_code in seen_new_codes) or (
                key_name and key_name in seen_new_names
            )
            if not already:
                new_customers += 1
                if key_code:
                    seen_new_codes.add(key_code)
                if key_name:
                    seen_new_names.add(key_name)

    invalid = sum(1 for r in validated if r.has_validation_errors)
    skipped_dup_preview = sum(
        1
        for r in validated
        if r.is_duplicate
        and not r.has_validation_errors
        and job.duplicate_policy == DuplicatePolicy.SKIP
    )
    summary = {
        "total_rows": len(rows),
        "valid_rows": len(rows) - invalid - skipped_dup_preview,
        "invalid_rows": invalid,
        "new_customer_count": new_customers,
        "new_invoice_count": new_invoices,
        "likely_duplicate_count": likely_duplicates,
        "skipped_duplicate_count": skipped_dup_preview,
        "error_count": len(errors),
        "duplicate_policy": job.duplicate_policy,
    }

    return {
        "summary": summary,
        "errors": errors[:500],
        "mapping": mapping,
    }


def process_import_job(job_id: int) -> dict[str, Any]:
    """
    Commit validated rows to DB (NP-066). Called from Celery worker.
    """
    try:
        job = ImportJob.objects.select_related("organization").get(pk=job_id)
    except ImportJob.DoesNotExist:
        return {"ok": False, "detail": "Job not found"}

    if job.status not in {ImportJobStatus.READY, ImportJobStatus.PROCESSING}:
        return {"ok": False, "detail": f"Unexpected status {job.status}"}

    job.status = ImportJobStatus.PROCESSING
    job.save(update_fields=["status", "updated_at"])

    try:
        mapping = job.column_mapping or suggest_mapping(job.headers)
        _headers, rows = read_tabular_file(job.stored_path)
        validated = validate_all_rows(
            rows=rows,
            mapping=mapping,
            organization=job.organization,
        )

        ImportError.objects.filter(job=job).delete()

        successful = 0
        failed = 0
        skipped = 0
        error_rows: list[ImportError] = []
        touched_customer_ids: set[int] = set()

        with transaction.atomic():
            for row in validated:
                if row.has_validation_errors:
                    failed += 1
                    for issue in row.issues:
                        if issue.kind != "VALIDATION":
                            continue
                        error_rows.append(
                            ImportError(
                                organization=job.organization,
                                job=job,
                                row_number=issue.row_number,
                                field_name=issue.field_name,
                                raw_value=issue.raw_value,
                                error_message=issue.error_message,
                                kind=ImportErrorKind.VALIDATION,
                            )
                        )
                    continue

                if row.is_duplicate:
                    if job.duplicate_policy == DuplicatePolicy.SKIP:
                        skipped += 1
                        error_rows.append(
                            ImportError(
                                organization=job.organization,
                                job=job,
                                row_number=row.row_number,
                                field_name="fatura_numarası",
                                raw_value=row.invoice_number,
                                error_message="Aynı fatura daha önce eklenmiş (atlandı)",
                                kind=ImportErrorKind.SKIPPED,
                            )
                        )
                        continue
                    if job.duplicate_policy == DuplicatePolicy.UPDATE:
                        target = row.existing_invoice or Invoice.objects.filter(
                            organization=job.organization,
                            number=row.invoice_number,
                        ).first()
                        if target is None:
                            failed += 1
                            error_rows.append(
                                ImportError(
                                    organization=job.organization,
                                    job=job,
                                    row_number=row.row_number,
                                    field_name="fatura_numarası",
                                    raw_value=row.invoice_number,
                                    error_message="Güncellenecek fatura bulunamadı",
                                    kind=ImportErrorKind.VALIDATION,
                                )
                            )
                            continue
                        _update_invoice_from_row(target, row)
                        touched_customer_ids.add(target.customer_id)
                        successful += 1
                        continue
                    # CREATE: suffix if number already exists
                    if Invoice.objects.filter(
                        organization=job.organization,
                        number=row.invoice_number,
                    ).exists():
                        row.invoice_number = f"{row.invoice_number}-IMP{row.row_number}"

                # Org-unique number without matching NP-065 key
                existing_by_number = Invoice.objects.filter(
                    organization=job.organization,
                    number=row.invoice_number,
                ).first()
                if existing_by_number is not None:
                    if job.duplicate_policy == DuplicatePolicy.SKIP:
                        skipped += 1
                        error_rows.append(
                            ImportError(
                                organization=job.organization,
                                job=job,
                                row_number=row.row_number,
                                field_name="fatura_numarası",
                                raw_value=row.invoice_number,
                                error_message="Aynı fatura daha önce eklenmiş (atlandı)",
                                kind=ImportErrorKind.SKIPPED,
                            )
                        )
                        continue
                    if job.duplicate_policy == DuplicatePolicy.UPDATE:
                        _update_invoice_from_row(existing_by_number, row)
                        touched_customer_ids.add(existing_by_number.customer_id)
                        successful += 1
                        continue
                    row.invoice_number = f"{row.invoice_number}-IMP{row.row_number}"

                customer = row.existing_customer
                if customer is None:
                    customer = Customer.objects.create(
                        organization=job.organization,
                        code=row.customer_code,
                        name=row.customer_name or row.customer_code or f"Müşteri-{row.row_number}",
                        tax_number=row.tax_number,
                        phone=row.phone,
                        email=row.email,
                        is_active=True,
                    )

                assert row.invoice_date is not None and row.due_date is not None
                assert row.total_amount is not None

                remaining = row.total_amount - (row.paid_amount or ZERO)
                if remaining < ZERO:
                    remaining = ZERO
                status_value = compute_invoice_status(
                    total_amount=row.total_amount,
                    remaining_amount=remaining,
                    due_date=row.due_date,
                )
                Invoice.objects.create(
                    organization=job.organization,
                    customer=customer,
                    number=row.invoice_number,
                    invoice_date=row.invoice_date,
                    due_date=row.due_date,
                    currency=row.currency,
                    subtotal_amount=row.total_amount,
                    tax_amount=ZERO,
                    total_amount=row.total_amount,
                    status=status_value,
                    description=f"Import #{job.id}",
                )
                touched_customer_ids.add(customer.id)
                successful += 1

            ImportError.objects.bulk_create(error_rows, batch_size=500)

            summary = {
                "successful_rows": successful,
                "failed_rows": failed,
                "skipped_duplicates": skipped,
                "total_rows": len(rows),
                "duplicate_policy": job.duplicate_policy,
            }
            job.successful_rows = successful
            job.failed_rows = failed
            job.skipped_duplicates = skipped
            job.result_summary = summary
            job.preview_errors = [
                {
                    "row_number": e.row_number,
                    "field_name": e.field_name,
                    "raw_value": e.raw_value,
                    "error_message": e.error_message,
                    "kind": e.kind,
                }
                for e in error_rows[:500]
            ]
            job.status = ImportJobStatus.COMPLETED
            job.error_message = ""
            job.save(
                update_fields=[
                    "successful_rows",
                    "failed_rows",
                    "skipped_duplicates",
                    "result_summary",
                    "preview_errors",
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )

        # NP-103: yeni/güncellenen faturalar → risk (batch sonrası)
        if touched_customer_ids:
            from apps.risk.triggers import bump_customers_risk

            bump_customers_risk(touched_customer_ids)

        from apps.notifications.services import notify_import_result

        notify_import_result(job, success=True)

        return {"ok": True, "summary": job.result_summary}
    except Exception as exc:  # noqa: BLE001 — persist failure on job
        job.status = ImportJobStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        from apps.notifications.services import notify_import_result

        notify_import_result(job, success=False)
        return {"ok": False, "detail": str(exc)}


def _update_invoice_from_row(invoice: Invoice, row) -> None:
    invoice.invoice_date = row.invoice_date
    invoice.due_date = row.due_date
    invoice.currency = row.currency
    invoice.total_amount = row.total_amount
    invoice.subtotal_amount = row.total_amount
    invoice.status = compute_invoice_status(
        total_amount=row.total_amount,
        remaining_amount=invoice.remaining_amount(),
        due_date=row.due_date,
    )
    if invoice.status == InvoiceStatus.PAID and invoice.payment_completion_date is None:
        invoice.payment_completion_date = timezone.localdate()
    invoice.save()


def build_errors_workbook(job: ImportJob) -> bytes:
    """NP-067: Excel export of import errors / skips."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Hatalar"
    ws.append(["satir", "alan", "deger", "hata", "tur"])
    qs = job.errors.all().order_by("row_number", "id")
    if not qs.exists() and job.preview_errors:
        for err in job.preview_errors:
            ws.append(
                [
                    err.get("row_number"),
                    err.get("field_name"),
                    err.get("raw_value"),
                    err.get("error_message"),
                    err.get("kind", "VALIDATION"),
                ]
            )
    else:
        for err in qs:
            ws.append(
                [
                    err.row_number,
                    err.field_name,
                    err.raw_value,
                    err.error_message,
                    err.kind,
                ]
            )
    import io

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
