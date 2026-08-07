"""NP-251 — dispute status transitions + NP-253 attachments."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.collections.models import (
    DISPUTE_ACTIVE_STATUSES,
    DISPUTE_TERMINAL_STATUSES,
    Dispute,
    DisputeAttachment,
    DisputeAttachmentKind,
    DisputeStatus,
    DisputeStatusEvent,
)
from apps.imports.services_io import private_upload_root

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    DisputeStatus.OPEN: {
        DisputeStatus.UNDER_REVIEW,
        DisputeStatus.WAITING_CUSTOMER,
        DisputeStatus.WAITING_INTERNAL,
        DisputeStatus.RESOLVED,
        DisputeStatus.REJECTED,
        DisputeStatus.CANCELLED,
    },
    DisputeStatus.UNDER_REVIEW: {
        DisputeStatus.WAITING_CUSTOMER,
        DisputeStatus.WAITING_INTERNAL,
        DisputeStatus.RESOLVED,
        DisputeStatus.REJECTED,
        DisputeStatus.CANCELLED,
        DisputeStatus.OPEN,
    },
    DisputeStatus.WAITING_CUSTOMER: {
        DisputeStatus.UNDER_REVIEW,
        DisputeStatus.WAITING_INTERNAL,
        DisputeStatus.RESOLVED,
        DisputeStatus.REJECTED,
        DisputeStatus.CANCELLED,
    },
    DisputeStatus.WAITING_INTERNAL: {
        DisputeStatus.UNDER_REVIEW,
        DisputeStatus.WAITING_CUSTOMER,
        DisputeStatus.RESOLVED,
        DisputeStatus.REJECTED,
        DisputeStatus.CANCELLED,
    },
    DisputeStatus.RESOLVED: set(),
    DisputeStatus.REJECTED: set(),
    DisputeStatus.CANCELLED: set(),
}

ATTACHMENT_MAX_BYTES = 15 * 1024 * 1024
KIND_EXTENSIONS = {
    DisputeAttachmentKind.PDF: {".pdf"},
    DisputeAttachmentKind.IMAGE: {".png", ".jpg", ".jpeg", ".gif", ".webp"},
    DisputeAttachmentKind.DELIVERY_DOC: {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"},
    DisputeAttachmentKind.EMAIL: {".eml", ".msg", ".pdf", ".txt"},
    DisputeAttachmentKind.CONTRACT: {".pdf", ".doc", ".docx"},
}


class DisputeWorkflowError(Exception):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


@transaction.atomic
def transition_dispute(
    dispute: Dispute,
    *,
    to_status: str,
    actor=None,
    note: str = "",
    resolution_note: str = "",
) -> Dispute:
    to_status = (to_status or "").strip().upper()
    if to_status not in DisputeStatus.values:
        raise DisputeWorkflowError("Geçersiz durum.", "invalid_status")
    allowed = ALLOWED_TRANSITIONS.get(dispute.status, set())
    if to_status == dispute.status:
        return dispute
    if to_status not in allowed:
        raise DisputeWorkflowError(
            f"{dispute.status} → {to_status} geçişine izin verilmiyor.",
            "invalid_transition",
        )
    from_status = dispute.status
    dispute.status = to_status
    if to_status in DISPUTE_TERMINAL_STATUSES:
        dispute.resolved_at = timezone.now()
        if resolution_note:
            dispute.resolution_note = resolution_note
        elif note and not dispute.resolution_note:
            dispute.resolution_note = note
    elif to_status in DISPUTE_ACTIVE_STATUSES:
        dispute.resolved_at = None
    dispute.save()
    DisputeStatusEvent.objects.create(
        organization_id=dispute.organization_id,
        dispute=dispute,
        from_status=from_status,
        to_status=to_status,
        note=note or "",
        changed_by=actor,
    )
    return dispute


def store_dispute_file(*, organization_id: int, filename: str, content: bytes) -> str:
    ext = Path(filename or "file.bin").suffix.lower() or ".bin"
    root = private_upload_root() / "org" / str(organization_id) / "disputes"
    root.mkdir(parents=True, exist_ok=True)
    path = (root / f"{uuid.uuid4().hex}{ext}").resolve()
    if not str(path).startswith(str(root.resolve())):
        raise DisputeWorkflowError("Geçersiz depolama yolu.", "invalid_file")
    path.write_bytes(content)
    return str(path)


def add_dispute_attachment(
    dispute: Dispute,
    *,
    kind: str,
    filename: str,
    content: bytes,
    actor=None,
    notes: str = "",
    content_type: str = "",
) -> DisputeAttachment:
    kind = (kind or DisputeAttachmentKind.PDF).strip().upper()
    if kind not in DisputeAttachmentKind.values:
        raise DisputeWorkflowError("Geçersiz ek türü.", "invalid_kind")
    if len(content) > ATTACHMENT_MAX_BYTES:
        raise DisputeWorkflowError("Dosya 15 MB sınırını aşıyor.", "file_too_large")
    if not content:
        raise DisputeWorkflowError("Boş dosya yüklenemez.", "empty_file")
    ext = Path(filename or "").suffix.lower()
    allowed = KIND_EXTENSIONS.get(kind, set())
    if allowed and ext and ext not in allowed:
        raise DisputeWorkflowError(
            f"{kind} için izin verilen uzantılar: {', '.join(sorted(allowed))}",
            "invalid_extension",
        )
    stored = store_dispute_file(
        organization_id=dispute.organization_id,
        filename=filename,
        content=content,
    )
    mime = content_type or mimetypes.guess_type(filename)[0] or ""
    return DisputeAttachment.objects.create(
        organization_id=dispute.organization_id,
        dispute=dispute,
        kind=kind,
        original_filename=filename[:255],
        stored_path=stored,
        content_type=mime[:128],
        file_size=len(content),
        notes=(notes or "")[:255],
        uploaded_by=actor,
    )


def serialize_attachment(att: DisputeAttachment) -> dict[str, Any]:
    return {
        "id": att.id,
        "dispute_id": att.dispute_id,
        "kind": att.kind,
        "kind_label": DisputeAttachmentKind(att.kind).label,
        "original_filename": att.original_filename,
        "content_type": att.content_type,
        "file_size": att.file_size,
        "notes": att.notes,
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }
