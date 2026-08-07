"""Risk ML / dataset enums (NP-221–223)."""

from __future__ import annotations

from django.db import models


class RiskModelStatus(models.TextChoices):
    """NP-223 model lifecycle."""

    TRAINING = "training", "Training"
    CANDIDATE = "candidate", "Candidate"
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retired"
    FAILED = "failed", "Failed"


class RiskAlgorithm(models.TextChoices):
    LOGISTIC_REGRESSION = "logistic_regression", "Logistic Regression"
    GRADIENT_BOOSTING = "gradient_boosting", "Gradient Boosting"
    RANDOM_FOREST = "random_forest", "Random Forest"


# Outcome keys stored in RiskPrediction.actual_outcome
OUTCOME_PAID_WITHIN_30D = "paid_within_30d"
OUTCOME_PAID_WITHIN_60D = "paid_within_60d"
OUTCOME_INVOICE_90PLUS = "invoice_90plus_overdue"

OUTCOME_KEYS = (
    OUTCOME_PAID_WITHIN_30D,
    OUTCOME_PAID_WITHIN_60D,
    OUTCOME_INVOICE_90PLUS,
)

# Days after prediction_date before each label is knowable
OUTCOME_HORIZONS = {
    OUTCOME_PAID_WITHIN_30D: 30,
    OUTCOME_PAID_WITHIN_60D: 60,
    OUTCOME_INVOICE_90PLUS: 90,
}

# Default supervised target for NP-222 (1 = riskier)
DEFAULT_TARGET_LABEL = OUTCOME_INVOICE_90PLUS

# Max outcome horizon used for outcome_date on new predictions
MAX_OUTCOME_HORIZON_DAYS = 90

LEVEL_LABELS_TR = {
    "LOW": "Düşük",
    "MEDIUM": "Orta",
    "HIGH": "Yüksek",
    "CRITICAL": "Kritik",
}
