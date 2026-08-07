"""NP-227 risk scoring fallback: ML → rules → simple overdue."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from django.utils import timezone

from apps.customers.features import extract_customer_features
from apps.customers.metrics import customer_financial_metrics
from apps.risk.registry import blend_scores, score_feature_values
from apps.risk.rules import clamp_score, compute_customer_risk_score, risk_level_for_score

logger = logging.getLogger(__name__)

SOURCE_ML = "ml"
SOURCE_RULES = "rules"
SOURCE_SIMPLE = "simple_overdue"


def simple_overdue_risk(
    customer,
    *,
    as_of: date | None = None,
) -> tuple[int, str, dict[str, Any]]:
    """
    Minimal delay-based score when rules and ML both fail.

    Uses oldest open overdue days only.
    """
    today = as_of or timezone.localdate()
    try:
        metrics = customer_financial_metrics(customer)
        days = int(metrics.get("oldest_overdue_days") or 0)
    except Exception:  # pragma: no cover
        logger.exception("simple_overdue_risk metrics failed customer=%s", customer.pk)
        days = 0

    if days <= 0:
        score = 10
        label = "Açık gecikme yok"
    elif days <= 15:
        score = 30
        label = f"{days} gün gecikme"
    elif days <= 30:
        score = 45
        label = f"{days} gün gecikme"
    elif days <= 60:
        score = 60
        label = f"{days} gün gecikme"
    elif days <= 90:
        score = 75
        label = f"{days} gün gecikme"
    else:
        score = 90
        label = f"{days} gün gecikme"

    score = clamp_score(score)
    level = risk_level_for_score(score)
    details = {
        "score": score,
        "level": level,
        "reasons": [
            {
                "code": "SIMPLE_OVERDUE",
                "label": label,
                "points": score,
            }
        ],
        "meta": {
            "oldest_overdue_days": days,
            "as_of": today.isoformat(),
            "engine": SOURCE_SIMPLE,
        },
    }
    return score, level, details


def resolve_risk_with_fallback(
    customer,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    NP-227 cascade:

    1. Active ML model score (if available)
    2. Rule engine
    3. Simple overdue heuristic

    Never raises for scoring failures — always returns a score.
    When ML succeeds, final score blends with rules if rules also succeeded;
    otherwise uses the first available layer.
    """
    today = as_of or timezone.localdate()
    feature_values: dict[str, Any] = {}
    try:
        feature_values = extract_customer_features(customer, as_of=today)["features"]
    except Exception:
        logger.exception("feature extraction failed customer=%s", customer.pk)
        feature_values = {}

    model_score: float | None = None
    model_version = None
    ml_ok = False
    try:
        model_score, model_version = score_feature_values(
            customer.organization, feature_values
        )
        ml_ok = model_score is not None
    except Exception:
        logger.exception("ML scoring failed customer=%s", customer.pk)
        model_score, model_version = None, None
        ml_ok = False

    rule_score: int | None = None
    rule_details: dict[str, Any] = {"reasons": [], "meta": {}}
    rules_ok = False
    try:
        rule_score, _level, rule_details = compute_customer_risk_score(
            customer, as_of=today
        )
        rules_ok = True
    except Exception:
        logger.exception("rule engine failed customer=%s", customer.pk)
        rule_score = None
        rules_ok = False
        rule_details = {"reasons": [], "meta": {"engine_error": True}}

    source = SOURCE_SIMPLE
    if ml_ok and rules_ok:
        final_score = blend_scores(int(rule_score), model_score)
        source = SOURCE_ML
        details = rule_details
    elif ml_ok:
        final_score = clamp_score(int(round(float(model_score))))
        source = SOURCE_ML
        details = {
            "reasons": [
                {
                    "code": "ML_SCORE",
                    "label": "Aktif ML modeli",
                    "points": final_score,
                }
            ],
            "meta": {"engine": SOURCE_ML},
        }
    elif rules_ok:
        final_score = int(rule_score)
        source = SOURCE_RULES
        details = rule_details
    else:
        final_score, _level, details = simple_overdue_risk(customer, as_of=today)
        source = SOURCE_SIMPLE
        rule_score = final_score

    level = risk_level_for_score(final_score)
    return {
        "score": final_score,
        "level": level,
        "rule_score": int(rule_score) if rule_score is not None else final_score,
        "model_score": model_score,
        "model_version": model_version,
        "feature_values": feature_values,
        "details": details,
        "source": source,
        "fallback_chain": {
            "ml": ml_ok,
            "rules": rules_ok,
            "simple_overdue": source == SOURCE_SIMPLE or (not ml_ok and not rules_ok),
            "selected": source,
        },
    }
