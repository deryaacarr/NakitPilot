"""NP-160 — gecikmiş alacak raporu."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import RiskStatus
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_overdue_days

ZERO = Decimal("0.00")
QUANTIZE = Decimal("0.01")
OPEN = {InvoiceStatus.OPEN, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID}


def _money(value: Decimal) -> str:
    return str(Decimal(str(value)).quantize(QUANTIZE))


def _parse_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def overdue_receivables_report(
    organization,
    *,
    filters: dict[str, Any] | None = None,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """
    Filters (NP-160):
    - date_from / date_to — vade tarihi aralığı
    - customer — müşteri id
    - risk_status — müşteri risk seviyesi
    - assigned_user — sorumlu (fatura veya müşteri)
    - overdue_days_min / overdue_days_max — gecikme aralığı
    """
    today = as_of or timezone.localdate()
    f = filters or {}

    qs = (
        Invoice.objects.for_organization(organization)
        .filter(status__in=OPEN)
        .select_related("customer", "customer__assigned_user", "assigned_user")
        .prefetch_related(
            Prefetch(
                "customer__payment_promises",
                queryset=PaymentPromise.objects.filter(
                    status__in=[
                        PaymentPromiseStatus.PENDING,
                        PaymentPromiseStatus.PARTIALLY_FULFILLED,
                    ]
                ).order_by("promised_date", "id"),
                to_attr="open_promises",
            )
        )
        .order_by("due_date", "id")
    )

    date_from = _parse_date(str(f.get("date_from") or ""))
    date_to = _parse_date(str(f.get("date_to") or ""))
    if date_from:
        qs = qs.filter(due_date__gte=date_from)
    if date_to:
        qs = qs.filter(due_date__lte=date_to)

    customer_id = str(f.get("customer") or "").strip()
    if customer_id.isdigit():
        qs = qs.filter(customer_id=int(customer_id))

    risk = str(f.get("risk_status") or "").strip().upper()
    if risk and risk in RiskStatus.values:
        qs = qs.filter(customer__risk_status=risk)

    assignee = str(f.get("assigned_user") or "").strip()
    if assignee in {"null", "none", "0"}:
        qs = qs.filter(Q(assigned_user__isnull=True) & Q(customer__assigned_user__isnull=True))
    elif assignee.isdigit():
        uid = int(assignee)
        qs = qs.filter(Q(assigned_user_id=uid) | Q(customer__assigned_user_id=uid))

    overdue_min = str(f.get("overdue_days_min") or "").strip()
    overdue_max = str(f.get("overdue_days_max") or "").strip()
    if overdue_min.isdigit():
        qs = qs.filter(due_date__lte=today - timedelta(days=int(overdue_min)))
    if overdue_max.isdigit() and int(overdue_max) >= 0:
        qs = qs.filter(due_date__gte=today - timedelta(days=int(overdue_max)))

    rows: list[dict[str, Any]] = []
    min_days = int(overdue_min) if overdue_min.isdigit() else 1
    max_days = int(overdue_max) if overdue_max.isdigit() else None

    for inv in qs.iterator(chunk_size=200):
        remaining = inv.remaining_amount()
        if remaining <= ZERO:
            continue
        days = invoice_overdue_days(inv, as_of=today)
        if days < min_days:
            continue
        if max_days is not None and days > max_days:
            continue

        customer = inv.customer
        promises = getattr(customer, "open_promises", None)
        promise_label = ""
        if promises:
            p = promises[0]
            promise_label = f"{p.promised_date.isoformat()} / {_money(p.amount)} {p.currency}"

        last_contact = ""
        if customer.last_contact_at:
            last_contact = timezone.localtime(customer.last_contact_at).strftime("%Y-%m-%d %H:%M")

        rows.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "customer_code": customer.code,
                "invoice_id": inv.id,
                "invoice_number": inv.number,
                "open_balance": _money(remaining),
                "currency": inv.currency,
                "due_date": inv.due_date.isoformat(),
                "overdue_days": days,
                "risk_status": customer.risk_status,
                "risk_score": customer.risk_score,
                "last_contact_at": last_contact,
                "payment_promise": promise_label,
                "assigned_user_id": inv.assigned_user_id or customer.assigned_user_id,
            }
        )
    return rows
