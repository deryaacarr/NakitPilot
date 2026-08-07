from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer
from apps.forecasting.probability import (
    base_probability_for_overdue_days,
    calculate_collection_probability,
)
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Prob Co", slug="prob-co")
    customer = Customer.objects.create(
        organization=org,
        name="Olasılık",
        code="P-1",
        last_contact_at=timezone.now(),
    )
    return org, customer


def _open(org, customer, *, number, due, total="1000.00"):
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
    ("days", "expected"),
    [
        (0, Decimal("0.90")),
        (1, Decimal("0.80")),
        (15, Decimal("0.80")),
        (16, Decimal("0.65")),
        (30, Decimal("0.65")),
        (31, Decimal("0.45")),
        (60, Decimal("0.45")),
        (61, Decimal("0.25")),
        (90, Decimal("0.25")),
        (91, Decimal("0.10")),
        (200, Decimal("0.10")),
    ],
)
def test_base_probability_buckets(days, expected):
    assert base_probability_for_overdue_days(days) == expected


@pytest.mark.django_db
def test_not_due_expected_amount(org_customer):
    org, customer = org_customer
    today = date.today()
    inv = _open(org, customer, number="N1", due=today + timedelta(days=10))
    result = calculate_collection_probability(inv, as_of=today)
    assert result["overdue_days"] == 0
    assert result["base_probability"] == Decimal("0.90")
    assert result["probability"] == Decimal("0.90")
    assert result["expected_amount"] == Decimal("900.00")
    assert result["adjustments"] == []


@pytest.mark.django_db
def test_overdue_bucket_and_adjustments(org_customer):
    org, customer = org_customer
    today = date.today()
    inv = _open(org, customer, number="O20", due=today - timedelta(days=20))
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        invoice=inv,
        promised_date=today - timedelta(days=5),
        amount=Decimal("100.00"),
        status=PaymentPromiseStatus.BROKEN,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        invoice=inv,
        promised_date=today + timedelta(days=3),
        amount=Decimal("200.00"),
        status=PaymentPromiseStatus.PENDING,
    )
    result = calculate_collection_probability(inv, as_of=today)
    # base 0.65 − 0.20 + 0.15 = 0.60
    assert result["base_probability"] == Decimal("0.65")
    assert result["probability"] == Decimal("0.60")
    assert result["expected_amount"] == Decimal("600.00")
    codes = {a["code"] for a in result["adjustments"]}
    assert codes == {"BROKEN_PROMISE", "NEW_PROMISE"}


@pytest.mark.django_db
def test_probability_clamped_at_zero(org_customer):
    org, customer = org_customer
    today = date.today()
    inv = _open(org, customer, number="O90", due=today - timedelta(days=100), total="500.00")
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=2),
        amount=Decimal("50.00"),
        status=PaymentPromiseStatus.BROKEN,
    )
    result = calculate_collection_probability(inv, as_of=today)
    # 0.10 − 0.20 = −0.10 → clamp 0
    assert result["probability"] == Decimal("0.00")
    assert result["expected_amount"] == Decimal("0.00")
