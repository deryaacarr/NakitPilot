"""NP-270 — expected outflows and net cash helpers."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.payables.models import (
    ZERO,
    ExpectedExpense,
    Payable,
    PayableStatus,
    RecurringExpense,
)

OPEN_PAYABLE = {PayableStatus.OPEN, PayableStatus.PARTIALLY_PAID}


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def expected_outflows_by_week(
    organization,
    *,
    weeks: int = 13,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Aggregate payables + recurring + expected expenses into weekly buckets."""
    start = _week_start(as_of or date.today())
    buckets: list[dict[str, Any]] = []
    for i in range(weeks):
        ws = start + timedelta(days=7 * i)
        we = ws + timedelta(days=6)
        buckets.append(
            {
                "week_start": ws.isoformat(),
                "week_end": we.isoformat(),
                "payable_amount": ZERO,
                "recurring_amount": ZERO,
                "expected_amount": ZERO,
                "total_outflow": ZERO,
            }
        )

    def _bucket_index(d: date) -> int | None:
        if d < start:
            return None
        idx = (d - start).days // 7
        return idx if 0 <= idx < weeks else None

    for p in Payable.objects.for_organization(organization).filter(status__in=OPEN_PAYABLE):
        idx = _bucket_index(p.due_date)
        if idx is None:
            continue
        buckets[idx]["payable_amount"] += p.remaining_amount

    end_horizon = start + timedelta(days=7 * weeks - 1)
    for rexp in RecurringExpense.objects.for_organization(organization).filter(
        is_active=True
    ):
        cursor = max(rexp.start_date, start)
        # Align to day_of_month
        while cursor <= end_horizon and (rexp.end_date is None or cursor <= rexp.end_date):
            day = min(rexp.day_of_month, 28)
            try:
                occurrence = cursor.replace(day=day)
            except ValueError:
                occurrence = cursor.replace(day=28)
            if occurrence < start:
                # next month
                if cursor.month == 12:
                    cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
                else:
                    cursor = cursor.replace(month=cursor.month + 1, day=1)
                continue
            if occurrence > end_horizon:
                break
            if rexp.end_date and occurrence > rexp.end_date:
                break
            idx = _bucket_index(occurrence)
            if idx is not None:
                buckets[idx]["recurring_amount"] += rexp.amount
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1, day=1)

    for exp in ExpectedExpense.objects.for_organization(organization).filter(
        expected_date__gte=start,
        expected_date__lte=end_horizon,
    ):
        idx = _bucket_index(exp.expected_date)
        if idx is not None:
            buckets[idx]["expected_amount"] += exp.expected_amount

    for b in buckets:
        b["total_outflow"] = (
            b["payable_amount"] + b["recurring_amount"] + b["expected_amount"]
        )
        for key in (
            "payable_amount",
            "recurring_amount",
            "expected_amount",
            "total_outflow",
        ):
            b[key] = str(b[key])
    return buckets


def net_cash_summary(
    organization,
    *,
    expected_collections: list[dict[str, Any]] | None = None,
    weeks: int = 13,
) -> dict[str, Any]:
    """
    Beklenen tahsilatlar - beklenen ödemeler = tahmini net nakit.
    expected_collections: optional list with week_start + expected amount.
    """
    outflows = expected_outflows_by_week(organization, weeks=weeks)
    collection_by_week: dict[str, Decimal] = {}
    if expected_collections:
        for row in expected_collections:
            ws = row.get("week_start")
            amt = Decimal(str(row.get("expected") or row.get("expected_amount") or 0))
            if ws:
                collection_by_week[ws] = collection_by_week.get(ws, ZERO) + amt

    weeks_out = []
    total_in = ZERO
    total_out = ZERO
    for b in outflows:
        inflow = collection_by_week.get(b["week_start"], ZERO)
        outflow = Decimal(b["total_outflow"])
        net = inflow - outflow
        total_in += inflow
        total_out += outflow
        weeks_out.append(
            {
                **b,
                "expected_collection": str(inflow),
                "net_cash": str(net),
            }
        )
    return {
        "weeks": weeks_out,
        "total_expected_collections": str(total_in),
        "total_expected_outflows": str(total_out),
        "total_net_cash": str(total_in - total_out),
    }
