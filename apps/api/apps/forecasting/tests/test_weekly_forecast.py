from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer
from apps.forecasting.models import ForecastSnapshot
from apps.forecasting.weekly import (
    FORECAST_WEEK_COUNT,
    calculate_organization_forecast,
    iso_week_start,
)
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Week Fc", slug="week-fc")
    customer = Customer.objects.create(
        organization=org,
        name="Haftalık",
        code="W-1",
        last_contact_at=timezone.now(),
    )
    return org, customer


@pytest.mark.django_db
def test_thirteen_week_horizon_has_fourteen_buckets(org_customer):
    org, customer = org_customer
    today = date.today()
    # Not-due invoice → nominal this/future week, high probability
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="F1",
        invoice_date=today,
        due_date=today + timedelta(days=10),
        total_amount=Decimal("1000.00"),
        status=InvoiceStatus.OPEN,
        currency="TRY",
    )
    result = calculate_organization_forecast(org.id, as_of=today, persist=True)
    assert result["week_count"] == FORECAST_WEEK_COUNT == 14
    assert len(result["weeks"]) == 14
    assert result["weeks"][0]["week_start"] == iso_week_start(today)

    week = next(w for w in result["weeks"] if w["nominal_amount"] > 0)
    assert week["nominal_amount"] == Decimal("1000.00")
    assert week["expected_amount"] == Decimal("900.00")  # 90% not overdue
    assert week["optimistic_amount"] >= week["expected_amount"]
    assert week["pessimistic_amount"] <= week["expected_amount"]

    snaps = ForecastSnapshot.objects.filter(organization=org, run_id=result["run_id"])
    assert snaps.count() == 14
    assert snaps.filter(nominal_amount=Decimal("1000.00")).exists()


@pytest.mark.django_db
def test_overdue_and_unlinked_promise(org_customer):
    org, customer = org_customer
    today = date.today()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OV",
        invoice_date=today - timedelta(days=60),
        due_date=today - timedelta(days=20),
        total_amount=Decimal("500.00"),
        status=InvoiceStatus.OVERDUE,
        currency="TRY",
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        invoice=None,
        promised_date=today + timedelta(days=5),
        amount=Decimal("200.00"),
        currency="TRY",
        status=PaymentPromiseStatus.PENDING,
    )
    result = calculate_organization_forecast(org.id, as_of=today, persist=False)
    total_nominal = sum((w["nominal_amount"] for w in result["weeks"]), Decimal("0"))
    assert total_nominal == Decimal("700.00")
    assert any(w["promise_count"] > 0 for w in result["weeks"])


@pytest.mark.django_db
def test_past_due_clamped_to_current_week(org_customer):
    org, customer = org_customer
    today = date.today()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OLD",
        invoice_date=today - timedelta(days=120),
        due_date=today - timedelta(days=100),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OVERDUE,
        currency="TRY",
    )
    result = calculate_organization_forecast(org.id, as_of=today, persist=False)
    first = result["weeks"][0]
    assert first["nominal_amount"] == Decimal("100.00")
