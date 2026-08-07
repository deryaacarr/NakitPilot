"""Risk prediction dataset helpers (NP-221)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.customers.features import FEATURE_NAMES, extract_customer_features
from apps.risk.enums import DEFAULT_TARGET_LABEL
from apps.risk.models import RiskPrediction, RiskSnapshot
from apps.risk.outcomes import (
    compute_actual_outcome,
    outcome_date_for_prediction,
    outcomes_fully_resolved,
    risk_label_from_outcome,
)

logger = logging.getLogger(__name__)


def record_risk_prediction(
    *,
    customer,
    snapshot: RiskSnapshot | None,
    feature_values: dict[str, Any],
    rule_score: int,
    model_score: float | None,
    final_score: int,
    prediction_date: date,
    model_version=None,
    resolve_if_ready: bool = False,
) -> RiskPrediction:
    """Persist one NP-221 dataset row for a risk calculation."""
    as_of = prediction_date
    outcome = None
    resolved_at = None
    if resolve_if_ready:
        outcome = compute_actual_outcome(customer, prediction_date, as_of=as_of)
        if outcomes_fully_resolved(outcome):
            resolved_at = timezone.now()
        else:
            # partial — keep null until fully known
            outcome = None

    return RiskPrediction.objects.create(
        organization=customer.organization,
        customer=customer,
        snapshot=snapshot,
        feature_values=feature_values or {},
        rule_score=rule_score,
        model_score=model_score,
        final_score=final_score,
        prediction_date=prediction_date,
        outcome_date=outcome_date_for_prediction(prediction_date),
        actual_outcome=outcome,
        model_version=model_version,
        outcomes_resolved_at=resolved_at,
    )


def resolve_pending_outcomes(
    *,
    organization_id: int | None = None,
    as_of: date | None = None,
    limit: int = 5000,
) -> dict[str, int]:
    """Backfill actual_outcome once outcome horizons have elapsed."""
    as_of = as_of or timezone.localdate()
    qs = RiskPrediction.objects.filter(
        Q(outcomes_resolved_at__isnull=True) | Q(actual_outcome__isnull=True)
    ).select_related("customer")
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)
    qs = qs.filter(outcome_date__lte=as_of).order_by("id")[:limit]

    resolved = 0
    skipped = 0
    for pred in qs:
        outcome = compute_actual_outcome(
            pred.customer, pred.prediction_date, as_of=as_of
        )
        if not outcomes_fully_resolved(outcome):
            skipped += 1
            continue
        pred.actual_outcome = outcome
        pred.outcomes_resolved_at = timezone.now()
        pred.save(
            update_fields=["actual_outcome", "outcomes_resolved_at"]
        )
        resolved += 1

    logger.info(
        "resolve_pending_outcomes resolved=%s skipped=%s as_of=%s",
        resolved,
        skipped,
        as_of,
    )
    return {"resolved": resolved, "skipped": skipped}


def extract_labeled_rows(
    organization,
    *,
    target_label: str = DEFAULT_TARGET_LABEL,
    limit: int = 50_000,
) -> list[dict[str, Any]]:
    """
    Return training rows with feature_values + binary label.

    Only predictions with fully resolved outcomes are included.
    """
    qs = (
        RiskPrediction.objects.filter(
            organization=organization,
            outcomes_resolved_at__isnull=False,
            actual_outcome__isnull=False,
        )
        .order_by("prediction_date", "id")[:limit]
    )
    rows: list[dict[str, Any]] = []
    for pred in qs.iterator(chunk_size=500):
        label = risk_label_from_outcome(pred.actual_outcome or {}, target_label=target_label)
        if label is None:
            continue
        features = {name: (pred.feature_values or {}).get(name) for name in FEATURE_NAMES}
        rows.append(
            {
                "prediction_id": pred.id,
                "customer_id": pred.customer_id,
                "prediction_date": pred.prediction_date.isoformat(),
                "features": features,
                "label": label,
                "rule_score": pred.rule_score,
                "final_score": pred.final_score,
            }
        )
    return rows


def backfill_features_for_organization(
    organization,
    *,
    as_of: date | None = None,
    limit: int = 500,
) -> dict[str, int]:
    """
    Create dataset rows from a one-shot feature extraction pass without
    changing customer.risk_score (useful to seed the training set).
    """
    from apps.customers.models import Customer
    from apps.risk.rules import compute_customer_risk_score

    as_of = as_of or timezone.localdate()
    created = 0
    customers = Customer.objects.filter(organization=organization, is_active=True).order_by("id")[
        :limit
    ]
    for customer in customers:
        feat = extract_customer_features(customer, as_of=as_of)
        score, _level, _details = compute_customer_risk_score(customer, as_of=as_of)
        record_risk_prediction(
            customer=customer,
            snapshot=None,
            feature_values=feat["features"],
            rule_score=score,
            model_score=None,
            final_score=score,
            prediction_date=as_of,
            model_version=None,
        )
        created += 1
    return {"created": created}
