"""NP-221 risk dataset + outcome labels."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization
from apps.payments.models import Payment
from apps.risk.dataset import record_risk_prediction, resolve_pending_outcomes
from apps.risk.enums import (
    OUTCOME_INVOICE_90PLUS,
    OUTCOME_PAID_WITHIN_30D,
    OUTCOME_PAID_WITHIN_60D,
)
from apps.risk.models import RiskPrediction
from apps.risk.outcomes import compute_actual_outcome, risk_label_from_outcome
from apps.risk.services import calculate_customer_risk


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Dataset Co", slug="dataset-co")
    customer = Customer.objects.create(
        organization=org,
        name="Aday",
        code="D-1",
        credit_limit=Decimal("5000.00"),
        last_contact_at=timezone.now(),
    )
    return org, customer


@pytest.mark.django_db
def test_calculate_customer_risk_persists_prediction_row(org_customer):
    org, customer = org_customer
    result = calculate_customer_risk(customer.pk)

    assert "prediction_id" in result
    assert result["rule_score"] == result["final_score"]
    assert result["model_score"] is None

    pred = RiskPrediction.objects.get(pk=result["prediction_id"])
    assert pred.organization_id == org.id
    assert pred.customer_id == customer.id
    assert pred.feature_values
    assert "overdue_balance" in pred.feature_values
    assert pred.rule_score == result["rule_score"]
    assert pred.final_score == result["final_score"]
    assert pred.prediction_date == timezone.localdate()
    assert pred.outcome_date == pred.prediction_date + timedelta(days=90)
    assert pred.actual_outcome is None
    assert pred.model_version_id is None


@pytest.mark.django_db
def test_paid_within_outcomes(org_customer):
    org, customer = org_customer
    pred_date = date(2026, 1, 1)
    Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=date(2026, 1, 15),
        amount=Decimal("100.00"),
    )

    # Before 30d horizon → None
    early = compute_actual_outcome(customer, pred_date, as_of=date(2026, 1, 20))
    assert early[OUTCOME_PAID_WITHIN_30D] is None

    after30 = compute_actual_outcome(customer, pred_date, as_of=date(2026, 2, 1))
    assert after30[OUTCOME_PAID_WITHIN_30D] is True
    assert after30[OUTCOME_PAID_WITHIN_60D] is None

    after60 = compute_actual_outcome(customer, pred_date, as_of=date(2026, 3, 5))
    assert after60[OUTCOME_PAID_WITHIN_60D] is True


@pytest.mark.django_db
def test_invoice_90plus_outcome(org_customer):
    org, customer = org_customer
    pred_date = date(2026, 1, 1)
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-90",
        invoice_date=date(2025, 9, 1),
        due_date=date(2025, 10, 1),
        total_amount=Decimal("200.00"),
        status=InvoiceStatus.OVERDUE,
    )
    # day_90 = 2025-12-30 which is before pred; still unpaid → True once horizon elapsed
    as_of = pred_date + timedelta(days=90)
    outcome = compute_actual_outcome(customer, pred_date, as_of=as_of)
    assert outcome[OUTCOME_INVOICE_90PLUS] is True
    assert risk_label_from_outcome(outcome, target_label=OUTCOME_INVOICE_90PLUS) == 1


@pytest.mark.django_db
def test_resolve_pending_outcomes(org_customer):
    org, customer = org_customer
    pred_date = timezone.localdate() - timedelta(days=100)
    pred = record_risk_prediction(
        customer=customer,
        snapshot=None,
        feature_values={"overdue_balance": 0},
        rule_score=10,
        model_score=None,
        final_score=10,
        prediction_date=pred_date,
    )
    assert pred.actual_outcome is None

    result = resolve_pending_outcomes(organization_id=org.id, as_of=timezone.localdate())
    assert result["resolved"] >= 1
    pred.refresh_from_db()
    assert pred.actual_outcome is not None
    assert pred.outcomes_resolved_at is not None
    assert OUTCOME_PAID_WITHIN_30D in pred.actual_outcome
