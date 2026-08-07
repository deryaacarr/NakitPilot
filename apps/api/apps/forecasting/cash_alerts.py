"""NP-274 — cash gap / insufficient balance alerts."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.forecasting.scenarios import run_scenario
from apps.forecasting.weekly import QUANTIZE, ZERO
from apps.notifications.models import (
    AlertSeverity,
    NotificationType,
    create_dashboard_alert,
)
from apps.organizations.models import Organization
from apps.payables.models import BankAccount, Payable, PayableStatus


# Default minimum safe balance if org has no setting
DEFAULT_SAFE_BALANCE = Decimal("50000.00")

# Heuristic keywords for payroll / tax weeks
PAYROLL_KEYWORDS = ("maaş", "maas", "salary", "payroll", "ücret", "ucret")
TAX_KEYWORDS = ("vergi", "kdv", "sgk", "stopaj", "tax", "muhtasar")


def _already_alerted_today(organization, category: str, entity_id: str = "") -> bool:
    from apps.notifications.models import DashboardAlert

    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    qs = DashboardAlert.objects.filter(
        organization=organization,
        category=category,
        created_at__gte=start,
    )
    if entity_id:
        qs = qs.filter(entity_id=str(entity_id))
    return qs.exists()


def evaluate_cash_gap_rules(
    organization_id: int,
    *,
    weeks: int = 13,
    min_safe_balance: Decimal | None = None,
    create_alerts: bool = True,
) -> dict[str, Any]:
    """
    Rules:
    - Forecast balance goes negative
    - Below minimum safe balance
    - Insufficient in payroll period
    - Gap in tax payment period
    """
    org = Organization.objects.get(pk=organization_id)
    safe = min_safe_balance if min_safe_balance is not None else DEFAULT_SAFE_BALANCE
    scenario = run_scenario(organization_id, scenario_type="BASE", weeks=weeks)

    findings: list[dict[str, Any]] = []
    alerts_created: list[int] = []

    for w in scenario["weeks"]:
        bal = Decimal(str(w["ending_balance"]))
        ws = w["week_start"]
        if bal < ZERO:
            findings.append(
                {
                    "rule": "NEGATIVE_BALANCE",
                    "week_start": ws,
                    "ending_balance": str(bal),
                    "severity": "CRITICAL",
                    "message": f"{ws} haftasında tahmini bakiye sıfırın altına düşüyor ({bal}).",
                }
            )
        elif bal < safe:
            findings.append(
                {
                    "rule": "BELOW_SAFE_BALANCE",
                    "week_start": ws,
                    "ending_balance": str(bal),
                    "severity": "WARNING",
                    "message": (
                        f"{ws} haftasında bakiye asgari güvenli seviyenin "
                        f"({safe}) altında: {bal}."
                    ),
                }
            )

    # Payroll / tax payable detection
    payables = Payable.objects.filter(
        organization_id=organization_id,
        status__in=[PayableStatus.OPEN, PayableStatus.PARTIALLY_PAID],
    )
    balance_by_week = {
        w["week_start"]: Decimal(str(w["ending_balance"])) for w in scenario["weeks"]
    }
    from apps.forecasting.weekly import iso_week_start

    for p in payables:
        text = f"{p.vendor_name} {p.description}".lower()
        ws = iso_week_start(p.due_date).isoformat()
        bal = balance_by_week.get(ws)
        if bal is None:
            continue
        needed = p.remaining_amount
        if bal < needed:
            if any(k in text for k in PAYROLL_KEYWORDS):
                findings.append(
                    {
                        "rule": "PAYROLL_SHORTFALL",
                        "week_start": ws,
                        "ending_balance": str(bal),
                        "payable_id": p.id,
                        "severity": "CRITICAL",
                        "message": (
                            f"Maaş döneminde yetersiz bakiye: {p.vendor_name} "
                            f"({needed}) — bakiye {bal}."
                        ),
                    }
                )
            if any(k in text for k in TAX_KEYWORDS):
                findings.append(
                    {
                        "rule": "TAX_SHORTFALL",
                        "week_start": ws,
                        "ending_balance": str(bal),
                        "payable_id": p.id,
                        "severity": "CRITICAL",
                        "message": (
                            f"Vergi ödeme döneminde açık riski: {p.vendor_name} "
                            f"({needed}) — bakiye {bal}."
                        ),
                    }
                )

    if create_alerts:
        for f in findings:
            cat = f"cash_gap_{f['rule'].lower()}"
            eid = f.get("week_start") or ""
            if _already_alerted_today(org, cat, eid):
                continue
            sev = (
                AlertSeverity.CRITICAL
                if f["severity"] == "CRITICAL"
                else AlertSeverity.WARNING
            )
            ntype = NotificationType.CASH_GAP
            alert = create_dashboard_alert(
                organization=org,
                title="Nakit açığı uyarısı",
                body=f["message"],
                severity=sev,
                notification_type=ntype,
                category=cat,
                entity_type="forecast_week",
                entity_id=eid,
                href="/forecast",
            )
            alerts_created.append(alert.id)

    return {
        "min_safe_balance": str(safe.quantize(QUANTIZE)),
        "minimum_cash": scenario["minimum_cash"],
        "minimum_cash_week": scenario["minimum_cash_week"],
        "findings": findings,
        "alerts_created": alerts_created,
        "finding_count": len(findings),
    }
