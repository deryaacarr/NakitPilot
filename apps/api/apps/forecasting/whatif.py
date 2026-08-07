"""NP-273 — what-if analysis (e.g. customer pays late)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer
from apps.forecasting.scenarios import run_scenario
from apps.forecasting.weekly import QUANTIZE, ZERO, calculate_organization_forecast, iso_week_start
from apps.invoices.models import Invoice, InvoiceStatus
from apps.payables.models import BankAccount, Payable, PayableStatus
from apps.payables.services import expected_outflows_by_week


def what_if_customer_late_payment(
    organization_id: int,
    *,
    customer_id: int,
    delay_days: int = 30,
    amount: Decimal | None = None,
    weeks: int = 13,
) -> dict[str, Any]:
    """
    ABC Elektrik 450.000 TL'yi 30 gün geç öderse ne olur? (NP-273)

    Returns minimum cash, first gap week, affected payment plans, risky periods.
    """
    customer = Customer.objects.filter(
        pk=customer_id, organization_id=organization_id
    ).first()
    if customer is None:
        raise ValueError("customer_not_found")

    baseline = run_scenario(organization_id, scenario_type="BASE", weeks=weeks)

    # Scenario: zero this customer's expected collections then re-add delayed
    forecast = calculate_organization_forecast(
        organization_id, persist=False, weeks=weeks
    )
    contribs = [
        c
        for c in forecast.get("contributions", [])
        if c.get("customer_id") == customer_id
    ]
    total_expected = sum((Decimal(str(c["expected_amount"])) for c in contribs), ZERO)
    impact_amount = amount if amount is not None else total_expected
    if impact_amount <= ZERO and amount is not None:
        impact_amount = amount

    variables = {
        "non_paying_customer_ids": [customer_id],
        "large_payment_customer_id": customer_id,
        "large_payment_amount": str(impact_amount),
        "large_payment_date": (
            timezone.localdate() + timedelta(days=max(delay_days, 1))
        ).isoformat(),
        "collection_probability_factor": "1.0",
    }
    stressed = run_scenario(
        organization_id,
        scenario_type="CUSTOM",
        variables=variables,
        weeks=weeks,
    )

    # Affected payment plans / promises
    promises = list(
        PaymentPromise.objects.filter(
            organization_id=organization_id,
            customer_id=customer_id,
            status__in=[
                PaymentPromiseStatus.PENDING,
                PaymentPromiseStatus.PARTIALLY_FULFILLED,
            ],
        ).order_by("promised_date")[:20]
    )
    affected_promises = [
        {
            "id": p.id,
            "promised_date": p.promised_date.isoformat(),
            "amount": str(p.amount),
            "status": p.status,
        }
        for p in promises
    ]

    open_invoices = list(
        Invoice.objects.filter(
            organization_id=organization_id,
            customer_id=customer_id,
            status__in=[
                InvoiceStatus.OPEN,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.PARTIALLY_PAID,
            ],
        ).order_by("due_date")[:20]
    )
    affected_invoices = [
        {
            "id": inv.id,
            "number": inv.number,
            "due_date": inv.due_date.isoformat(),
            "remaining": str(inv.remaining_amount()),
        }
        for inv in open_invoices
    ]

    # Payables that may be at risk in gap weeks
    gap_weeks = set(stressed.get("gap_weeks") or [])
    risky_payables: list[dict[str, Any]] = []
    if gap_weeks:
        for p in Payable.objects.filter(
            organization_id=organization_id,
            status__in=[PayableStatus.OPEN, PayableStatus.PARTIALLY_PAID],
        ).order_by("due_date")[:50]:
            ws = iso_week_start(p.due_date).isoformat()
            if ws in gap_weeks:
                risky_payables.append(
                    {
                        "id": p.id,
                        "vendor_name": p.vendor_name,
                        "due_date": p.due_date.isoformat(),
                        "remaining": str(p.remaining_amount),
                        "week_start": ws,
                    }
                )

    baseline_min = Decimal(str(baseline["minimum_cash"]))
    stressed_min = Decimal(str(stressed["minimum_cash"]))

    return {
        "customer": {"id": customer.id, "name": customer.name},
        "assumption": {
            "delay_days": delay_days,
            "amount": str(impact_amount.quantize(QUANTIZE)),
            "delayed_to": variables["large_payment_date"],
        },
        "baseline": {
            "minimum_cash": baseline["minimum_cash"],
            "minimum_cash_week": baseline["minimum_cash_week"],
            "ending_cash": baseline["ending_cash"],
            "gap_weeks": baseline["gap_weeks"],
        },
        "scenario": {
            "minimum_cash": stressed["minimum_cash"],
            "minimum_cash_week": stressed["minimum_cash_week"],
            "ending_cash": stressed["ending_cash"],
            "gap_weeks": stressed["gap_weeks"],
            "weeks": stressed["weeks"],
        },
        "impact": {
            "minimum_cash_delta": str((stressed_min - baseline_min).quantize(QUANTIZE)),
            "first_gap_week": (stressed["gap_weeks"] or [None])[0],
            "gap_week_count": len(stressed["gap_weeks"]),
        },
        "affected_payment_plans": affected_promises,
        "affected_invoices": affected_invoices,
        "risky_periods": [
            {"week_start": w, "reason": "Tahmini bakiye sıfırın altına düşüyor"}
            for w in stressed["gap_weeks"]
        ],
        "risky_payables": risky_payables,
    }
