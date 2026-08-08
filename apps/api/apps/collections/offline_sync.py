"""NP-342 — sync offline field drafts (notes / complete / promise) with conflicts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.collections.models import (
    CallOutcome,
    CollectionActivity,
    CollectionActivityType,
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.collections.promises import create_promise
from apps.collections.services import CollectionValidationError, complete_task
from apps.customers.models import Customer


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_day(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return parse_date(str(value))


def _conflict(
    *,
    client_id: str,
    reason: str,
    server: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "client_id": client_id,
        "status": "conflict",
        "reason": reason,
        "server": server or {},
    }


@transaction.atomic
def sync_offline_item(
    *,
    organization,
    user,
    item: dict[str, Any],
) -> dict[str, Any]:
    client_id = str(item.get("client_id") or "")
    kind = str(item.get("kind") or "").upper()
    payload = item.get("payload") or {}
    base_updated_at = _parse_ts(item.get("base_updated_at"))
    client_updated_at = _parse_ts(item.get("client_updated_at"))

    if not client_id or kind not in {"NOTE", "COMPLETE_TASK", "PROMISE_DRAFT"}:
        return _conflict(client_id=client_id or "unknown", reason="invalid_item")

    task_id = item.get("task_id")
    customer_id = item.get("customer_id") or payload.get("customer_id")
    task: CollectionTask | None = None
    if task_id:
        task = (
            CollectionTask.objects.select_related("customer")
            .filter(organization=organization, pk=task_id)
            .first()
        )
        if task is None:
            return _conflict(client_id=client_id, reason="task_not_found")
        if base_updated_at and task.updated_at and task.updated_at > base_updated_at:
            if kind == "COMPLETE_TASK" and task.status == CollectionTaskStatus.COMPLETED:
                return _conflict(
                    client_id=client_id,
                    reason="task_already_completed",
                    server={
                        "task_id": task.id,
                        "status": task.status,
                        "outcome": task.outcome,
                        "outcome_notes": task.outcome_notes,
                        "updated_at": task.updated_at.isoformat(),
                    },
                )
            if kind in {"NOTE", "COMPLETE_TASK"}:
                return _conflict(
                    client_id=client_id,
                    reason="task_updated_on_server",
                    server={
                        "task_id": task.id,
                        "status": task.status,
                        "updated_at": task.updated_at.isoformat(),
                        "outcome_notes": task.outcome_notes,
                    },
                )

    if kind == "NOTE":
        if task is None:
            return _conflict(client_id=client_id, reason="task_required")
        notes = str(payload.get("notes") or payload.get("outcome_notes") or "").strip()
        if not notes:
            return _conflict(client_id=client_id, reason="notes_required")
        activity = CollectionActivity.objects.create(
            organization=organization,
            customer=task.customer,
            task=task,
            activity_type=CollectionActivityType.NOTE,
            summary="Offline görüşme notu",
            notes=notes,
            created_by=user,
            metadata={
                "offline_client_id": client_id,
                "client_updated_at": client_updated_at.isoformat()
                if client_updated_at
                else None,
                "synced_at": timezone.now().isoformat(),
            },
        )
        return {
            "client_id": client_id,
            "status": "synced",
            "kind": kind,
            "activity_id": activity.id,
            "task_id": task.id,
        }

    if kind == "COMPLETE_TASK":
        if task is None:
            return _conflict(client_id=client_id, reason="task_required")
        if task.status == CollectionTaskStatus.COMPLETED:
            return _conflict(
                client_id=client_id,
                reason="task_already_completed",
                server={
                    "task_id": task.id,
                    "outcome": task.outcome,
                    "outcome_notes": task.outcome_notes,
                    "updated_at": task.updated_at.isoformat(),
                },
            )
        outcome = str(payload.get("outcome") or CallOutcome.REACHED).upper()
        notes = str(payload.get("outcome_notes") or payload.get("notes") or "").strip()
        try:
            result = complete_task(
                task,
                outcome=outcome,
                outcome_notes=notes or "Offline tamamlandı",
                actor=user,
                create_follow_up=bool(payload.get("create_follow_up")),
                promise_given=bool(payload.get("promise_given")),
                callback_date=_parse_day(payload.get("callback_date")),
                promise_amount=(
                    Decimal(str(payload["promise_amount"]))
                    if payload.get("promise_amount") not in (None, "")
                    else None
                ),
                promise_date=_parse_day(payload.get("promise_date")),
            )
        except (CollectionValidationError, InvalidOperation) as exc:
            message = getattr(exc, "message", None) or str(exc)
            return _conflict(client_id=client_id, reason=message)
        completed = result.get("task") if isinstance(result, dict) else task
        return {
            "client_id": client_id,
            "status": "synced",
            "kind": kind,
            "task_id": getattr(completed, "id", task.id),
        }

    # PROMISE_DRAFT
    if task is not None:
        customer = task.customer
    else:
        customer = Customer.objects.filter(
            organization=organization, pk=customer_id
        ).first()
    if customer is None:
        return _conflict(client_id=client_id, reason="customer_required")

    try:
        amount = Decimal(str(payload.get("amount") or "0"))
    except (InvalidOperation, TypeError):
        return _conflict(client_id=client_id, reason="invalid_amount")
    promised_date = _parse_day(payload.get("promised_date"))
    if promised_date is None:
        return _conflict(client_id=client_id, reason="promised_date_required")

    existing = (
        PaymentPromise.objects.filter(
            organization=organization,
            customer=customer,
            status=PaymentPromiseStatus.PENDING,
            promised_date=promised_date,
            amount=amount,
        )
        .order_by("-updated_at")
        .first()
    )
    if existing and base_updated_at and existing.updated_at > base_updated_at:
        return _conflict(
            client_id=client_id,
            reason="promise_already_exists",
            server={
                "promise_id": existing.id,
                "amount": str(existing.amount),
                "promised_date": existing.promised_date.isoformat(),
                "updated_at": existing.updated_at.isoformat(),
            },
        )

    notes = str(payload.get("notes") or "Offline taslak ödeme sözü")
    if client_id:
        notes = f"{notes}\n[offline:{client_id}]"
    promise, _warnings = create_promise(
        organization=organization,
        customer=customer,
        promised_date=promised_date,
        amount=amount,
        notes=notes,
        created_by=user,
    )
    return {
        "client_id": client_id,
        "status": "synced",
        "kind": kind,
        "promise_id": promise.id,
        "customer_id": customer.id,
    }


def sync_offline_batch(*, organization, user, items: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    conflicts = []
    for item in items:
        try:
            row = sync_offline_item(organization=organization, user=user, item=item)
        except Exception as exc:  # noqa: BLE001
            row = _conflict(
                client_id=str(item.get("client_id") or "unknown"),
                reason=f"sync_error: {exc}",
            )
        results.append(row)
        if row.get("status") == "conflict":
            conflicts.append(row)
    return {
        "synced": [r for r in results if r.get("status") == "synced"],
        "conflicts": conflicts,
        "results": results,
    }
