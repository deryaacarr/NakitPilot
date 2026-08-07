"""NP-310 — retention policy defaults + purge helpers."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.governance.models import RetentionPolicy


DEFAULTS = {
    "activity_logs_days": 365 * 5,
    "audit_logs_days": 365 * 10,
    "import_files_days": 90,
    "failed_webhook_bodies_days": 30,
    "ai_requests_days": 30,
    "deleted_user_data_days": 30,
}


def ensure_retention_policy(organization) -> RetentionPolicy:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    policy, _ = RetentionPolicy.objects.get_or_create(
        organization_id=org_id,
        defaults=DEFAULTS,
    )
    return policy


def policy_as_dict(policy: RetentionPolicy) -> dict[str, Any]:
    return {
        "activity_logs_days": policy.activity_logs_days,
        "audit_logs_days": policy.audit_logs_days,
        "import_files_days": policy.import_files_days,
        "failed_webhook_bodies_days": policy.failed_webhook_bodies_days,
        "ai_requests_days": policy.ai_requests_days,
        "deleted_user_data_days": policy.deleted_user_data_days,
        "labels": {
            "activity_logs_days": "Aktivite kayıtları",
            "audit_logs_days": "Audit log",
            "import_files_days": "Import dosyaları",
            "failed_webhook_bodies_days": "Başarısız webhook gövdeleri",
            "ai_requests_days": "AI talepleri",
            "deleted_user_data_days": "Silinen kullanıcı verisi",
        },
    }


def apply_retention_purge(organization) -> dict[str, int]:
    """Delete expired rows according to policy (best-effort)."""
    policy = ensure_retention_policy(organization)
    org_id = organization.pk if hasattr(organization, "pk") else organization
    now = timezone.now()
    deleted: dict[str, int] = {}

    try:
        from apps.audit.models import AuditLog

        cutoff = now - timedelta(days=policy.audit_logs_days)
        deleted["audit_logs"] = AuditLog.objects.filter(
            organization_id=org_id, created_at__lt=cutoff
        ).delete()[0]
    except Exception:  # noqa: BLE001
        deleted["audit_logs"] = 0

    try:
        from apps.ai_usage.models import AIUsageEvent

        cutoff = now - timedelta(days=policy.ai_requests_days)
        deleted["ai_requests"] = AIUsageEvent.objects.filter(
            organization_id=org_id, created_at__lt=cutoff
        ).delete()[0]
    except Exception:  # noqa: BLE001
        deleted["ai_requests"] = 0

    try:
        from apps.webhooks.models import WebhookDelivery

        cutoff = now - timedelta(days=policy.failed_webhook_bodies_days)
        qs = WebhookDelivery.objects.filter(
            organization_id=org_id, created_at__lt=cutoff
        )
        # Clear bodies on failed deliveries if field exists
        count = 0
        for row in qs.iterator():
            changed = False
            for field in ("response_body", "request_body", "payload", "body"):
                if hasattr(row, field) and getattr(row, field):
                    setattr(row, field, "")
                    changed = True
            if changed:
                row.save()
                count += 1
        deleted["failed_webhook_bodies"] = count
    except Exception:  # noqa: BLE001
        deleted["failed_webhook_bodies"] = 0

    return deleted
