"""NP-162 — müşteri risk raporu."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Count, Max

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer, RiskStatus
from apps.payments.models import Payment
from apps.risk.models import RiskSnapshot

QUANTIZE = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value: Decimal) -> str:
    return str(Decimal(str(value or ZERO)).quantize(QUANTIZE))


def customer_risk_report(
    organization,
    *,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Filters: risk_status, assigned_user, is_active (default true).
    """
    f = filters or {}
    qs = Customer.objects.for_organization(organization).select_related("assigned_user")

    is_active = str(f.get("is_active") or "true").strip().lower()
    if is_active in {"true", "1", "yes"}:
        qs = qs.filter(is_active=True)
    elif is_active in {"false", "0", "no"}:
        qs = qs.filter(is_active=False)

    risk = str(f.get("risk_status") or "").strip().upper()
    if risk and risk in RiskStatus.values:
        qs = qs.filter(risk_status=risk)

    assignee = str(f.get("assigned_user") or "").strip()
    if assignee in {"null", "none", "0"}:
        qs = qs.filter(assigned_user__isnull=True)
    elif assignee.isdigit():
        qs = qs.filter(assigned_user_id=int(assignee))

    qs = qs.order_by("-risk_score", "name")

    broken_map = {
        row["customer_id"]: row["c"]
        for row in PaymentPromise.objects.for_organization(organization)
        .filter(status=PaymentPromiseStatus.BROKEN)
        .values("customer_id")
        .annotate(c=Count("id"))
    }
    last_pay_map = {
        row["customer_id"]: row["last"]
        for row in Payment.objects.for_organization(organization)
        .filter(cancelled_at__isnull=True)
        .values("customer_id")
        .annotate(last=Max("payment_date"))
    }

    # Latest snapshot reasons (first seen per customer while iterating newest-first)
    reasons_map: dict[int, str] = {}
    for snap in (
        RiskSnapshot.objects.for_organization(organization)
        .order_by("-calculated_at", "-id")
        .iterator(chunk_size=200)
    ):
        if snap.customer_id in reasons_map:
            continue
        details = snap.score_details or {}
        reasons = details.get("reasons") or []
        if isinstance(reasons, list):
            labels = [
                str(item.get("label") or item.get("code") or item)
                if isinstance(item, dict)
                else str(item)
                for item in reasons
            ]
            reasons_map[snap.customer_id] = "; ".join(labels)
        elif reasons:
            reasons_map[snap.customer_id] = str(reasons)

    rows: list[dict[str, Any]] = []
    for customer in qs.iterator(chunk_size=100):
        metrics = customer_financial_metrics(customer)
        last_pay = last_pay_map.get(customer.id)
        rows.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "customer_code": customer.code,
                "risk_score": customer.risk_score,
                "risk_status": customer.risk_status,
                "risk_reasons": reasons_map.get(customer.id, ""),
                "overdue_balance": _money(metrics["overdue_balance"]),
                "avg_delay_days": metrics["avg_delay_days"],
                "broken_promise_count": broken_map.get(customer.id, 0),
                "last_payment_date": last_pay.isoformat() if last_pay else "",
                "assigned_user_id": customer.assigned_user_id,
            }
        )
    return rows
