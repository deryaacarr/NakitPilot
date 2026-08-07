"""NP-170 — smoke suite tying required unit areas together."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.collections.models import PaymentPromiseStatus
from apps.collections.promises import compute_promise_status
from apps.customers.models import Customer, RiskStatus
from apps.forecasting.weekly import calculate_organization_forecast
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import overdue_days
from apps.invoices.services import compute_invoice_status
from apps.organizations.models import Organization
from apps.risk.rules import risk_level_for_score
from apps.risk.services import calculate_customer_risk


def test_np170_invoice_status_matrix():
    today = date(2026, 7, 31)
    assert (
        compute_invoice_status(
            total_amount=Decimal("100"),
            remaining_amount=Decimal("0"),
            due_date=today,
            as_of=today,
        )
        == InvoiceStatus.PAID
    )
    assert (
        compute_invoice_status(
            total_amount=Decimal("100"),
            remaining_amount=Decimal("50"),
            due_date=today,
            as_of=today,
        )
        == InvoiceStatus.PARTIALLY_PAID
    )
    assert (
        compute_invoice_status(
            total_amount=Decimal("100"),
            remaining_amount=Decimal("100"),
            due_date=today - timedelta(days=1),
            as_of=today,
        )
        == InvoiceStatus.OVERDUE
    )
    assert (
        compute_invoice_status(
            total_amount=Decimal("100"),
            remaining_amount=Decimal("100"),
            due_date=today + timedelta(days=1),
            as_of=today,
        )
        == InvoiceStatus.OPEN
    )


def test_np170_overdue_promise_risk_level():
    assert overdue_days(date(2026, 7, 1), as_of=date(2026, 7, 11)) == 10

    fulfilled = SimpleNamespace(
        status=PaymentPromiseStatus.PENDING,
        promised_date=date(2026, 7, 1),
        amount=Decimal("100"),
    )
    assert (
        compute_promise_status(fulfilled, as_of=date(2026, 7, 2), paid=Decimal("100"))
        == PaymentPromiseStatus.FULFILLED
    )
    broken = SimpleNamespace(
        status=PaymentPromiseStatus.PENDING,
        promised_date=date(2026, 7, 1),
        amount=Decimal("100"),
    )
    assert (
        compute_promise_status(broken, as_of=date(2026, 7, 2), paid=Decimal("0"))
        == PaymentPromiseStatus.BROKEN
    )
    assert risk_level_for_score(10) == RiskStatus.LOW
    assert risk_level_for_score(80) == RiskStatus.CRITICAL


@pytest.mark.django_db
def test_np170_risk_and_forecast_smoke():
    org = Organization.objects.create(name="Smoke Co", slug="smoke-co")
    customer = Customer.objects.create(organization=org, name="S", code="S-1")
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="S-INV",
        invoice_date=date.today() - timedelta(days=60),
        due_date=date.today() - timedelta(days=30),
        total_amount=Decimal("500.00"),
        status=InvoiceStatus.OVERDUE,
    )
    result = calculate_customer_risk(customer.pk)
    assert "score" in result
    assert 0 <= int(result["score"]) <= 100

    forecast = calculate_organization_forecast(org.pk, persist=True)
    assert isinstance(forecast, dict)
    assert "weeks" in forecast or "currency" in forecast
