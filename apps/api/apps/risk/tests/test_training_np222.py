"""NP-222 model training pipeline + registry."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.customers.models import Customer
from apps.organizations.models import Organization
from apps.risk.enums import RiskAlgorithm, RiskModelStatus
from apps.risk.models import RiskModelVersion
from apps.risk.registry import blend_scores, publish_model_version, score_feature_values
from apps.risk.services import calculate_customer_risk
from apps.risk.training import MIN_LABELED_ROWS, run_training_pipeline, train_synthetic_smoke


@pytest.fixture
def org_with_customer(db):
    org = Organization.objects.create(name="ML Co", slug="ml-co")
    customer = Customer.objects.create(
        organization=org,
        name="Trainee",
        code="ML-1",
        credit_limit=Decimal("1000.00"),
        last_contact_at=timezone.now(),
    )
    return org, customer


@pytest.mark.django_db
def test_blend_scores():
    assert blend_scores(80, None) == 80
    assert blend_scores(0, 100.0, weight=0.5) == 50
    assert blend_scores(100, 0.0, weight=0.5) == 50


@pytest.mark.django_db
def test_training_pipeline_synthetic_and_publish(org_with_customer):
    pytest.importorskip("sklearn")
    org, _customer = org_with_customer

    result = train_synthetic_smoke(org, n_samples=max(MIN_LABELED_ROWS, 40), publish=True)
    assert result["n_rows"] >= MIN_LABELED_ROWS
    assert result["algorithm"] in {c.value for c in RiskAlgorithm}
    assert "comparison" in result
    assert set(result["comparison"].keys()) >= {
        RiskAlgorithm.LOGISTIC_REGRESSION,
        RiskAlgorithm.GRADIENT_BOOSTING,
        RiskAlgorithm.RANDOM_FOREST,
    }

    version = RiskModelVersion.objects.get(pk=result["model_version_id"])
    assert version.status == RiskModelStatus.ACTIVE
    assert version.artifact
    assert version.metrics_json.get("roc_auc") is not None
    assert version.training_data_range.get("n_rows") >= MIN_LABELED_ROWS
    assert version.feature_list_json


@pytest.mark.django_db
def test_published_model_used_in_risk_calc(org_with_customer):
    pytest.importorskip("sklearn")
    org, customer = org_with_customer

    train_synthetic_smoke(org, n_samples=50, publish=True)
    result = calculate_customer_risk(customer.pk)

    assert result["model_score"] is not None
    assert 0 <= result["model_score"] <= 100
    assert result["final_score"] == blend_scores(
        result["rule_score"], result["model_score"]
    )


@pytest.mark.django_db
def test_publish_retires_previous(org_with_customer):
    pytest.importorskip("sklearn")
    org, _ = org_with_customer

    first = train_synthetic_smoke(org, n_samples=40, publish=True)
    second = run_training_pipeline(org, publish=False)
    v2 = RiskModelVersion.objects.get(pk=second["model_version_id"])
    publish_model_version(v2)

    v1 = RiskModelVersion.objects.get(pk=first["model_version_id"])
    v1.refresh_from_db()
    v2.refresh_from_db()
    assert v1.status == RiskModelStatus.RETIRED
    assert v2.status == RiskModelStatus.ACTIVE

    score, active = score_feature_values(
        org, {"overdue_balance": 500, "maximum_overdue_days": 40}
    )
    assert active is not None
    assert active.id == v2.id
    assert score is not None
