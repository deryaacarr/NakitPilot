"""NP-272 — cash-flow scenario builder."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.forecasting.weekly import (
    QUANTIZE,
    ZERO,
    calculate_organization_forecast,
    iso_week_start,
)
from apps.payables.services import expected_outflows_by_week, net_cash_summary


class ScenarioType:
    BASE = "BASE"
    OPTIMISTIC = "OPTIMISTIC"
    PESSIMISTIC = "PESSIMISTIC"
    CRISIS = "CRISIS"
    CUSTOM = "CUSTOM"

    ALL = (BASE, OPTIMISTIC, PESSIMISTIC, CRISIS, CUSTOM)
    LABELS = {
        BASE: "Temel",
        OPTIMISTIC: "İyimser",
        PESSIMISTIC: "Kötümser",
        CRISIS: "Kriz",
        CUSTOM: "Özel senaryo",
    }


@dataclass
class ScenarioVariables:
    """User-tunable scenario knobs (NP-272)."""

    collection_probability_factor: Decimal = Decimal("1.0")  # multiply expected
    average_delay_days_delta: int = 0  # shift expected weeks
    non_paying_customer_ids: list[int] = field(default_factory=list)
    large_payment_customer_id: int | None = None
    large_payment_date: date | None = None
    large_payment_amount: Decimal | None = None
    expense_increase_factor: Decimal = Decimal("1.0")
    fx_change_percent: Decimal = Decimal("0")  # +/- on foreign-ish totals (simplified)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ScenarioVariables:
        data = data or {}
        lp_date = data.get("large_payment_date")
        if isinstance(lp_date, str) and lp_date:
            lp_date = date.fromisoformat(lp_date)
        elif not lp_date:
            lp_date = None
        amount = data.get("large_payment_amount")
        return cls(
            collection_probability_factor=Decimal(
                str(data.get("collection_probability_factor", 1))
            ),
            average_delay_days_delta=int(data.get("average_delay_days_delta") or 0),
            non_paying_customer_ids=[
                int(x) for x in (data.get("non_paying_customer_ids") or [])
            ],
            large_payment_customer_id=(
                int(data["large_payment_customer_id"])
                if data.get("large_payment_customer_id") is not None
                else None
            ),
            large_payment_date=lp_date,
            large_payment_amount=(
                Decimal(str(amount)) if amount is not None else None
            ),
            expense_increase_factor=Decimal(str(data.get("expense_increase_factor", 1))),
            fx_change_percent=Decimal(str(data.get("fx_change_percent", 0))),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "collection_probability_factor": str(self.collection_probability_factor),
            "average_delay_days_delta": self.average_delay_days_delta,
            "non_paying_customer_ids": self.non_paying_customer_ids,
            "large_payment_customer_id": self.large_payment_customer_id,
            "large_payment_date": (
                self.large_payment_date.isoformat() if self.large_payment_date else None
            ),
            "large_payment_amount": (
                str(self.large_payment_amount) if self.large_payment_amount is not None else None
            ),
            "expense_increase_factor": str(self.expense_increase_factor),
            "fx_change_percent": str(self.fx_change_percent),
        }


PRESETS: dict[str, ScenarioVariables] = {
    ScenarioType.BASE: ScenarioVariables(),
    ScenarioType.OPTIMISTIC: ScenarioVariables(
        collection_probability_factor=Decimal("1.15"),
        average_delay_days_delta=-7,
        expense_increase_factor=Decimal("0.95"),
    ),
    ScenarioType.PESSIMISTIC: ScenarioVariables(
        collection_probability_factor=Decimal("0.75"),
        average_delay_days_delta=14,
        expense_increase_factor=Decimal("1.10"),
    ),
    ScenarioType.CRISIS: ScenarioVariables(
        collection_probability_factor=Decimal("0.45"),
        average_delay_days_delta=30,
        expense_increase_factor=Decimal("1.25"),
        fx_change_percent=Decimal("15"),
    ),
}


def _shift_week_amount(
    weeks: list[dict[str, Any]],
    *,
    from_idx: int,
    to_idx: int,
    amount: Decimal,
    key: str = "expected",
) -> None:
    if from_idx < 0 or from_idx >= len(weeks):
        return
    to_idx = max(0, min(to_idx, len(weeks) - 1))
    cur = Decimal(str(weeks[from_idx].get(key) or 0))
    move = min(cur, amount)
    weeks[from_idx][key] = str((cur - move).quantize(QUANTIZE))
    dest = Decimal(str(weeks[to_idx].get(key) or 0))
    weeks[to_idx][key] = str((dest + move).quantize(QUANTIZE))


def apply_scenario_to_collections(
    weeks: list[dict[str, Any]],
    variables: ScenarioVariables,
    *,
    contributions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Mutate a copy of collection weeks according to scenario variables."""
    out = deepcopy(weeks)
    factor = variables.collection_probability_factor
    fx = Decimal("1") + (variables.fx_change_percent / Decimal("100"))

    # Zero-out / reduce non-paying customers from contributions if available
    remove_by_week: dict[str, Decimal] = {}
    if contributions and variables.non_paying_customer_ids:
        skip = set(variables.non_paying_customer_ids)
        for c in contributions:
            if c.get("customer_id") in skip:
                ws = c.get("expected_week") or c.get("expected_week_start")
                amt = Decimal(str(c.get("expected_amount") or c.get("expected") or 0))
                if ws:
                    key = ws if isinstance(ws, str) else ws.isoformat()
                    remove_by_week[key] = remove_by_week.get(key, ZERO) + amt

    for w in out:
        exp = Decimal(str(w.get("expected") or w.get("expected_amount") or 0))
        ws = w.get("week_start")
        if isinstance(ws, date):
            ws_key = ws.isoformat()
        else:
            ws_key = str(ws)
        if ws_key in remove_by_week:
            exp = max(ZERO, exp - remove_by_week[ws_key])
        exp = (exp * factor * fx).quantize(QUANTIZE)
        if "expected" in w:
            w["expected"] = str(exp)
        if "expected_amount" in w:
            w["expected_amount"] = str(exp)
        # Keep optimistic/pessimistic scaled lightly
        for k in ("optimistic", "optimistic_amount", "pessimistic", "pessimistic_amount"):
            if k in w:
                w[k] = str((Decimal(str(w[k])) * factor * fx).quantize(QUANTIZE))

    # Delay shift: move expected mass forward/backward by week buckets
    if variables.average_delay_days_delta and len(out) > 1:
        shift_weeks = int(round(variables.average_delay_days_delta / 7))
        if shift_weeks != 0:
            # Work on a snapshot of amounts
            amounts = [Decimal(str(w.get("expected") or w.get("expected_amount") or 0)) for w in out]
            new_amounts = [ZERO] * len(out)
            for i, amt in enumerate(amounts):
                j = max(0, min(len(out) - 1, i + shift_weeks))
                new_amounts[j] += amt
            for i, w in enumerate(out):
                val = str(new_amounts[i].quantize(QUANTIZE))
                if "expected" in w:
                    w["expected"] = val
                if "expected_amount" in w:
                    w["expected_amount"] = val

    # Inject large payment on a date
    if variables.large_payment_date and variables.large_payment_amount:
        target = iso_week_start(variables.large_payment_date).isoformat()
        for w in out:
            ws = w.get("week_start")
            ws_key = ws.isoformat() if isinstance(ws, date) else str(ws)
            if ws_key == target:
                exp = Decimal(str(w.get("expected") or w.get("expected_amount") or 0))
                exp = (exp + variables.large_payment_amount).quantize(QUANTIZE)
                if "expected" in w:
                    w["expected"] = str(exp)
                if "expected_amount" in w:
                    w["expected_amount"] = str(exp)
                break

    return out


