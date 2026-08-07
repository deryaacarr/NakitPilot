"""NP-226 model accuracy / monitoring metrics."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from apps.risk.enums import DEFAULT_TARGET_LABEL, OUTCOME_PAID_WITHIN_30D
from apps.risk.models import RiskPrediction, RiskSnapshot
from apps.risk.outcomes import risk_label_from_outcome
from apps.risk.rules import risk_level_for_score

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _expected_calibration_error(y_true: list[int], y_prob: list[float], *, n_bins: int = 10) -> float:
    """ECE — mean absolute gap between bin confidence and accuracy."""
    if not y_true:
        return 0.0
    bins: list[list[tuple[int, float]]] = [[] for _ in range(n_bins)]
    for yt, yp in zip(y_true, y_prob, strict=True):
        idx = min(n_bins - 1, max(0, int(yp * n_bins)))
        bins[idx].append((yt, yp))
    total = len(y_true)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        acc = sum(t for t, _ in bucket) / len(bucket)
        conf = sum(p for _, p in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(acc - conf)
    return float(ece)


def _sklearn_classification_metrics(
    y_true: list[int], y_prob: list[float], *, threshold: float = 0.5
) -> dict[str, float | None]:
    try:
        from sklearn.metrics import (
            precision_score,
            recall_score,
            roc_auc_score,
        )
    except ImportError:  # pragma: no cover
        return {
            "precision": None,
            "recall": None,
            "roc_auc": None,
            "calibration_error": _expected_calibration_error(y_true, y_prob),
        }

    if len(y_true) < 2 or len(set(y_true)) < 2:
        return {
            "precision": None,
            "recall": None,
            "roc_auc": None,
            "calibration_error": _expected_calibration_error(y_true, y_prob),
        }

    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "calibration_error": _expected_calibration_error(y_true, y_prob),
    }


def _labeled_prediction_rows(
    organization,
    *,
    target_label: str = DEFAULT_TARGET_LABEL,
    since: date | None = None,
    limit: int = 20_000,
) -> list[dict[str, Any]]:
    qs = RiskPrediction.objects.filter(
        organization=organization,
        outcomes_resolved_at__isnull=False,
        actual_outcome__isnull=False,
    ).order_by("-prediction_date", "-id")
    if since is not None:
        qs = qs.filter(prediction_date__gte=since)
    rows: list[dict[str, Any]] = []
    for pred in qs[:limit]:
        label = risk_label_from_outcome(pred.actual_outcome or {}, target_label=target_label)
        if label is None:
            continue
        score = pred.model_score if pred.model_score is not None else float(pred.final_score)
        prob = max(0.0, min(1.0, float(score) / 100.0))
        paid_30 = (pred.actual_outcome or {}).get(OUTCOME_PAID_WITHIN_30D)
        rows.append(
            {
                "id": pred.id,
                "y_true": label,
                "y_prob": prob,
                "final_score": pred.final_score,
                "level": risk_level_for_score(int(pred.final_score)),
                "paid_within_30d": paid_30,
                "maximum_overdue_days": _safe_float(
                    (pred.feature_values or {}).get("maximum_overdue_days")
                ),
            }
        )
    return rows


def predicted_vs_actual_collection(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    High-risk predictions (score ≥ 50) vs whether payment landed within 30d.

    ``predicted_collection`` = score < 50 (model expects payment / lower risk)
    ``actual_collection`` = paid_within_30d is True
    """
    predicted_yes = 0
    predicted_no = 0
    actual_yes = 0
    actual_no = 0
    both_yes = 0
    known = 0
    for row in rows:
        paid = row.get("paid_within_30d")
        if paid is None:
            continue
        known += 1
        pred_collect = int(row["final_score"]) < 50
        if pred_collect:
            predicted_yes += 1
        else:
            predicted_no += 1
        if paid:
            actual_yes += 1
        else:
            actual_no += 1
        if pred_collect and paid:
            both_yes += 1
    return {
        "n": known,
        "predicted_collection": predicted_yes,
        "predicted_no_collection": predicted_no,
        "actual_collection": actual_yes,
        "actual_no_collection": actual_no,
        "predicted_and_actual_collection": both_yes,
        "collection_hit_rate": (both_yes / predicted_yes) if predicted_yes else None,
    }


def delay_rate_by_risk_level(organization, *, days: int = 90) -> list[dict[str, Any]]:
    """Share of snapshots per risk level whose customer had overdue delay > 0 at calc time."""
    since = timezone.now() - timedelta(days=days)
    qs = (
        RiskSnapshot.objects.filter(organization=organization, calculated_at__gte=since)
        .order_by("-calculated_at")
        .only("risk_level", "score_details", "score")[:5000]
    )
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "with_delay": 0})
    for snap in qs:
        level = snap.risk_level or risk_level_for_score(snap.score)
        meta = (snap.score_details or {}).get("meta") or {}
        days_over = meta.get("max_overdue_days")
        buckets[level]["count"] += 1
        if days_over is not None and int(days_over) > 0:
            buckets[level]["with_delay"] += 1
        elif (snap.score_details or {}).get("reasons"):
            # Fallback: any OVERDUE reason
            if any(
                str(r.get("code", "")).startswith("OVERDUE")
                for r in (snap.score_details or {}).get("reasons", [])
            ):
                buckets[level]["with_delay"] += 1

    order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    out = []
    for level in order:
        data = buckets.get(level) or {"count": 0, "with_delay": 0}
        count = data["count"]
        with_delay = data["with_delay"]
        out.append(
            {
                "risk_level": level,
                "n": count,
                "with_delay": with_delay,
                "delay_rate": (with_delay / count) if count else None,
            }
        )
    return out


def build_monitoring_dashboard(
    organization,
    *,
    include_technical: bool = False,
    target_label: str = DEFAULT_TARGET_LABEL,
    lookback_days: int = 180,
) -> dict[str, Any]:
    """
    NP-226 dashboard payload.

    Business metrics always included; technical metrics only when
    ``include_technical`` (admin / MANAGE_SETTINGS).
    """
    since = timezone.localdate() - timedelta(days=lookback_days)
    rows = _labeled_prediction_rows(
        organization, target_label=target_label, since=since
    )
    y_true = [r["y_true"] for r in rows]
    y_prob = [r["y_prob"] for r in rows]

    payload: dict[str, Any] = {
        "lookback_days": lookback_days,
        "n_labeled": len(rows),
        "target_label": target_label,
        "business": {
            "predicted_vs_actual_collection": predicted_vs_actual_collection(rows),
            "delay_rate_by_risk_level": delay_rate_by_risk_level(
                organization, days=min(lookback_days, 90)
            ),
        },
        "technical": None,
    }

    if include_technical:
        tech = _sklearn_classification_metrics(y_true, y_prob)
        payload["technical"] = {
            "precision": tech["precision"],
            "recall": tech["recall"],
            "roc_auc": tech["roc_auc"],
            "calibration_error": tech["calibration_error"],
            "n": len(rows),
        }

    return payload
