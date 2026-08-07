"""NP-227 fallback cascade tests."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization
from apps.risk.fallback import (
    SOURCE_ML,
    SOURCE_RULES,
    SOURCE_SIMPLE,
    resolve_risk_with_fallback,
    simple_overdue_risk,
)
from apps.risk.services import calculate_customer_risk


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Fallback Co", slug="fallback-co")
    customer = Customer.objects.create(
        organization=org,
        name="Fallback",
        code="FB-1",
        credit_limit=Decimal("5000.00"),
        last_contact_at=timezone.now(),
    )
    return org, customer


@pytest.mark.django_db
def test_simple_overdue_risk_buckets(org_customer):
    org, customer = org_customer
    today = date.today()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="FB-O",
        invoice_date=today - timedelta(days=100),
        due_date=today - timedelta(days=95),
        total_amount=Decimal("200.00"),
        status=InvoiceStatus.OVERDUE,
    )
    score, level, details = simple_overdue_risk(customer, as_of=today)
    assert score >= 75
    assert details["meta"]["oldest_overdue_days"] >= 90
    assert level in {"HIGH", "CRITICAL"}


@pytest.mark.django_db
def test_fallback_uses_rules_when_ml_absent(org_customer):
    _, customer = org_customer
    resolved = resolve_risk_with_fallback(customer)
    assert resolved["source"] in {SOURCE_RULES, SOURCE_SIMPLE}
    assert resolved["model_score"] is None
    assert 0 <= resolved["score"] <= 100


@pytest.mark.django_db
def test_fallback_to_simple_when_rules_fail(org_customer):
    org, customer = org_customer
    today = date.today()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="FB-S",
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=20),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OVERDUE,
    )
    with patch(
        "apps.risk.fallback.compute_customer_risk_score",
        side_effect=RuntimeError("boom"),
    ):
        with patch(
            "apps.risk.fallback.score_feature_values",
            return_value=(None, None),
        ):
            resolved = resolve_risk_with_fallback(customer, as_of=today)
    assert resolved["source"] == SOURCE_SIMPLE
    assert resolved["score"] > 0


@pytest.mark.django_db
def test_calculate_customer_risk_records_source(org_customer):
    _, customer = org_customer
    result = calculate_customer_risk(customer.pk)
    assert "source" in result
    assert "fallback_chain" in result
    assert result["source"] in {SOURCE_ML, SOURCE_RULES, SOURCE_SIMPLE}
