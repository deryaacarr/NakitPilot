"""Model training pipeline (NP-222).

Pipeline: extract → clean → train/val → train → calibrate → evaluate → registry → publish.
Compares Logistic Regression, Gradient Boosting, and Random Forest.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.customers.features import FEATURE_NAMES
from apps.risk.dataset import extract_labeled_rows
from apps.risk.enums import (
    DEFAULT_TARGET_LABEL,
    MAX_OUTCOME_HORIZON_DAYS,
    RiskAlgorithm,
    RiskModelStatus,
)
from apps.risk.models import RiskModelVersion

logger = logging.getLogger(__name__)

MIN_LABELED_ROWS = 20
DEFAULT_TEST_SIZE = 0.25
RANDOM_STATE = 42


def _require_sklearn():
    try:
        import joblib  # noqa: F401
        import numpy as np  # noqa: F401
        from sklearn.calibration import CalibratedClassifierCV  # noqa: F401
        from sklearn.ensemble import (  # noqa: F401
            GradientBoostingClassifier,
            RandomForestClassifier,
        )
        from sklearn.impute import SimpleImputer  # noqa: F401
        from sklearn.linear_model import LogisticRegression  # noqa: F401
        from sklearn.metrics import (  # noqa: F401
            accuracy_score,
            average_precision_score,
            brier_score_loss,
            roc_auc_score,
        )
        from sklearn.model_selection import train_test_split  # noqa: F401
        from sklearn.pipeline import Pipeline  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "scikit-learn and joblib are required for risk model training. "
            "Install apps/api requirements."
        ) from exc


def _matrix_from_rows(rows: list[dict[str, Any]]):
    import numpy as np

    feature_names = list(FEATURE_NAMES)
    x = np.array(
        [[row["features"].get(name) for name in feature_names] for row in rows],
        dtype=float,
    )
    y = np.array([row["label"] for row in rows], dtype=int)
    return x, y, feature_names


def _build_estimators() -> dict[str, Any]:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression

    return {
        RiskAlgorithm.LOGISTIC_REGRESSION: LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        RiskAlgorithm.GRADIENT_BOOSTING: GradientBoostingClassifier(
            random_state=RANDOM_STATE,
        ),
        RiskAlgorithm.RANDOM_FOREST: RandomForestClassifier(
            n_estimators=100,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


def _metrics(y_true, y_prob, y_pred) -> dict[str, float]:
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        brier_score_loss,
        roc_auc_score,
    )

    out: dict[str, float] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "brier": float(brier_score_loss(y_true, y_prob)),
    }
    # ROC-AUC needs both classes present
    if len(set(int(v) for v in y_true)) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
        out["average_precision"] = float(average_precision_score(y_true, y_prob))
    else:
        out["roc_auc"] = 0.0
        out["average_precision"] = 0.0
    return out


def _train_and_calibrate(estimator, x_train, y_train, x_val, y_val) -> tuple[Any, dict]:
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    base = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("clf", estimator),
        ]
    )
    n_train = len(y_train)
    n_classes = len(set(int(v) for v in y_train))
    # sklearn>=1.6: prefer CV calibration; fall back to uncalibrated pipeline
    if n_train >= 30 and n_classes > 1:
        cv = 3 if n_train >= 45 else 2
        model = CalibratedClassifierCV(base, method="sigmoid", cv=cv)
        model.fit(x_train, y_train)
    else:
        model = base
        model.fit(x_train, y_train)

    y_prob = model.predict_proba(x_val)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    return model, _metrics(y_val, y_prob, y_pred)


def clean_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop rows with empty feature dicts; keep None features for imputer."""
    cleaned = []
    for row in rows:
        feats = row.get("features") or {}
        if not feats:
            continue
        if row.get("label") not in (0, 1):
            continue
        cleaned.append(row)
    return cleaned


