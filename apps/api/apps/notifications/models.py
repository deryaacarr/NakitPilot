"""In-app notifications (NP-140–142)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.organizations.tenancy import TenantModel


class AlertSeverity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Critical"


class NotificationType(models.TextChoices):
    """NP-140 typed in-app notifications (+ NP-344 field push types)."""

    TASK_DUE = "TASK_DUE", "Görev vadesi"
    TASK_OVERDUE = "TASK_OVERDUE", "Gecikmiş görev"
    TASK_ASSIGNED = "TASK_ASSIGNED", "Atanan görev"
    PROMISE_DUE = "PROMISE_DUE", "Ödeme sözü vadesi"
    PROMISE_BROKEN = "PROMISE_BROKEN", "Bozulan ödeme sözü"
    HIGH_RISK_CUSTOMER = "HIGH_RISK_CUSTOMER", "Yüksek riskli müşteri"
    CRITICAL_CUSTOMER = "CRITICAL_CUSTOMER", "Kritik müşteri"
    IMPORT_COMPLETED = "IMPORT_COMPLETED", "İçe aktarma tamamlandı"
    IMPORT_FAILED = "IMPORT_FAILED", "İçe aktarma başarısız"
    CASH_GAP = "CASH_GAP", "Nakit açığı"


# Deep-link helpers for the web app
NOTIFICATION_HREF = {
    NotificationType.TASK_DUE: "/collections/field",
    NotificationType.TASK_OVERDUE: "/collections/field",
    NotificationType.TASK_ASSIGNED: "/collections/field",
    NotificationType.PROMISE_DUE: "/promises",
    NotificationType.PROMISE_BROKEN: "/promises",
    NotificationType.HIGH_RISK_CUSTOMER: "/customers/{id}",
    NotificationType.CRITICAL_CUSTOMER: "/customers/{id}",
    NotificationType.IMPORT_COMPLETED: "/imports",
    NotificationType.IMPORT_FAILED: "/imports",
    NotificationType.CASH_GAP: "/forecast",
}


class DashboardAlert(TenantModel):
    """In-app notification (NP-140)."""

    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    severity = models.CharField(
        max_length=16,
        choices=AlertSeverity.choices,
        default=AlertSeverity.WARNING,
    )
    notification_type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
        blank=True,
        db_index=True,
    )
    category = models.CharField(max_length=64, blank=True, db_index=True)
    entity_type = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    href = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_for = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_alerts",
        help_text="Optional target user; null = org-wide.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "dashboard alert"
        verbose_name_plural = "dashboard alerts"

    def __str__(self) -> str:
        return self.title


def resolve_notification_href(
    notification_type: str,
    *,
    entity_type: str = "",
    entity_id: str | int = "",
) -> str:
    template = NOTIFICATION_HREF.get(notification_type, "")
    if not template:
        return ""
    if "{id}" in template and entity_id != "":
        return template.format(id=entity_id)
    if notification_type in {
        NotificationType.TASK_DUE,
        NotificationType.TASK_OVERDUE,
        NotificationType.TASK_ASSIGNED,
    } and entity_id != "":
        return f"/collections/field?task={entity_id}"
    if notification_type in {
        NotificationType.PROMISE_DUE,
        NotificationType.PROMISE_BROKEN,
    } and entity_id != "":
        return f"/promises?promise={entity_id}"
    return template.replace("/{id}", "").replace("{id}", "")


def create_dashboard_alert(
    *,
    organization,
    title: str,
    body: str = "",
    severity: str = AlertSeverity.WARNING,
    notification_type: str = "",
    category: str = "",
    entity_type: str = "",
    entity_id: str | int = "",
    created_for=None,
    href: str = "",
) -> DashboardAlert:
    ntype = notification_type or category.upper().replace("-", "_")
    # Map legacy broken_promise → PROMISE_BROKEN
    if ntype == "BROKEN_PROMISE" or category == "broken_promise":
        ntype = NotificationType.PROMISE_BROKEN
    if ntype and ntype not in NotificationType.values:
        ntype = notification_type or ""
    cat = category or (ntype.lower() if ntype else "")
    link = href or resolve_notification_href(
        ntype, entity_type=entity_type, entity_id=entity_id
    )
    alert = DashboardAlert.objects.create(
        organization=organization,
        title=title[:255],
        body=body,
        severity=severity,
        notification_type=ntype,
        category=cat,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id != "" else "",
        href=link[:255],
        created_for=created_for,
    )
    # NP-344 — mirror critical field alerts to web push when subscribed
    if ntype in {
        NotificationType.TASK_DUE,
        NotificationType.TASK_OVERDUE,
        NotificationType.TASK_ASSIGNED,
        NotificationType.PROMISE_BROKEN,
        NotificationType.HIGH_RISK_CUSTOMER,
        NotificationType.CRITICAL_CUSTOMER,
    }:
        try:
            from apps.notifications.push import enqueue_web_push

            enqueue_web_push(
                organization=organization,
                user=created_for,
                title=alert.title,
                body=alert.body,
                href=alert.href,
                tag=ntype or "nakitpilot",
                data={
                    "notification_type": ntype,
                    "entity_type": entity_type,
                    "entity_id": str(entity_id) if entity_id != "" else "",
                },
            )
        except Exception:  # noqa: BLE001 — never fail alert creation on push
            pass
    return alert


class PushSubscription(TenantModel):
    """NP-344 — Web Push subscription endpoint."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=2048)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "push subscription"
        verbose_name_plural = "push subscriptions"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "endpoint"),
                name="notifications_push_endpoint_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"PushSubscription<{self.user_id}>"
