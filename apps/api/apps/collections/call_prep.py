"""NP-231 — call preparation brief (DB-sourced only)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.collections.models import (
    CallOutcome,
    CollectionActivity,
    CollectionActivityType,
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.metrics import OPEN_STATUSES, customer_financial_metrics
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_overdue_days
from apps.payments.models import ZERO

_MONTHS_TR = (
    "",
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)


def _fmt_money(amount: Decimal) -> str:
    q = Decimal(str(amount)).quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    q = abs(q)
    whole, frac = f"{q:.2f}".split(".")
    groups: list[str] = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    whole_fmt = ".".join(reversed(groups))
    if frac == "00":
        return f"{sign}{whole_fmt} TL"
    return f"{sign}{whole_fmt},{frac} TL"


def _fmt_date(value: date | None) -> str:
    if value is None:
        return ""
    return f"{value.day} {_MONTHS_TR[value.month]} {value.year}"


def _source(**kwargs) -> dict[str, Any]:
    return kwargs


def _suggested_payment_plan(
    open_balance: Decimal,
    *,
    as_of: date,
) -> dict[str, Any] | None:
    """Heuristic installment suggestion from open balance (DB amount only)."""
    if open_balance <= ZERO:
        return None
    # Two installments: ~half now(+7d), remainder month-end
    first = (open_balance / 2).quantize(Decimal("0.01"))
    second = (open_balance - first).quantize(Decimal("0.01"))
    # last calendar day of month
    if as_of.month == 12:
        month_end = date(as_of.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(as_of.year, as_of.month + 1, 1) - timedelta(days=1)
    first_date = as_of + timedelta(days=7)
    if first_date > month_end:
        first_date = as_of + timedelta(days=3)
    return {
        "label": (
            f"{_fmt_money(first)} ({_fmt_date(first_date)}) + "
            f"{_fmt_money(second)} ({_fmt_date(month_end)})"
        ),
        "installments": [
            {"amount": str(first), "due_date": first_date.isoformat()},
            {"amount": str(second), "due_date": month_end.isoformat()},
        ],
        "basis_open_balance": str(open_balance),
    }


def build_call_preparation(
    customer: Customer,
    *,
    organization=None,
    task: CollectionTask | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    NP-231 prep brief for a call.

    All numbers and dates come from the database; talking points are derived
    from those records (no invented figures).
    """
    org = organization or customer.organization
    if customer.organization_id != org.id:
        raise PermissionError("Customer is outside the request organization.")
    if task is not None and task.customer_id != customer.id:
        raise PermissionError("Task does not belong to this customer.")

    today = as_of or timezone.localdate()
    metrics = customer_financial_metrics(customer)
    open_balance = Decimal(str(metrics["open_balance"] or ZERO))
    sources: list[dict[str, Any]] = []
    talking_points: list[str] = []

    # --- Open invoices ---
    open_invoices_qs = (
        Invoice.objects.filter(customer=customer, organization=org)
        .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED, InvoiceStatus.PAID])
        .order_by("due_date", "id")
    )
    open_invoices: list[dict[str, Any]] = []
    for inv in open_invoices_qs:
        remaining = inv.remaining_amount()
        if remaining <= ZERO or inv.status not in OPEN_STATUSES:
            continue
        days = invoice_overdue_days(inv, as_of=today)
        row = {
            "id": inv.id,
            "number": inv.number,
            "due_date": inv.due_date.isoformat(),
            "remaining_amount": str(remaining),
            "overdue_days": days,
            "status": inv.status,
        }
        open_invoices.append(row)
        sources.append(
            _source(
                type="invoice",
                id=inv.id,
                label=f"Fatura {inv.number}",
                field="remaining_amount",
                value=str(remaining),
                url_hint=f"/invoices/{inv.id}",
            )
        )
        if days > 0:
            talking_points.append(
                f"Fatura {inv.number}: {_fmt_money(remaining)} · {days} gün gecikme"
            )
        else:
            talking_points.append(
                f"Fatura {inv.number}: {_fmt_money(remaining)} · vade {_fmt_date(inv.due_date)}"
            )

    if open_balance > ZERO:
        talking_points.insert(
            0,
            f"Toplam açık bakiye {_fmt_money(open_balance)}",
        )
        sources.insert(
            0,
            _source(
                type="customer",
                id=customer.id,
                label=customer.name,
                field="open_balance",
                value=str(open_balance),
                url_hint=f"/customers/{customer.id}",
            ),
        )

    # --- Last payment promise ---
    last_promise = (
        PaymentPromise.objects.filter(customer=customer, organization=org)
        .exclude(status=PaymentPromiseStatus.CANCELLED)
        .order_by("-promised_date", "-id")
        .first()
    )
    last_promise_payload = None
    if last_promise is not None:
        last_promise_payload = {
            "id": last_promise.id,
            "amount": str(last_promise.amount),
            "promised_date": last_promise.promised_date.isoformat(),
            "status": last_promise.status,
            "notes": last_promise.notes or "",
        }
        sources.append(
            _source(
                type="payment_promise",
                id=last_promise.id,
                label=f"Ödeme sözü #{last_promise.id}",
                field="promised_date",
                value=last_promise.promised_date.isoformat(),
                url_hint="/promises",
            )
        )
        status_label = dict(PaymentPromiseStatus.choices).get(
            last_promise.status, last_promise.status
        )
        talking_points.append(
            f"Son ödeme sözü: {_fmt_money(last_promise.amount)} · "
            f"{_fmt_date(last_promise.promised_date)} ({status_label})"
        )

    # --- Last objection (DISPUTED outcome) ---
    last_objection_task = (
        CollectionTask.objects.filter(
            customer=customer,
            organization=org,
            status=CollectionTaskStatus.COMPLETED,
            outcome=CallOutcome.DISPUTED,
        )
        .order_by("-completed_at", "-id")
        .first()
    )
    last_objection = None
    if last_objection_task is not None:
        last_objection = {
            "task_id": last_objection_task.id,
            "outcome": last_objection_task.outcome,
            "notes": last_objection_task.outcome_notes or "",
            "completed_at": last_objection_task.completed_at.isoformat()
            if last_objection_task.completed_at
            else None,
        }
        talking_points.append(
            f"Son itiraz: {(last_objection_task.outcome_notes or '').strip() or 'Not yok'}"
        )
        sources.append(
            _source(
                type="collection_task",
                id=last_objection_task.id,
                label=f"Görev #{last_objection_task.id}",
                field="outcome_notes",
                value=last_objection_task.outcome_notes or "",
                url_hint="/collections",
            )
        )

    # --- Previous call notes ---
    prev_calls = list(
        CollectionActivity.objects.filter(
            customer=customer,
            organization=org,
            activity_type__in=[
                CollectionActivityType.CALL,
                CollectionActivityType.TASK_COMPLETED,
                CollectionActivityType.NOTE,
            ],
        )
        .order_by("-occurred_at", "-id")[:5]
    )
    previous_notes = []
    for act in prev_calls:
        previous_notes.append(
            {
                "id": act.id,
                "summary": act.summary,
                "notes": act.notes or "",
                "occurred_at": act.occurred_at.isoformat(),
                "activity_type": act.activity_type,
            }
        )
        sources.append(
            _source(
                type="collection_activity",
                id=act.id,
                label=act.summary or f"Aktivite #{act.id}",
                field="notes",
                value=act.notes or "",
                url_hint="/collections",
            )
        )
    if previous_notes:
        latest = previous_notes[0]
        snippet = (latest["notes"] or latest["summary"] or "").strip()
        if snippet:
            talking_points.append(f"Önceki görüşme: {snippet[:160]}")

    plan = _suggested_payment_plan(open_balance, as_of=today)
    from apps.collections.payment_plans import suggest_payment_plans

    plan_bundle = suggest_payment_plans(
        customer, organization=org, as_of=today
    )
    options = plan_bundle.get("options") or []
    if options:
        talking_points.append(
            f"Ödeme planı önerileri (onay gerekir): {options[0]['summary']}"
        )
    elif plan is not None:
        talking_points.append(f"Önerilen ödeme planı: {plan['label']}")

    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "task_id": task.id if task else None,
        "as_of": today.isoformat(),
        "talking_points": talking_points,
        "open_invoices": open_invoices,
        "last_payment_promise": last_promise_payload,
        "last_objection": last_objection,
        "previous_call_notes": previous_notes,
        "suggested_payment_plan": plan,
        "payment_plan_suggestions": plan_bundle,
        "open_balance": str(open_balance),
        "sources": sources,
    }
