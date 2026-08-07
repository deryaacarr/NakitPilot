"""NP-303 — approval workflow service."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.governance.models import ApprovalRequest, ApprovalStatus


class ApprovalError(Exception):
    def __init__(self, message: str, code: str = "approval_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def request_approval(
    organization,
    *,
    action_type: str,
    requested_by,
    payload: dict[str, Any] | None = None,
    reason: str = "",
) -> ApprovalRequest:
    return ApprovalRequest.objects.create(
        organization=organization,
        action_type=action_type,
        requested_by=requested_by,
        payload=payload or {},
        reason=reason,
        status=ApprovalStatus.PENDING,
    )


def decide_approval(
    approval: ApprovalRequest,
    *,
    decided_by,
    approve: bool,
    note: str = "",
) -> ApprovalRequest:
    if approval.status != ApprovalStatus.PENDING:
        raise ApprovalError("Onay zaten karara bağlanmış.", code="already_decided")
    if decided_by and approval.requested_by_id and decided_by.pk == approval.requested_by_id:
        raise ApprovalError("Talep eden kişi kendi talebini onaylayamaz.", code="self_approve")
    approval.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
    approval.decided_by = decided_by
    approval.decision_note = note
    approval.decided_at = timezone.now()
    approval.save(
        update_fields=["status", "decided_by", "decision_note", "decided_at"]
    )
    return approval


def requires_approval(action_type: str, *, amount: float | None = None) -> bool:
    """Heuristic: high-value cancel / large plan need approval."""
    from apps.governance.models import ApprovalActionType

    if action_type in {
        ApprovalActionType.BULK_MESSAGE,
        ApprovalActionType.LEGAL_HANDOFF,
        ApprovalActionType.CREDIT_LIMIT_CHANGE,
        ApprovalActionType.MANUAL_RISK_CHANGE,
    }:
        return True
    if action_type == ApprovalActionType.HIGH_VALUE_PAYMENT_CANCEL:
        return (amount or 0) >= 10_000
    if action_type == ApprovalActionType.LARGE_PAYMENT_PLAN:
        return (amount or 0) >= 50_000
    return False
