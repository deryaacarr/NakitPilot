"""Risk model registry: load, score, activate (NP-222 / NP-223)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from django.utils import timezone

from apps.customers.features import FEATURE_NAMES
from apps.risk.enums import RiskModelStatus
from apps.risk.models import RiskModelVersion

logger = logging.getLogger(__name__)


def get_active_model(organization) -> RiskModelVersion | None:
    return (
        RiskModelVersion.objects.filter(
            organization=organization,
            status=RiskModelStatus.ACTIVE,
        )
        .order_by("-published_at", "-id")
        .first()
    )


# Back-compat alias
get_published_model = get_active_model


def publish_model_version(version: RiskModelVersion) -> RiskModelVersion:
    """Mark version ACTIVE; retire previous active models for the org."""
    org = version.organization
    RiskModelVersion.objects.filter(
        organization=org,
        status=RiskModelStatus.ACTIVE,
    ).exclude(pk=version.pk).update(
        status=RiskModelStatus.RETIRED,
        updated_at=timezone.now(),
    )
    version.status = RiskModelStatus.ACTIVE
    version.published_at = timezone.now()
    version.save(update_fields=["status", "published_at", "updated_at"])
    _load_artifact.cache_clear()
    logger.info("activated risk model version=%s org=%s", version.version, org.id)
    return version


def retire_model_version(version: RiskModelVersion) -> RiskModelVersion:
    version.status = RiskModelStatus.RETIRED
    version.save(update_fields=["status", "updated_at"])
    _load_artifact.cache_clear()
    return version


def mark_model_failed(version: RiskModelVersion, *, notes: str = "") -> RiskModelVersion:
    version.status = RiskModelStatus.FAILED
    if notes:
        version.notes = notes
        version.save(update_fields=["status", "notes", "updated_at"])
    else:
        version.save(update_fields=["status", "updated_at"])
    return version


@lru_cache(maxsize=32)
def _load_artifact(version_id: int, artifact_name: str) -> dict[str, Any]:
    import joblib

    version = RiskModelVersion.objects.get(pk=version_id)
    if not version.artifact:
        raise FileNotFoundError(f"Model version {version_id} has no artifact")
    with version.artifact.open("rb") as fh:
        return joblib.load(fh)


def load_model_payload(version: RiskModelVersion) -> dict[str, Any]:
    name = version.artifact.name if version.artifact else ""
    return _load_artifact(version.id, name)


def score_feature_values(
    organization,
    feature_values: dict[str, Any],
) -> tuple[float | None, RiskModelVersion | None]:
    """
    Score a feature dict with the org's active model.

    Returns (model_score 0–100, version) or (None, None).
    """
    version = get_active_model(organization)
    if version is None:
        return None, None
    try:
        payload = load_model_payload(version)
    except Exception:  # pragma: no cover
        logger.exception("Failed to load risk model artifact id=%s", version.id)
        return None, None

    model = payload["model"]
    names = payload.get("feature_names") or version.feature_list_json or list(FEATURE_NAMES)
    row = [[feature_values.get(name) for name in names]]
    try:
        proba = float(model.predict_proba(row)[0][1])
    except Exception:  # pragma: no cover
        logger.exception("Model scoring failed id=%s", version.id)
        return None, None

    score = max(0.0, min(100.0, proba * 100.0))
    return score, version


def blend_scores(rule_score: int, model_score: float | None, *, weight: float = 0.5) -> int:
    """Combine rule and model scores into final_score."""
    if model_score is None:
        return int(rule_score)
    w = max(0.0, min(1.0, weight))
    blended = (1.0 - w) * float(rule_score) + w * float(model_score)
    return int(max(0, min(100, round(blended))))
