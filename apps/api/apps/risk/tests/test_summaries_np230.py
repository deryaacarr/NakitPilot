"""NP-230 customer summary — sourced facts only."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization
from apps.risk.summaries import build_customer_summary


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Sum Co", slug="sum-co")
    customer = Customer.objects.create(
        organization=org,
        name="ABC Elektrik",
        code="S-1",
        credit_limit=Decimal("1000000.00"),
        last_contact_at=timezone.now() - timedelta(days=8),
    )
    return org, customer


@pytest.mark.django_db
def test_summary_uses_db_numbers_and_sources(org_customer):
    org, customer = org_customer
    today = date.today()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="SUM-1",
        invoice_date=today - timedelta(days=77),
        due_date=today - timedelta(days=47),
        total_amount=Decimal("425000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    # Three paid invoices: two late
    for i, delay in enumerate([5, 3, -1]):
        Invoice.objects.create(
            organization=org,
            customer=customer,
            number=f"PAID-{i}",
            invoice_date=today - timedelta(days=120 + i),
            due_date=today - timedelta(days=90 + i),
            total_amount=Decimal("1000.00"),
            status=InvoiceStatus.PAID,
            payment_completion_date=today - timedelta(days=90 + i - delay),
        )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=date(today.year, 7, 12) if today.month >= 7 else date(today.year - 1, 7, 12),
        amount=Decimal("5000.00"),
        status=PaymentPromiseStatus.BROKEN,
    )

    result = build_customer_summary(customer, organization=org, as_of=today)
    assert "425.000 TL" in result["summary"] or "425000" in result["summary"].replace(".", "")
    assert any("gün gecikmiş" in p for p in result["paragraphs"])
    assert any("geç ödendi" in p for p in result["paragraphs"])
    assert any("ödeme sözünü yerine getirmedi" in p for p in result["paragraphs"])
    assert any("görüşme" in p for p in result["paragraphs"])

    fact_keys = {f["key"] for f in result["facts"]}
    assert "open_balance" in fact_keys
    assert result["sources"]
    assert all("type" in s and "field" in s for s in result["sources"])
    # No hallucinated free-form numbers outside facts
    open_fact = next(f for f in result["facts"] if f["key"] == "open_balance")
    assert open_fact["value"] == "425000.00"


@pytest.mark.django_db
def test_summary_rejects_cross_org(org_customer):
    org, customer = org_customer
    other = Organization.objects.create(name="Other", slug="other-sum")
    with pytest.raises(PermissionError):
        build_customer_summary(customer, organization=other)
