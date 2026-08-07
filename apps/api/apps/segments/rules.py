"""NP-261 — segment rule evaluator."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer

OPERATORS = {
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "equal",
    "not_equal",
    "in",
    "not_in",
}


class RuleError(Exception):
    def __init__(self, message: str, code: str = "invalid_rule"):
        super().__init__(message)
        self.message = message
        self.code = code


def validate_rules(rules: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rules, dict) or not rules:
        raise RuleError("Kurallar nesne olmalı ({'all': [...]}).", "invalid_rule")
    if "all" not in rules and "any" not in rules:
        raise RuleError("Kök anahtar 'all' veya 'any' olmalı.", "invalid_rule")
    for key in ("all", "any"):
        if key in rules:
            if not isinstance(rules[key], list):
                raise RuleError(f"'{key}' bir dizi olmalı.", "invalid_rule")
            for clause in rules[key]:
                _validate_clause(clause)
    return rules


def _validate_clause(clause: Any) -> None:
    if not isinstance(clause, dict):
        raise RuleError("Kural maddesi nesne olmalı.", "invalid_rule")
    if "all" in clause or "any" in clause:
        validate_rules(clause)
        return
    field = clause.get("field")
    operator = clause.get("operator")
    if not field or not operator:
        raise RuleError("Her madde field ve operator içermeli.", "invalid_rule")
    if operator not in OPERATORS:
        raise RuleError(f"Geçersiz operator: {operator}", "invalid_operator")


def _customer_context(customer: Customer) -> dict[str, Any]:
    metrics = customer_financial_metrics(customer)
    today = timezone.localdate()
    overdue_days_max = metrics.get("oldest_overdue_days") or 0
    broken = PaymentPromise.objects.filter(
        customer=customer,
        status=PaymentPromiseStatus.BROKEN,
    ).count()
    created_days = (today - customer.created_at.date()).days if customer.created_at else 9999
    strategic = "strategic" in (customer.tags or []) or (
        (customer.collection_strategy or "").lower().find("stratejik") >= 0
    )
    return {
        "overdue_balance": metrics["overdue_balance"],
        "open_balance": metrics["open_balance"],
        "disputed_balance": metrics["disputed_balance"],
        "risk_level": customer.risk_status,
        "risk_status": customer.risk_status,
        "risk_score": customer.risk_score,
        "oldest_overdue_days": overdue_days_max,
        "broken_promise_count": broken,
        "days_since_created": created_days,
        "is_strategic": strategic,
        "is_new": created_days <= 90,
        "frequent_late": (metrics.get("avg_delay_days") or 0) >= 15,
    }


def _compare(left: Any, operator: str, right: Any) -> bool:
    if operator in {"in", "not_in"}:
        values = right if isinstance(right, (list, tuple, set)) else [right]
        present = left in values
        return present if operator == "in" else not present
    try:
        if isinstance(left, Decimal) or isinstance(right, (int, float, str, Decimal)):
            l = Decimal(str(left))
            r = Decimal(str(right))
            left, right = l, r
    except (InvalidOperation, TypeError, ValueError):
        pass
    if operator == "greater_than":
        return left > right
    if operator == "greater_than_or_equal":
        return left >= right
    if operator == "less_than":
        return left < right
    if operator == "less_than_or_equal":
        return left <= right
    if operator == "equal":
        return left == right
    if operator == "not_equal":
        return left != right
    return False


def evaluate_clause(ctx: dict[str, Any], clause: dict[str, Any]) -> bool:
    if "all" in clause:
        return all(evaluate_clause(ctx, c) for c in clause["all"])
    if "any" in clause:
        return any(evaluate_clause(ctx, c) for c in clause["any"])
    field = clause["field"]
    operator = clause["operator"]
    value = clause.get("value")
    left = ctx.get(field)
    if left is None:
        return False
    return _compare(left, operator, value)


def customer_matches_rules(customer: Customer, rules: dict[str, Any]) -> bool:
    if not rules:
        return False
    ctx = _customer_context(customer)
    if "all" in rules:
        return all(evaluate_clause(ctx, c) for c in rules["all"])
    if "any" in rules:
        return any(evaluate_clause(ctx, c) for c in rules["any"])
    return False


def evaluate_segment_customers(organization, rules: dict[str, Any]) -> list[Customer]:
    validate_rules(rules)
    customers = Customer.objects.for_organization(organization).filter(is_active=True)
    return [c for c in customers.iterator() if customer_matches_rules(c, rules)]


DEFAULT_SEGMENTS: list[dict[str, Any]] = [
    {
        "name": "Yüksek bakiye / düşük risk",
        "slug": "high-balance-low-risk",
        "rules": {
            "all": [
                {"field": "overdue_balance", "operator": "greater_than", "value": 100000},
                {"field": "risk_level", "operator": "in", "value": ["LOW", "MEDIUM"]},
            ]
        },
    },
    {
        "name": "Yüksek bakiye / yüksek risk",
        "slug": "high-balance-high-risk",
        "rules": {
            "all": [
                {"field": "overdue_balance", "operator": "greater_than", "value": 250000},
                {"field": "risk_level", "operator": "in", "value": ["HIGH", "CRITICAL"]},
            ]
        },
    },
    {
        "name": "Sık gecikenler",
        "slug": "frequent-late",
        "rules": {
            "all": [{"field": "frequent_late", "operator": "equal", "value": True}]
        },
    },
    {
        "name": "Sözünü tutmayanlar",
        "slug": "promise-breakers",
        "rules": {
            "all": [
                {
                    "field": "broken_promise_count",
                    "operator": "greater_than_or_equal",
                    "value": 2,
                }
            ]
        },
    },
    {
        "name": "Yeni müşteriler",
        "slug": "new-customers",
        "rules": {"all": [{"field": "is_new", "operator": "equal", "value": True}]},
    },
    {
        "name": "Stratejik müşteriler",
        "slug": "strategic",
        "rules": {
            "all": [{"field": "is_strategic", "operator": "equal", "value": True}]
        },
    },
    {
        "name": "90+ gün gecikmiş müşteriler",
        "slug": "overdue-90-plus",
        "rules": {
            "all": [
                {
                    "field": "oldest_overdue_days",
                    "operator": "greater_than_or_equal",
                    "value": 90,
                }
            ]
        },
    },
]


DEFAULT_STRATEGIES: dict[str, list[dict[str, Any]]] = {
    "high-balance-low-risk": [
        {"type": "EMAIL", "tone": "polite", "note": "Nazik e-posta"},
        {"type": "WAIT_DAYS", "wait_days": 7},
        {"type": "CALL_TASK", "note": "Telefon görevi"},
    ],
    "high-balance-high-risk": [
        {"type": "CALL_TASK", "note": "Telefon görevi"},
        {"type": "MANAGER_NOTIFY", "note": "Yönetici bildirimi"},
        {"type": "DAILY_FOLLOWUP", "note": "Günlük takip"},
    ],
    "strategic": [
        {"type": "NO_AUTO_MESSAGE"},
        {"type": "ACCOUNT_MANAGER_ONLY", "note": "Yalnızca hesap yöneticisi"},
    ],
}
