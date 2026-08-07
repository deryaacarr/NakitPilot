"""Notification generators (NP-140/142)."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.utils import timezone

from apps.collections.models import (
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.models import Customer, RiskStatus
from apps.notifications.models import (
    AlertSeverity,
    NotificationType,
    create_dashboard_alert,
)

OPEN_TASK = {CollectionTaskStatus.OPEN, CollectionTaskStatus.IN_PROGRESS}


def _already_notified_today(
    *,
    organization_id: int,
    notification_type: str,
    entity_type: str,
    entity_id: str | int,
    as_of: date,
) -> bool:
    from apps.notifications.models import DashboardAlert

    return DashboardAlert.objects.filter(
        organization_id=organization_id,
        notification_type=notification_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        created_at__date=as_of,
    ).exists()


def generate_daily_task_promise_reminders(
    organization,
    *,
    as_of: date | None = None,
) -> dict[str, int]:
    """08:00 job: TASK_DUE, TASK_OVERDUE, PROMISE_DUE."""
    today = as_of or timezone.localdate()
    created = {"task_due": 0, "task_overdue": 0, "promise_due": 0}

    due_tasks = CollectionTask.objects.filter(
        organization=organization,
        status__in=OPEN_TASK,
        due_date=today,
    ).select_related("customer", "assigned_to")
    for task in due_tasks:
        if _already_notified_today(
            organization_id=organization.id,
            notification_type=NotificationType.TASK_DUE,
            entity_type="CollectionTask",
            entity_id=task.id,
            as_of=today,
        ):
            continue
        create_dashboard_alert(
            organization=organization,
            title=f"Bugün yapılacak görev: {task.title}",
            body=f"{task.customer.name} — vade {task.due_date}",
            severity=AlertSeverity.INFO,
            notification_type=NotificationType.TASK_DUE,
            entity_type="CollectionTask",
            entity_id=task.id,
            created_for=task.assigned_to,
        )
        created["task_due"] += 1

    overdue_tasks = CollectionTask.objects.filter(
        organization=organization,
        status__in=OPEN_TASK,
        due_date__lt=today,
    ).select_related("customer", "assigned_to")
    for task in overdue_tasks:
        if _already_notified_today(
            organization_id=organization.id,
            notification_type=NotificationType.TASK_OVERDUE,
            entity_type="CollectionTask",
            entity_id=task.id,
            as_of=today,
        ):
            continue
        create_dashboard_alert(
            organization=organization,
            title=f"Gecikmiş görev: {task.title}",
            body=f"{task.customer.name} — vade {task.due_date}",
            severity=AlertSeverity.WARNING,
            notification_type=NotificationType.TASK_OVERDUE,
            entity_type="CollectionTask",
            entity_id=task.id,
            created_for=task.assigned_to,
        )
        created["task_overdue"] += 1

    promises = PaymentPromise.objects.filter(
        organization=organization,
        status=PaymentPromiseStatus.PENDING,
        promised_date=today,
    ).select_related("customer", "customer__assigned_user")
    for promise in promises:
        if _already_notified_today(
            organization_id=organization.id,
            notification_type=NotificationType.PROMISE_DUE,
            entity_type="PaymentPromise",
            entity_id=promise.id,
            as_of=today,
        ):
            continue
        create_dashboard_alert(
            organization=organization,
            title=f"Bugün vadesi gelen ödeme sözü: {promise.customer.name}",
            body=f"{promise.amount} {promise.currency} — {promise.promised_date}",
            severity=AlertSeverity.INFO,
            notification_type=NotificationType.PROMISE_DUE,
            entity_type="PaymentPromise",
            entity_id=promise.id,
            created_for=promise.customer.assigned_user,
        )
        created["promise_due"] += 1

    return created


def notify_high_risk_customers(
    organization,
    *,
    as_of: date | None = None,
) -> int:
    """After risk calc: alert for CRITICAL customers (once per day)."""
    today = as_of or timezone.localdate()
    count = 0
    qs = Customer.objects.filter(
        organization=organization,
        is_active=True,
        risk_status=RiskStatus.CRITICAL,
    )
    for customer in qs:
        if _already_notified_today(
            organization_id=organization.id,
            notification_type=NotificationType.HIGH_RISK_CUSTOMER,
            entity_type="Customer",
            entity_id=customer.id,
            as_of=today,
        ):
            continue
        create_dashboard_alert(
            organization=organization,
            title=f"Kritik risk: {customer.name}",
            body=f"Risk skoru {customer.risk_score}",
            severity=AlertSeverity.CRITICAL,
            notification_type=NotificationType.HIGH_RISK_CUSTOMER,
            entity_type="Customer",
            entity_id=customer.id,
            created_for=customer.assigned_user,
        )
        count += 1
    return count


def notify_import_result(job, *, success: bool) -> Any:
    ntype = (
        NotificationType.IMPORT_COMPLETED if success else NotificationType.IMPORT_FAILED
    )
    severity = AlertSeverity.INFO if success else AlertSeverity.WARNING
    title = (
        f"İçe aktarma tamamlandı (#{job.id})"
        if success
        else f"İçe aktarma başarısız (#{job.id})"
    )
    body = ""
    if success and getattr(job, "result_summary", None):
        body = str(job.result_summary)
    elif not success:
        body = job.error_message or "Bilinmeyen hata"
    return create_dashboard_alert(
        organization=job.organization,
        title=title,
        body=body[:2000],
        severity=severity,
        notification_type=ntype,
        entity_type="ImportJob",
        entity_id=job.id,
        created_for=getattr(job, "uploaded_by", None) or getattr(job, "created_by", None),
    )
