"""Nested condition expression evaluator (NP-212)."""

from __future__ import annotations

from typing import Any

from apps.workflows.enums import WorkflowConditionOperator
from apps.workflows.models import WorkflowCondition, WorkflowStep

OPERATOR_ALIASES: dict[str, str] = {
    "equals": WorkflowConditionOperator.EQ,
    "eq": WorkflowConditionOperator.EQ,
    "not_equals": WorkflowConditionOperator.NE,
    "ne": WorkflowConditionOperator.NE,
    "greater_than": WorkflowConditionOperator.GT,
    "gt": WorkflowConditionOperator.GT,
    "gte": WorkflowConditionOperator.GTE,
    "less_than": WorkflowConditionOperator.LT,
    "lt": WorkflowConditionOperator.LT,
    "lte": WorkflowConditionOperator.LTE,
    "in": WorkflowConditionOperator.IN,
    "not_in": WorkflowConditionOperator.NOT_IN,
    "contains": WorkflowConditionOperator.CONTAINS,
    "is_empty": WorkflowConditionOperator.IS_EMPTY,
    "is_not_empty": WorkflowConditionOperator.IS_NOT_EMPTY,
}


def normalize_operator(op: str) -> str:
    key = (op or "").strip().lower()
    return OPERATOR_ALIASES.get(key, key)


def resolve_context_value(context: dict[str, Any], field: str) -> Any:
    """Resolve dotted paths like invoice.overdue_days from nested context."""
    if field in context:
        return context[field]
    # Alias risk_level → risk_status for customer payloads.
    aliases = {
        "customer.risk_level": ("customer", "risk_status"),
    }
    if field in aliases:
        parts = aliases[field]
        cur: Any = context
        for part in parts:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur

    parts = field.split(".")
    cur = context
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) == 0
    return False


def evaluate_predicate(predicate: dict[str, Any], context: dict[str, Any]) -> bool:
    field = predicate.get("field") or ""
    op = normalize_operator(str(predicate.get("operator") or "eq"))
    right = predicate.get("value")
    if isinstance(right, dict) and "value" in right and len(right) == 1:
        right = right["value"]

    left = resolve_context_value(context, field)

    if op in {WorkflowConditionOperator.IS_EMPTY, "is_empty"}:
        return _is_empty(left)
    if op in {WorkflowConditionOperator.IS_NOT_EMPTY, "is_not_empty"}:
        return not _is_empty(left)

    if op in {WorkflowConditionOperator.EQ, "eq", "equals"}:
        return left == right
    if op in {WorkflowConditionOperator.NE, "ne", "not_equals"}:
        return left != right

    if op in {
        WorkflowConditionOperator.GT,
        WorkflowConditionOperator.GTE,
        WorkflowConditionOperator.LT,
        WorkflowConditionOperator.LTE,
        "gt",
        "gte",
        "lt",
        "lte",
        "greater_than",
        "less_than",
    }:
        if left is None or right is None:
            return False
        try:
            lv, rv = float(left), float(right)
        except (TypeError, ValueError):
            return False
        if op in {WorkflowConditionOperator.GT, "gt", "greater_than"}:
            return lv > rv
        if op in {WorkflowConditionOperator.GTE, "gte"}:
            return lv >= rv
        if op in {WorkflowConditionOperator.LT, "lt", "less_than"}:
            return lv < rv
        return lv <= rv

    if op in {WorkflowConditionOperator.IN, "in"}:
        return left in (right or [])
    if op in {WorkflowConditionOperator.NOT_IN, "not_in"}:
        return left not in (right or [])

    if op in {WorkflowConditionOperator.CONTAINS, "contains"}:
        if left is None:
            return False
        if isinstance(left, str):
            return str(right) in left
        if isinstance(left, (list, tuple, set)):
            return right in left
        return False

    return False


def evaluate_expression(expression: Any, context: dict[str, Any]) -> bool:
    """
    Evaluate nested {"all": [...]} / {"any": [...]} trees, or a single predicate.
    Empty / missing expression is True (pass-through).
    """
    if expression is None or expression == {} or expression == []:
        return True
    if isinstance(expression, list):
        return all(evaluate_expression(item, context) for item in expression)
    if not isinstance(expression, dict):
        return False

    if "all" in expression:
        items = expression["all"] or []
        return all(evaluate_expression(item, context) for item in items)
    if "any" in expression:
        items = expression["any"] or []
        if not items:
            return True
        return any(evaluate_expression(item, context) for item in items)

    if "field" in expression and "operator" in expression:
        return evaluate_predicate(expression, context)

    return False


def expression_from_flat_conditions(conditions: list[WorkflowCondition]) -> dict[str, Any]:
    """Convert legacy flat AND/OR rows into a nested expression."""
    and_preds = []
    or_preds = []
    for cond in conditions:
        pred = {
            "field": cond.field,
            "operator": cond.operator,
            "value": cond.value,
        }
        if cond.logic == "or":
            or_preds.append(pred)
        else:
            and_preds.append(pred)
    if and_preds and or_preds:
        return {"any": [{"all": and_preds}, *or_preds]}
    if or_preds:
        return {"any": or_preds}
    return {"all": and_preds}


def evaluate_step_conditions(step: WorkflowStep, context: dict[str, Any]) -> bool:
    """Prefer config.expression; fall back to legacy WorkflowCondition rows."""
    expression = (step.config or {}).get("expression")
    if expression is not None:
        return evaluate_expression(expression, context)
    conditions = list(step.conditions.all())
    if not conditions:
        return True
    return evaluate_expression(expression_from_flat_conditions(conditions), context)


# Back-compat aliases for NP-210 imports
evaluate_condition = lambda condition, context: evaluate_predicate(  # noqa: E731
    {
        "field": condition.field,
        "operator": condition.operator,
        "value": condition.value,
    },
    context,
)
