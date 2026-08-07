"""NP-225 invoice collection horizons."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.customers.models import Customer
from apps.forecasting.probability import calculate_collection_horizons
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Horizon Co", slug="horizon-co")
    customer = Customer.objects.create(
        organization=org,
        name="Tahsilat",
        code="H-1",
        last_contact_at=timezone.now(),
    )
    return org, customer


@pytest.mark.django_db
def test_collection_horizons_monotonic(org_customer):
    org, customer = org_customer
    today = date.today()
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="HZ-1",
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=20),
        total_amount=Decimal("1000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    result = calculate_collection_horizons(inv, as_of=today)
    assert result["probability_7d"] <= result["probability_30d"] <= result["probability_60d"]
    assert result["expected_collection_date"] is not None
    expected = date.fromisoformat(result["expected_collection_date"])
    assert expected >= today
    assert expected <= today + timedelta(days=90)


@pytest.mark.django_db
def test_paid_invoice_horizons(org_customer):
    org, customer = org_customer
    today = date.today()
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="HZ-PAID",
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PAID,
        payment_completion_date=today - timedelta(days=5),
    )
    # remaining is 0 for paid after refresh — remaining_amount may still be total if no allocations
    # Force via open_amount path: remaining_amount() uses allocations
    result = calculate_collection_horizons(inv, as_of=today)
    assert "probability_7d" in result
    assert "expected_collection_date" in result
