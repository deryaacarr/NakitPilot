from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer
from apps.forecasting.prediction import (
    predict_expected_collection_date,
    prediction_confidence,
)
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Forecast Co", slug="forecast-co")
    customer = Customer.objects.create(
        organization=org,
        name="Tahmin",
        code="F-1",
        last_contact_at=timezone.now(),
    )
    return org, customer


def _paid(org, customer, *, number, due, paid_on, total="100.00"):
    return Invoice.objects.create(
        organization=org,
        customer=customer,
        number=number,
        invoice_date=due - timedelta(days=30),
        due_date=due,
        total_amount=Decimal(total),
        status=InvoiceStatus.PAID,
        payment_completion_date=paid_on,
    )


def _open(org, customer, *, number, due, total="200.00"):
    return Invoice.objects.create(
        organization=org,
        customer=customer,
        number=number,
        invoice_date=due - timedelta(days=30),
        due_date=due,
        total_amount=Decimal(total),
        status=InvoiceStatus.OPEN,
    )


@pytest.mark.parametrize(
    ("has_history", "broken", "expected"),
    [
        (True, False, "HIGH"),
        (False, False, "MEDIUM"),
        (True, True, "MEDIUM"),
        (False, True, "LOW"),
    ],
)
def test_confidence_bands(has_history, broken, expected):
    assert (
        prediction_confidence(has_history=has_history, has_broken_promise=broken)
        == expected
    )


@pytest.mark.django_db
def test_expected_collection_uses_avg_delay(org_customer):
    org, customer = org_customer
    today = date.today()
    # Three paid invoices, each 12 days late → avg 12
    for i in range(3):
        due = today - timedelta(days=60 + i * 10)
        _paid(org, customer, number=f"P{i}", due=due, paid_on=due + timedelta(days=12))

    open_inv = _open(org, customer, number="O1", due=today + timedelta(days=20))
    result = predict_expected_collection_date(open_inv)

    assert result["avg_delay_days"] == 12
    assert result["expected_collection_date"] == open_inv.due_date + timedelta(days=12)
    assert result["method"] == "AVG_DELAY"
    assert result["confidence"] == "HIGH"
    assert result["has_broken_promise"] is False


@pytest.mark.django_db
def test_no_history_falls_back_to_due_date(org_customer):
    org, customer = org_customer
    today = date.today()
    open_inv = _open(org, customer, number="O2", due=today + timedelta(days=15))
    result = predict_expected_collection_date(open_inv)

    assert result["avg_delay_days"] is None
    assert result["expected_collection_date"] == open_inv.due_date
    assert result["method"] == "DUE_DATE_FALLBACK"
    assert result["confidence"] == "MEDIUM"


@pytest.mark.django_db
def test_broken_promise_lowers_confidence(org_customer):
    org, customer = org_customer
    today = date.today()
    due = today - timedelta(days=40)
    _paid(org, customer, number="P0", due=due, paid_on=due + timedelta(days=12))
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=1),
        amount=Decimal("50.00"),
        status=PaymentPromiseStatus.BROKEN,
    )
    open_inv = _open(org, customer, number="O3", due=today + timedelta(days=10))
    result = predict_expected_collection_date(open_inv)

    assert result["method"] == "AVG_DELAY"
    assert result["expected_collection_date"] == open_inv.due_date + timedelta(days=12)
    assert result["has_broken_promise"] is True
    assert result["confidence"] == "MEDIUM"  # history + broken → reduced from HIGH
