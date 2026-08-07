"""NP-312 — account/organization deletion with waiting period."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.governance.models import DeletionRequest, DeletionRequestStatus
from apps.governance.retention import ensure_retention_policy

DEFAULT_WAIT_DAYS = 14


class DeletionError(Exception):
    def __init__(self, message: str, code: str = "deletion_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def request_deletion(
    organization,
    *,
    target_type: str,
    target_id: str,
    requested_by,
    reason: str = "",
) -> DeletionRequest:
    if target_type not in {"organization", "user"}:
        raise DeletionError("Geçersiz hedef tipi.", code="invalid_target")
    policy = ensure_retention_policy(organization)
    wait_days = max(DEFAULT_WAIT_DAYS, min(30, policy.deleted_user_data_days or DEFAULT_WAIT_DAYS))
    return DeletionRequest.objects.create(
        organization=organization,
        target_type=target_type,
        target_id=str(target_id),
        requested_by=requested_by,
        reason=reason,
        status=DeletionRequestStatus.WAITING,
        waiting_until=timezone.now() + timedelta(days=wait_days),
    )


def cancel_deletion(req: DeletionRequest) -> DeletionRequest:
    if req.status not in {DeletionRequestStatus.PENDING, DeletionRequestStatus.WAITING}:
        raise DeletionError("Bu talep iptal edilemez.", code="not_cancellable")
    req.status = DeletionRequestStatus.CANCELLED
    req.cancelled_at = timezone.now()
    req.save(update_fields=["status", "cancelled_at"])
    return req


def process_due_deletions() -> list[dict[str, Any]]:
    """Execute deletions whose waiting period elapsed (soft-delete)."""
    now = timezone.now()
    results = []
    qs = DeletionRequest.objects.filter(
        status=DeletionRequestStatus.WAITING,
        waiting_until__lte=now,
    )
    for req in qs:
        req.status = DeletionRequestStatus.PROCESSING
        req.save(update_fields=["status"])
        report: dict[str, Any] = {"target_type": req.target_type, "target_id": req.target_id}
        try:
            if req.target_type == "organization":
                from apps.organizations.models import Organization

                org = Organization.objects.filter(pk=req.target_id).first()
                if org:
                    org.is_active = False
                    org.name = f"[SİLİNDİ] {org.name}"[:255]
                    org.email = ""
                    org.phone = ""
                    org.tax_number = ""
                    org.save(
                        update_fields=["is_active", "name", "email", "phone", "tax_number", "updated_at"]
                    )
                    report["action"] = "organization_deactivated_anonymized"
            elif req.target_type == "user":
                from django.contrib.auth import get_user_model

                User = get_user_model()
                user = User.objects.filter(pk=req.target_id).first()
                if user:
                    user.is_active = False
                    user.email = f"deleted_{user.pk}@invalid.local"
                    if hasattr(user, "phone"):
                        user.phone = ""
                    user.save()
                    report["action"] = "user_deactivated_anonymized"
            req.status = DeletionRequestStatus.COMPLETED
            req.completed_at = timezone.now()
            req.completion_report = report
            req.save(update_fields=["status", "completed_at", "completion_report"])
            results.append(report)
        except Exception as exc:  # noqa: BLE001
            req.status = DeletionRequestStatus.WAITING
            req.completion_report = {"error": str(exc)}
            req.save(update_fields=["status", "completion_report"])
    return results
