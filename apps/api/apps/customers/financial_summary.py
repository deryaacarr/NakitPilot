"""NP-413 — customer financial summary series + insight copy."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_actual_delay_days
from apps.payments.models import Payment, ZERO

OPEN_STATUSES = {
    InvoiceStatus.OPEN,
    InvoiceStatus.OVERDUE,
    InvoiceStatus.PARTIALLY_PAID,
}


def _month_starts(months: int, *, as_of: date) -> list[date]:
    cursor = date(as_of.year, as_of.month, 1)
    out: list[date] = []
    for _ in range(months):
        out.append(cursor)
        if cursor.month == 1:
            cursor = date(cursor.year - 1, 12, 1)
        else:
            cursor = date(cursor.year, cursor.month - 1, 1)
    out.reverse()
    return out


def _month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def customer_financial_summary(customer, *, months: int = 12) -> dict[str, Any]:
    as_of = timezone.localdate()
    starts = _month_starts(months, as_of=as_of)
    currency = "TRY"

    inv_rows = (
        Invoice.objects.filter(customer=customer)
        .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED])
        .annotate(month=TruncMonth("invoice_date"))
        .values("month")
        .annotate(total=Sum("total_amount"))
    )
    inv_by_month = {
        (row["month"].date() if hasattr(row["month"], "date") else row["month"]): row["total"] or ZERO
        for row in inv_rows
        if row["month"]
    }

    pay_rows = (
        Payment.objects.filter(customer=customer, cancelled_at__isnull=True)
        .annotate(month=TruncMonth("payment_date"))
        .values("month")
        .annotate(total=Sum("amount"))
    )
    pay_by_month = {
        (row["month"].date() if hasattr(row["month"], "date") else row["month"]): row["total"] or ZERO
        for row in pay_rows
        if row["month"]
    }

    invoices = list(
        Invoice.objects.filter(customer=customer).exclude(
            status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]
        )
    )

    monthly_invoice: list[dict[str, Any]] = []
    monthly_payment: list[dict[str, Any]] = []
    open_balance_trend: list[dict[str, Any]] = []
    avg_delay_trend: list[dict[str, Any]] = []
    on_time_rate_trend: list[dict[str, Any]] = []

    for start in starts:
        end = _month_end(start)
        key = start
        inv_total = inv_by_month.get(key, ZERO)
        pay_total = pay_by_month.get(key, ZERO)
        monthly_invoice.append(
            {"month": start.isoformat()[:7], "amount": str(inv_total)}
        )
        monthly_payment.append(
            {"month": start.isoformat()[:7], "amount": str(pay_total)}
        )

        open_amt = ZERO
        delays: list[int] = []
        paid_in_month = 0
        on_time = 0
        for inv in invoices:
            if inv.invoice_date > end:
                continue
            rem = inv.remaining_amount()
            # Approximate open at month end: unpaid and due/issued by then
            if inv.status in OPEN_STATUSES and rem > ZERO and inv.invoice_date <= end:
                open_amt += rem
            if inv.payment_completion_date and start <= inv.payment_completion_date <= end:
                paid_in_month += 1
                actual = invoice_actual_delay_days(inv)
                if actual is not None:
                    delays.append(actual)
                    if actual <= 0:
                        on_time += 1
                else:
                    on_time += 1

        open_balance_trend.append(
            {"month": start.isoformat()[:7], "amount": str(open_amt)}
        )
        avg_delay_trend.append(
            {
                "month": start.isoformat()[:7],
                "days": int(round(sum(delays) / len(delays))) if delays else None,
            }
        )
        on_time_rate_trend.append(
            {
                "month": start.isoformat()[:7],
                "rate": round(on_time / paid_in_month, 4) if paid_in_month else None,
                "paid_count": paid_in_month,
            }
        )

    # Insights from last 3 months of avg delay
    recent_delays = [p["days"] for p in avg_delay_trend[-3:] if p["days"] is not None]
    insights: list[str] = []
    if len(recent_delays) >= 2:
        first, last = recent_delays[0], recent_delays[-1]
        if last > first:
            insights.append(
                f"Son 3 ayda ortalama ödeme gecikmesi {first} günden {last} güne yükseldi."
            )
        elif last < first:
            insights.append(
                f"Son 3 ayda ortalama ödeme gecikmesi {first} günden {last} güne düştü."
            )
        else:
            insights.append(
                f"Son 3 ayda ortalama ödeme gecikmesi {last} gün civarında sabit."
            )
    elif recent_delays:
        insights.append(f"Son dönemde ortalama ödeme gecikmesi {recent_delays[-1]} gün.")

    pay_last3 = sum(Decimal(p["amount"]) for p in monthly_payment[-3:])
    inv_last3 = sum(Decimal(p["amount"]) for p in monthly_invoice[-3:])
    if inv_last3 > ZERO:
        ratio = (pay_last3 / inv_last3 * Decimal("100")).quantize(Decimal("0.1"))
        insights.append(
            f"Son 3 ayda tahsilat / fatura oranı yaklaşık %{ratio}."
        )

    if not insights:
        insights.append("Henüz yeterli finansal geçmiş yok; fatura ve ödeme geldikçe trend oluşur.")

    return {
        "as_of": as_of.isoformat(),
        "currency": currency,
        "monthly_invoices": monthly_invoice,
        "monthly_payments": monthly_payment,
        "open_balance_trend": open_balance_trend,
        "avg_delay_trend": avg_delay_trend,
        "on_time_payment_rate": on_time_rate_trend,
        "insights": insights,
    }
