"""Back-compat re-exports — prefer condition_engine (NP-212)."""

from apps.workflows.condition_engine import (  # noqa: F401
    evaluate_condition,
    evaluate_expression,
    evaluate_predicate,
    evaluate_step_conditions,
    normalize_operator,
    resolve_context_value,
)