def run_training_pipeline(
    organization,
    *,
    target_label: str = DEFAULT_TARGET_LABEL,
    name: str | None = None,
    publish: bool = False,
    test_size: float = DEFAULT_TEST_SIZE,
) -> dict[str, Any]:
    """
    Full NP-222 pipeline for one organization.

    Returns summary with comparison metrics and registry version id.
    """
    _require_sklearn()
    from sklearn.model_selection import train_test_split

    raw = extract_labeled_rows(organization, target_label=target_label)
    rows = clean_rows(raw)
    if len(rows) < MIN_LABELED_ROWS:
        failed = RiskModelVersion.objects.create(
            organization=organization,
            name=name or f"risk-{slugify(organization.slug) or 'org'}-failed",
            version=f"v{timezone.now().strftime('%Y%m%d%H%M%S')}-failed",
            algorithm=RiskAlgorithm.LOGISTIC_REGRESSION,
            target_label=target_label,
            status=RiskModelStatus.FAILED,
            notes=f"Need at least {MIN_LABELED_ROWS} labeled rows; got {len(rows)}.",
            trained_at=timezone.now(),
        )
        raise ValueError(
            f"Need at least {MIN_LABELED_ROWS} labeled rows; got {len(rows)} "
            f"(failed version id={failed.id})."
        )

    dates = [r["prediction_date"] for r in rows if r.get("prediction_date")]
    training_data_range = {
        "from": min(dates) if dates else None,
        "to": max(dates) if dates else None,
        "n_rows": len(rows),
    }

    x, y, feature_names = _matrix_from_rows(rows)
    # Stratify when both classes exist
    stratify = y if len(set(int(v) for v in y)) > 1 else None
    x_train, x_val, y_train, y_val = train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=RANDOM_STATE,
        stratify=stratify,
    )

    comparison: dict[str, Any] = {}
    best_key: str | None = None
    best_auc = -1.0
    best_model = None

    for algo_key, estimator in _build_estimators().items():
        model, metrics = _train_and_calibrate(
            estimator, x_train, y_train, x_val, y_val
        )
        comparison[algo_key] = {
            "algorithm": algo_key,
            "metrics": metrics,
            "n_train": int(len(y_train)),
            "n_val": int(len(y_val)),
        }
        auc = metrics.get("roc_auc", 0.0)
        if auc > best_auc:
            best_auc = auc
            best_key = algo_key
            best_model = model

    if best_key is None or best_model is None:
        raise RuntimeError("Training produced no usable model.")

    # Refit winning algorithm on full cleaned data for the artifact
    full_estimator = _build_estimators()[best_key]
    final_model, full_metrics = _train_and_calibrate(
        full_estimator, x_train, y_train, x_val, y_val
    )
    # Prefer comparison val metrics for the winner; keep full_metrics as refit note
    winner_metrics = {
        **comparison[best_key]["metrics"],
        "refit_val": full_metrics,
        "n_rows": len(rows),
        "target_label": target_label,
        "positive_rate": float(sum(int(v) for v in y) / len(y)),
    }

    stamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    version_code = f"v{stamp}"
    model_name = name or f"risk-{slugify(organization.slug) or 'org'}-{best_key}"

    import joblib

    payload = {
        "model": final_model,
        "feature_names": feature_names,
        "algorithm": best_key,
        "target_label": target_label,
        "trained_at": timezone.now().isoformat(),
    }
    buf = io.BytesIO()
    joblib.dump(payload, buf)
    buf.seek(0)

    with transaction.atomic():
        version = RiskModelVersion.objects.create(
            organization=organization,
            name=model_name,
            version=version_code,
            algorithm=best_key,
            target_label=target_label,
            training_data_range=training_data_range,
            feature_list_json=feature_names,
            metrics_json=winner_metrics,
            comparison=comparison,
            status=RiskModelStatus.CANDIDATE,
            trained_at=timezone.now(),
            notes=f"Best of {', '.join(comparison.keys())} by roc_auc",
        )
        version.artifact.save(
            f"{organization_id_safe(organization)}_{version_code}.joblib",
            ContentFile(buf.read()),
            save=True,
        )

    result = {
        "model_version_id": version.id,
        "version": version.version,
        "algorithm": best_key,
        "metrics_json": winner_metrics,
        "metrics": winner_metrics,
        "comparison": comparison,
        "training_data_range": training_data_range,
        "feature_list_json": feature_names,
        "status": version.status,
        "n_rows": len(rows),
    }

    if publish:
        from apps.risk.registry import publish_model_version

        publish_model_version(version)
        version.refresh_from_db()
        result["status"] = version.status

    logger.info(
        "train_risk_model org=%s version=%s algo=%s auc=%s",
        organization.id,
        version.version,
        best_key,
        winner_metrics.get("roc_auc"),
    )
    return result


