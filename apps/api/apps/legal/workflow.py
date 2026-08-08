"""NP-354 status transitions + case helpers."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.imports.services_io import private_upload_root
from apps.legal.models import (
    LEGAL_TERMINAL_STATUSES,
    LegalCase,
    LegalCaseActivity,
    LegalCaseDocument,
    LegalCaseStatus,
    LegalCaseStatusHistory,
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    LegalCaseStatus.PREPARING: {
        LegalCaseStatus.HANDED_TO_LAWYER,
        LegalCaseStatus.CLOSED,
    },
    LegalCaseStatus.HANDED_TO_LAWYER: {
        LegalCaseStatus.NOTICE,
        LegalCaseStatus.MEDIATION,
        LegalCaseStatus.CLOSED,
    },
    LegalCaseStatus.NOTICE: {
        LegalCaseStatus.MEDIATION,
        LegalCaseStatus.LAWSUIT,
        LegalCaseStatus.ENFORCEMENT,
        LegalCaseStatus.COLLECTED,
        LegalCaseStatus.CLOSED,
    },
    LegalCaseStatus.MEDIATION: {
        LegalCaseStatus.NOTICE,
        LegalCaseStatus.LAWSUIT,
        LegalCaseStatus.ENFORCEMENT,
        LegalCaseStatus.COLLECTED,
        LegalCaseStatus.CLOSED,
    },
    LegalCaseStatus.LAWSUIT: {
        LegalCaseStatus.ENFORCEMENT,
        LegalCaseStatus.COLLECTED,
        LegalCaseStatus.CLOSED,
    },
    LegalCaseStatus.ENFORCEMENT: {
        LegalCaseStatus.COLLECTED,
        LegalCaseStatus.CLOSED,
    },
    LegalCaseStatus.COLLECTED: {LegalCaseStatus.CLOSED},
    LegalCaseStatus.CLOSED: set(),
}

DOC_MAX_BYTES = 20 * 1024 * 1024


class LegalWorkflowError(Exception):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


@transaction.atomic
def transition_legal_case(
    case: LegalCase,
    *,
    to_status: str,
    changed_by=None,
    note: str = "",
) -> LegalCase:
    if to_status not in LegalCaseStatus.values:
        raise LegalWorkflowError("Geçersiz durum.", code="invalid_status")
    if case.status in LEGAL_TERMINAL_STATUSES and to_status != case.status:
        if case.status == LegalCaseStatus.COLLECTED and to_status == LegalCaseStatus.CLOSED:
            pass
        else:
            raise LegalWorkflowError("Kapalı dosyada durum değiştirilemez.", code="terminal")
    allowed = ALLOWED_TRANSITIONS.get(case.status, set())
    if to_status not in allowed:
        raise LegalWorkflowError(
            f"{case.status} → {to_status} geçişine izin verilmiyor.",
            code="transition_not_allowed",
        )
    from_status = case.status
    case.status = to_status
    updates = ["status", "updated_at"]
    if to_status in LEGAL_TERMINAL_STATUSES:
        case.closed_at = timezone.now()
        updates.append("closed_at")
    case.save(update_fields=updates)
    LegalCaseStatusHistory.objects.create(
        organization=case.organization,
        legal_case=case,
        from_status=from_status,
        to_status=to_status,
        note=note,
        changed_by=changed_by,
    )
    return case


def add_activity(
    case: LegalCase,
    *,
    summary: str,
    notes: str = "",
    created_by=None,
    is_lawyer_visible: bool = True,
) -> LegalCaseActivity:
    return LegalCaseActivity.objects.create(
        organization=case.organization,
        legal_case=case,
        summary=summary[:255],
        notes=notes,
        created_by=created_by,
        is_lawyer_visible=is_lawyer_visible,
    )


def store_legal_document(
    case: LegalCase,
    *,
    uploaded_file,
    uploaded_by=None,
    notes: str = "",
) -> LegalCaseDocument:
    size = getattr(uploaded_file, "size", 0) or 0
    if size > DOC_MAX_BYTES:
        raise LegalWorkflowError("Dosya boyutu 20MB sınırını aşıyor.", code="file_too_large")
    original = Path(getattr(uploaded_file, "name", "document.bin")).name
    ext = Path(original).suffix.lower() or ".bin"
    root = private_upload_root() / "org" / str(case.organization_id) / "legal" / str(case.id)
    root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = root / stored_name
    with dest.open("wb") as fh:
        for chunk in uploaded_file.chunks():
            fh.write(chunk)
    return LegalCaseDocument.objects.create(
        organization=case.organization,
        legal_case=case,
        original_filename=original,
        stored_path=str(dest),
        content_type=getattr(uploaded_file, "content_type", "") or "",
        file_size=size,
        notes=notes,
        uploaded_by=uploaded_by,
    )


def lawyer_safe_case_payload(case: LegalCase) -> dict[str, Any]:
    """NP-353 — limited fields for external lawyers (no full finance dump)."""
    return {
        "id": case.id,
        "title": case.title,
        "status": case.status,
        "customer_name": case.customer.name,
        "customer_code": case.customer.code,
        "opened_at": case.opened_at.isoformat() if case.opened_at else None,
        "notes": case.notes,
        "balance_at_open": str(case.balance_at_open),
        "invoice_count": case.case_invoices.count(),
        "disclaimer": (
            "Avukat portalı yalnızca atanan dosya özetine erişim sağlar; "
            "tam finans verilerine erişim yoktur."
        ),
    }