def run_scenario(
    organization_id: int,
    *,
    scenario_type: str = ScenarioType.BASE,
    variables: dict[str, Any] | None = None,
    weeks: int = 13,
    starting_cash: Decimal | None = None,
) -> dict[str, Any]:
    """Build scenario collection + outflow + running cash (NP-272)."""
    stype = (scenario_type or ScenarioType.BASE).upper()
    if stype not in ScenarioType.ALL:
        stype = ScenarioType.CUSTOM

    base_vars = PRESETS.get(stype, ScenarioVariables())
    custom = ScenarioVariables.from_dict(variables)
    # Merge: custom overrides when provided as CUSTOM or when variables passed
    if stype == ScenarioType.CUSTOM or variables:
        merged = ScenarioVariables(
            collection_probability_factor=(
                custom.collection_probability_factor
                if variables and "collection_probability_factor" in variables
                else base_vars.collection_probability_factor
            ),
            average_delay_days_delta=(
                custom.average_delay_days_delta
                if variables and "average_delay_days_delta" in variables
                else base_vars.average_delay_days_delta
            ),
            non_paying_customer_ids=custom.non_paying_customer_ids
            or base_vars.non_paying_customer_ids,
            large_payment_customer_id=custom.large_payment_customer_id
            or base_vars.large_payment_customer_id,
            large_payment_date=custom.large_payment_date or base_vars.large_payment_date,
            large_payment_amount=custom.large_payment_amount
            if custom.large_payment_amount is not None
            else base_vars.large_payment_amount,
            expense_increase_factor=(
                custom.expense_increase_factor
                if variables and "expense_increase_factor" in variables
                else base_vars.expense_increase_factor
            ),
            fx_change_percent=(
                custom.fx_change_percent
                if variables and "fx_change_percent" in variables
                else base_vars.fx_change_percent
            ),
        )
    else:
        merged = base_vars

    from apps.organizations.models import Organization
    from apps.payables.models import BankAccount

    org = Organization.objects.get(pk=organization_id)
    forecast = calculate_organization_forecast(
        organization_id, persist=False, weeks=weeks
    )
    raw_weeks = []
    for w in forecast["weeks"]:
        raw_weeks.append(
            {
                "week_start": w["week_start"].isoformat()
                if isinstance(w["week_start"], date)
                else w["week_start"],
                "expected": str(w["expected_amount"]),
                "expected_amount": str(w["expected_amount"]),
                "optimistic": str(w["optimistic_amount"]),
                "pessimistic": str(w["pessimistic_amount"]),
                "nominal": str(w["nominal_amount"]),
            }
        )
    contributions = forecast.get("contributions") or []
    adjusted = apply_scenario_to_collections(
        raw_weeks, merged, contributions=contributions
    )

    outflows = expected_outflows_by_week(org, weeks=weeks)
    for o in outflows:
        total = Decimal(str(o["total_outflow"])) * merged.expense_increase_factor
        o["total_outflow"] = str(total.quantize(QUANTIZE))
        o["payable_amount"] = str(
            (Decimal(str(o["payable_amount"])) * merged.expense_increase_factor).quantize(
                QUANTIZE
            )
        )

    net = net_cash_summary(
        org, expected_collections=adjusted, weeks=weeks
    )
    # Rebuild weeks with adjusted outflows
    outflow_map = {o["week_start"]: Decimal(str(o["total_outflow"])) for o in outflows}
    if starting_cash is None:
        agg = BankAccount.objects.filter(
            organization_id=organization_id, is_active=True
        )
        starting_cash = sum((a.available_balance for a in agg), ZERO)

    running = Decimal(str(starting_cash))
    min_cash = running
    min_week = None
    gap_weeks: list[str] = []
    timeline = []
    for w in adjusted:
        ws = w["week_start"]
        inflow = Decimal(str(w.get("expected") or 0))
        outflow = outflow_map.get(ws, ZERO)
        running = (running + inflow - outflow).quantize(QUANTIZE)
        if running < min_cash:
            min_cash = running
            min_week = ws
        if running < ZERO:
            gap_weeks.append(ws)
        timeline.append(
            {
                "week_start": ws,
                "expected_collection": str(inflow),
                "expected_outflow": str(outflow),
                "net_cash_flow": str((inflow - outflow).quantize(QUANTIZE)),
                "ending_balance": str(running),
            }
        )

    return {
        "scenario_type": stype,
        "scenario_label": ScenarioType.LABELS.get(stype, stype),
        "variables": merged.as_dict(),
        "starting_cash": str(Decimal(str(starting_cash)).quantize(QUANTIZE)),
        "ending_cash": str(running),
        "minimum_cash": str(min_cash),
        "minimum_cash_week": min_week,
        "gap_weeks": gap_weeks,
        "weeks": timeline,
        "total_expected_collections": net["total_expected_collections"],
        "total_expected_outflows": str(
            sum((Decimal(str(o["total_outflow"])) for o in outflows), ZERO).quantize(
                QUANTIZE
            )
        ),
    }
