"""NP-460/461/462 — notification groups, actions, customer resolution."""

from __future__ import annotations

from typing import Any

from apps.notifications.models import AlertSeverity, NotificationType

ACTION_TYPES = {
    NotificationType.TASK_DUE,
    NotificationType.TASK_OVERDUE,
    NotificationType.TASK_ASSIGNED,
    NotificationType.PROMISE_DUE,
    NotificationType.PROMISE_BROKEN,
    NotificationType.HIGH_RISK_CUSTOMER,
    NotificationType.CRITICAL_CUSTOMER,
}

SYSTEM_TYPES = {
    NotificationType.IMPORT_COMPLETED,
    NotificationType.IMPORT_FAILED,
    NotificationType.CASH_GAP,
}


def importance_group(*, severity: str, notification_type: str) -> str:
    """critical | action | info | system"""
    if severity == AlertSeverity.CRITICAL or notification_type in {
        NotificationType.PROMISE_BROKEN,
        NotificationType.CRITICAL_CUSTOMER,
    }:
        return "critical"
    if notification_type in SYSTEM_TYPES:
        return "system"
    if notification_type in ACTION_TYPES or severity == AlertSeverity.WARNING:
        return "action"
    return "info"


def resolve_customer_ref(
    *,
    entity_type: str,
    entity_id: str,
) -> tuple[int | None, str | None]:
    if not entity_id:
        return None, None
    try:
        eid = int(entity_id)
    except (TypeError, ValueError):
        return None, None

    if entity_type == "Customer":
        from apps.customers.models import Customer

        name = (
            Customer.objects.filter(pk=eid).values_list("name", flat=True).first()
        )
        return eid, name

    if entity_type == "PaymentPromise":
        from apps.collections.models import PaymentPromise

        row = (
            PaymentPromise.objects.filter(pk=eid)
            .values_list("customer_id", "customer__name")
            .first()
        )
        if row:
            return int(row[0]), row[1]
        return None, None

    if entity_type == "CollectionTask":
        from apps.collections.models import CollectionTask

        row = (
            CollectionTask.objects.filter(pk=eid)
            .values_list("customer_id", "customer__name")
            .first()
        )
        if row:
            return int(row[0]), row[1]
        return None, None

    return None, None


def build_actions(
    *,
    notification_type: str,
    customer_id: int | None,
    href: str,
    entity_type: str,
    entity_id: str,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if customer_id:
        if notification_type in {
            NotificationType.PROMISE_BROKEN,
            NotificationType.PROMISE_DUE,
            NotificationType.TASK_OVERDUE,
            NotificationType.TASK_DUE,
            NotificationType.HIGH_RISK_CUSTOMER,
            NotificationType.CRITICAL_CUSTOMER,
        }:
            actions.append(
                {
                    "label": "Görev Oluştur",
                    "href": f"/collections/tasks?create=1&customer={customer_id}",
                }
            )
        actions.append(
            {
                "label": "Müşteriyi Aç",
                "href": f"/customers/{customer_id}",
            }
        )
    if href and not any(a["href"] == href for a in actions):
        actions.append({"label": "Kayda git", "href": href})
    elif not actions and href:
        actions.append({"label": "Kayda git", "href": href})
    return actions


def enrich_alert(alert) -> dict[str, Any]:
    customer_id, customer_name = resolve_customer_ref(
        entity_type=alert.entity_type,
        entity_id=alert.entity_id,
    )
    group = importance_group(
        severity=alert.severity,
        notification_type=alert.notification_type,
    )
    actions = build_actions(
        notification_type=alert.notification_type,
        customer_id=customer_id,
        href=alert.href,
        entity_type=alert.entity_type,
        entity_id=alert.entity_id,
    )
    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "importance_group": group,
        "actions": actions,
    }
