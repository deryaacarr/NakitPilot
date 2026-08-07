"""NP-226 monitoring dashboard tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.customers.models import Customer, RiskStatus
from apps.organizations.models import Organization
from apps.risk.dataset import record_risk_prediction
from apps.risk.enums import (
    OUTCOME_INVOICE_90PLUS,
    OUTCOME_PAID_WITHIN_30D,
    OUTCOME_PAID_WITHIN_60D,
)
from apps.risk.models import RiskSnapshot
from apps.risk.monitoring import build_monitoring_dashboard, delay_rate_by_risk_level


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Mon Co", slug="mon-co")
    customer = Customer.objects.create(
        organization=org,
        name="Mon",
        code="M-1",
        last_contact_at=timezone.now(),
    )
    return org, customer


def _seed_labeled(org, customer, *, n=30):
    today = timezone.localdate()
    for i in range(n):
        score = 20 + (i % 70)
        adverse = score >= 50
        pred = record_risk_prediction(
            customer=customer,
            snapshot=None,
            feature_values={"maximum_overdue_days": score},
            rule_score=score,
            model_score=float(score),
            final_score=score,
            prediction_date=today - timedelta(days=100 + i),
        )
        pred.actual_outcome = {
            OUTCOME_PAID_WITHIN_30D: not adverse,
            OUTCOME_PAID_WITHIN_60D: not adverse,
            OUTCOME_INVOICE_90PLUS: adverse and score >= 70,
        }
        pred.outcomes_resolved_at = timezone.now()
        pred.save(update_fields=["actual_outcome", "outcomes_resolved_at"])


@pytest.mark.django_db
def test_monitoring_business_and_technical(org_customer):
    org, customer = org_customer
    _seed_labeled(org, customer, n=40)

    business_only = build_monitoring_dashboard(org, include_technical=False)
    assert business_only["technical"] is None
    assert "predicted_vs_actual_collection" in business_only["business"]
    assert "delay_rate_by_risk_level" in business_only["business"]
    assert business_only["n_labeled"] >= 20

    full = build_monitoring_dashboard(org, include_technical=True)
    tech = full["technical"]
    assert tech is not None
    assert "precision" in tech
    assert "recall" in tech
    assert "roc_auc" in tech
    assert "calibration_error" in tech


@pytest.mark.django_db
def test_delay_rate_by_risk_level(org_customer):
    org, customer = org_customer
    RiskSnapshot.objects.create(
        organization=org,
        customer=customer,
        score=80,
        risk_level=RiskStatus.CRITICAL,
        score_details={"meta": {"max_overdue_days": 95}, "reasons": []},
    )
    RiskSnapshot.objects.create(
        organization=org,
        customer=customer,
        score=10,
        risk_level=RiskStatus.LOW,
        score_details={"meta": {"max_overdue_days": 0}, "reasons": []},
    )
    rows = delay_rate_by_risk_level(org, days=30)
    by_level = {r["risk_level"]: r for r in rows}
    assert by_level["CRITICAL"]["delay_rate"] == 1.0
    assert by_level["LOW"]["delay_rate"] == 0.0