def organization_id_safe(organization) -> str:
    return str(organization.id)


def train_synthetic_smoke(
    organization,
    *,
    n_samples: int = 80,
    publish: bool = False,
) -> dict[str, Any]:
    """
    Seed labeled predictions from a synthetic feature matrix and train.

    Intended for CI / empty orgs — not for production scoring quality.
    """
    import random
    from datetime import timedelta

    from apps.customers.models import Customer
    from apps.risk.dataset import record_risk_prediction

    rng = random.Random(RANDOM_STATE)
    as_of = timezone.localdate() - timedelta(days=MAX_OUTCOME_HORIZON_DAYS)
    customers = list(
        Customer.objects.filter(organization=organization, is_active=True).order_by("id")[:20]
    )
    if not customers:
        raise ValueError("Organization has no customers for synthetic training.")

    from apps.risk.enums import (
        OUTCOME_INVOICE_90PLUS,
        OUTCOME_PAID_WITHIN_30D,
        OUTCOME_PAID_WITHIN_60D,
    )

    created = 0
    for i in range(n_samples):
        customer = customers[i % len(customers)]
        overdue = rng.uniform(0, 120)
        features = {name: 0.0 for name in FEATURE_NAMES}
        features["overdue_invoice_count"] = int(overdue / 30)
        features["maximum_overdue_days"] = overdue
        features["overdue_balance"] = overdue * 100
        features["on_time_payment_ratio"] = max(0.0, 1.0 - overdue / 120)
        features["broken_promise_count"] = 1 if overdue > 60 else 0
        features["payment_frequency"] = max(0.1, 2.0 - overdue / 60)
        features["average_payment_delay"] = overdue / 2
        features["median_payment_delay"] = overdue / 2
        features["open_invoice_count"] = max(1, int(overdue / 40))
        features["fulfilled_promise_ratio"] = max(0.0, 1.0 - overdue / 150)
        features["last_payment_days_ago"] = overdue
        features["contact_success_ratio"] = max(0.1, 1.0 - overdue / 200)
        features["average_days_between_contacts"] = 7.0
        features["credit_utilization_ratio"] = min(1.5, overdue / 80)
        features["invoice_amount_variance"] = overdue * 10
        label_adverse = overdue > 45
        # Align default target (invoice_90plus) with synthetic signal
        hit_90 = overdue > 90
        pred_date = as_of - timedelta(days=rng.randint(0, 10))
        outcome = {
            OUTCOME_PAID_WITHIN_30D: not label_adverse,
            OUTCOME_PAID_WITHIN_60D: not label_adverse or rng.random() > 0.3,
            OUTCOME_INVOICE_90PLUS: hit_90,
        }
        pred = record_risk_prediction(
            customer=customer,
            snapshot=None,
            feature_values=features,
            rule_score=min(100, int(overdue)),
            model_score=None,
            final_score=min(100, int(overdue)),
            prediction_date=pred_date,
        )
        pred.actual_outcome = outcome
        pred.outcomes_resolved_at = timezone.now()
        pred.save(update_fields=["actual_outcome", "outcomes_resolved_at"])
        created += 1

    result = run_training_pipeline(organization, publish=publish)
    result["synthetic_rows"] = created
    return result
