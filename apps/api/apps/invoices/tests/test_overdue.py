from datetime import date
from decimal import Decimal

import pytest

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import (
    actual_delay_days,
    delay_days_for_risk,
    invoice_overdue_days,
    overdue_days,
)
from apps.organizations.models import Organization


def test_overdue_days_formula():
    today = date(2026, 7, 31)
    assert overdue_days(date(2026, 7, 20), as_of=today) == 11
    assert overdue_days(date(2026, 7, 31), as_of=today) == 0
    assert overdue_days(date(2026, 8, 5), as_of=today) == 0


def test_actual_delay_formula():
    due = date(2026, 7, 1)
    assert actual_delay_days(due, date(2026, 7, 10)) == 9
    assert actual_delay_days(due, date(2026, 6, 25)) == -6
    assert actual_delay_days(due, None) is None


@pytest.mark.django_db
def test_delay_for_risk_paid_vs_open():
    org = Organization.objects.create(name="Delay Co", slug="delay-co")
    customer = Customer.objects.create(organization=org, name="C", code="D1")
    paid = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="P1",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 15),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PAID,
        payment_completion_date=date(2026, 6, 20),
    )
    open_inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="O1",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 7, 20),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OVERDUE,
    )
    today = date(2026, 7, 31)
    assert delay_days_for_risk(paid, as_of=today) == 5
    assert delay_days_for_risk(open_inv, as_of=today) == 11


@pytest.mark.django_db
def test_invoice_overdue_days_gates():
    """NP-170: PAID/CANCELLED/DRAFT and zero remaining → 0."""
    org = Organization.objects.create(name="OD Co", slug="od-co")
    customer = Customer.objects.create(organization=org, name="C", code="OD1")
    today = date(2026, 7, 31)
    overdue = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OD-OPEN",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 7, 1),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OVERDUE,
    )
    assert invoice_overdue_days(overdue, as_of=today) == 30

    paid = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OD-PAID",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 7, 1),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PAID,
        payment_completion_date=date(2026, 7, 10),
    )
    assert invoice_overdue_days(paid, as_of=today) == 0

    cancelled = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OD-CAN",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 7, 1),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.CANCELLED,
    )
    assert invoice_overdue_days(cancelled, as_of=today) == 0

    draft = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OD-DR",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 7, 1),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.DRAFT,
    )
    assert invoice_overdue_days(draft, as_of=today) == 0
