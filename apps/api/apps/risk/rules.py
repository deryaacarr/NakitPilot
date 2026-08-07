"""NP-100/101 rule-based risk score (0–100) with reason codes.

Kurallar (ilk sürüm):
+20  30 günden fazla gecikme
+15  60 günden fazla gecikme
+15  90 günden fazla gecikme
+15  Son 3 faturadan 2'si geç ödendi
+25  Bozulan ödeme sözü
+10  Son 7 günde iletişim kurulamadı
+15  Kredi limitinin üzerinde açık bakiye
−15  Düzenli ödeme geçmişi
−10  Son ödeme zamanında yapıldı

Seviyeler (NP-101):
0–24 LOW · 25–49 MEDIUM · 50–74 HIGH · 75–100 CRITICAL
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer, RiskStatus
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_actual_delay_days, invoice_overdue_days
from apps.payments.models import ZERO

OPEN_STATUSES = {
    InvoiceStatus.OPEN,
    InvoiceStatus.OVERDUE,
    InvoiceStatus.PARTIALLY_PAID,
}


class RiskReason(TypedDict):
    code: str
    label: str
    points: int


def risk_level_for_score(score: int) -> str:
    """NP-101 bands."""
    if score >= 75:
        return RiskStatus.CRITICAL
    if score >= 50:
        return RiskStatus.HIGH
    if score >= 25:
        return RiskStatus.MEDIUM
    return RiskStatus.LOW


def clamp_score(score: int) -> int:
    return max(0, min(100, score))


def _reason(code: str, label: str, points: int) -> RiskReason:
    return {"code": code, "label": label, "points": points}


def compute_customer_risk_score(
    customer: Customer,
    *,
    as_of: date | None = None,
) -> tuple[int, str, dict[str, Any]]:
    """Pure rule evaluation → (score, level, score_details).

    score_details always includes ``reasons`` (list of {code, label, points})
    plus diagnostic meta for debugging.
    """
    today = as_of or timezone.localdate()
    reasons: list[RiskReason] = []
    meta: dict[str, Any] = {}
    score = 0

    invoices = list(
        Invoice.objects.filter(customer=customer)
        .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED])
        .order_by("-invoice_date", "-id")
    )

    # --- Overdue day buckets (stacking) ---
    max_overdue = 0
    for inv in invoices:
        if inv.status not in OPEN_STATUSES:
            continue
        days = invoice_overdue_days(inv, as_of=today)
        if days > max_overdue:
            max_overdue = days

    meta["max_overdue_days"] = max_overdue
    if max_overdue > 30:
        score += 20
        reasons.append(_reason("OVERDUE_GT_30", "30 günden fazla gecikme", 20))
    if max_overdue > 60:
        score += 15
        reasons.append(_reason("OVERDUE_GT_60", "60 günden fazla gecikme", 15))
    if max_overdue > 90:
        score += 15
        reasons.append(_reason("OVERDUE_GT_90", "90 günden fazla gecikme", 15))

    # --- Last 3 paid invoices: 2+ late ---
    paid = [inv for inv in invoices if inv.status == InvoiceStatus.PAID][:3]
    late_count = 0
    for inv in paid:
        delay = invoice_actual_delay_days(inv)
        if delay is not None and delay > 0:
            late_count += 1
    meta["last_3_paid_late_count"] = late_count
    if len(paid) >= 2 and late_count >= 2:
        score += 15
        reasons.append(
            _reason(
                "TWO_OF_LAST_THREE_LATE",
                "Son 3 faturadan 2'si geç ödendi",
                15,
            )
        )

    # --- Broken promise ---
    broken = PaymentPromise.objects.filter(
        customer=customer,
        status=PaymentPromiseStatus.BROKEN,
    ).exists()
    meta["has_broken_promise"] = broken
    if broken:
        score += 25
        reasons.append(_reason("BROKEN_PROMISE", "Ödeme sözü tutulmadı", 25))

    # --- No contact in 7 days ---
    last_contact = customer.last_contact_at
    no_contact = last_contact is None or (timezone.now() - last_contact).days > 7
    meta["no_contact_7d"] = no_contact
    if no_contact:
        score += 10
        reasons.append(
            _reason("NO_CONTACT_7D", "Son 7 günde iletişim kurulamadı", 10)
        )

    # --- Over credit limit ---
    metrics = customer_financial_metrics(customer)
    open_balance = Decimal(str(metrics.get("open_balance") or ZERO))
    credit_limit = customer.credit_limit or ZERO
    over_limit = credit_limit > ZERO and open_balance > credit_limit
    meta["open_balance"] = str(open_balance)
    meta["credit_limit"] = str(credit_limit)
    meta["over_credit_limit"] = over_limit
    if over_limit:
        score += 15
        reasons.append(
            _reason(
                "OVER_CREDIT_LIMIT",
                "Kredi limitinin üzerinde açık bakiye",
                15,
            )
        )

    # --- Regular payment history (last 5 paid, ≥80% on time, min 3) ---
    recent_paid = [inv for inv in invoices if inv.status == InvoiceStatus.PAID][:5]
    on_time = 0
    for inv in recent_paid:
        delay = invoice_actual_delay_days(inv)
        if delay is not None and delay <= 0:
            on_time += 1
    regular = len(recent_paid) >= 3 and (on_time / len(recent_paid)) >= 0.8
    meta["recent_paid_count"] = len(recent_paid)
    meta["recent_on_time_count"] = on_time
    meta["regular_payer"] = regular
    if regular:
        score -= 15
        reasons.append(
            _reason("REGULAR_PAYMENT_HISTORY", "Düzenli ödeme geçmişi", -15)
        )

    # --- Last payment on time ---
    last_on_time = False
    if recent_paid:
        delay = invoice_actual_delay_days(recent_paid[0])
        last_on_time = delay is not None and delay <= 0
    meta["last_payment_on_time"] = last_on_time
    if last_on_time:
        score -= 10
        reasons.append(
            _reason("LAST_PAYMENT_ON_TIME", "Son ödeme zamanında yapıldı", -10)
        )

    score = clamp_score(score)
    level = risk_level_for_score(score)
    details: dict[str, Any] = {
        "score": score,
        "level": level,
        "reasons": reasons,
        "meta": meta,
    }
    return score, level, details
