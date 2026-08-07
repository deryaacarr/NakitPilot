"""Risk calculation service (NP-100–104, NP-221, NP-227 fallback)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from apps.customers.models import Customer
from apps.risk.dataset import record_risk_prediction
from apps.risk.explain import build_risk_explanation
from apps.risk.fallback import resolve_risk_with_fallback
from apps.risk.models import RiskSnapshot
from apps.risk.rules import risk_level_for_score

HISTORY_RANGES = {
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "12m": timedelta(days=365),
}


def calculate_customer_risk(
    customer_id: int,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """NP-102 / NP-221 / NP-227: compute with fallback, persist snapshot + prediction."""
    customer = Customer.objects.select_related("organization").get(pk=customer_id)
    prediction_date = as_of or timezone.localdate()

    resolved = resolve_risk_with_fallback(customer, as_of=prediction_date)
    final_score = resolved["score"]
    level = resolved["level"]
    rule_score = resolved["rule_score"]
    model_score = resolved["model_score"]
    model_version = resolved["model_version"]
    feature_values = resolved["feature_values"]
    details = {
        **resolved["details"],
        "score": final_score,
        "level": level,
        "rule_score": rule_score,
        "model_score": model_score,
        "model_version": model_version.version if model_version else None,
        "source": resolved["source"],
        "fallback_chain": resolved["fallback_chain"],
    }
    explanation = build_risk_explanation(
        customer,
        as_of=prediction_date,
        score=final_score,
        level=level,
        reasons=details.get("reasons"),
        meta=details.get("meta"),
        features=feature_values,
    )
    details["explanation"] = explanation

    snapshot = RiskSnapshot.objects.create(
        organization=customer.organization,
        customer=customer,
        score=final_score,
        risk_level=level,
        score_details=details,
    )
    prediction = record_risk_prediction(
        customer=customer,
        snapshot=snapshot,
        feature_values=feature_values,
        rule_score=rule_score,
        model_score=model_score,
        final_score=final_score,
        prediction_date=prediction_date,
        model_version=model_version,
    )

    customer.risk_score = final_score
    customer.risk_status = level
    customer.save(update_fields=["risk_score", "risk_status", "updated_at"])
    return {
        "score": final_score,
        "level": level,
        "reasons": details.get("reasons", []),
        "explanation": explanation,
        "rule_score": rule_score,
        "model_score": model_score,
        "final_score": final_score,
        "prediction_id": prediction.id,
        "source": resolved["source"],
        "fallback_chain": resolved["fallback_chain"],
    }


def customer_risk_history(
    customer_id: int,
    *,
    range_key: str = "30d",
) -> dict[str, Any]:
    """NP-104: score time series for chart (30d / 90d / 12m)."""
    if range_key not in HISTORY_RANGES:
        raise ValueError(f"Invalid range: {range_key}")
    since = timezone.now() - HISTORY_RANGES[range_key]
    snapshots = (
        RiskSnapshot.objects.filter(customer_id=customer_id, calculated_at__gte=since)
        .order_by("calculated_at", "id")
        .only("score", "risk_level", "calculated_at", "score_details")
    )
    points = [
        {
            "score": snap.score,
            "level": snap.risk_level,
            "at": snap.calculated_at.isoformat().replace("+00:00", "Z"),
            "reasons": (snap.score_details or {}).get("reasons", []),
        }
        for snap in snapshots
    ]
    return {"range": range_key, "points": points}


def recalculate_customer_risk(
    customer: Customer,
    *,
    as_of: date | None = None,
) -> RiskSnapshot:
    """Apply rules for a Customer instance; return latest RiskSnapshot."""
    calculate_customer_risk(customer.pk, as_of=as_of)
    snap = (
        RiskSnapshot.objects.filter(customer_id=customer.pk)
        .order_by("-calculated_at", "-id")
        .first()
    )
    if snap is None:  # pragma: no cover
        raise RuntimeError("RiskSnapshot missing after calculate_customer_risk")
    return snap


def _level_for_score(score: int) -> str:
    """Back-compat alias."""
    return risk_level_for_score(score)
