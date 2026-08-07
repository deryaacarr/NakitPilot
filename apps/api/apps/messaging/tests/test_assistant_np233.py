"""NP-233 message tone assistant tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.messaging.assistant import MessageTone, generate_message
from apps.messaging.services import MessagingError, generate_toned_message
from apps.organizations.models import Organization


@pytest.fixture
def org_invoice(db):
    org = Organization.objects.create(name="Msg Co", slug="msg-tone-co")
    customer = Customer.objects.create(
        organization=org,
        name="ABC Elektrik",
        code="MT-1",
        last_contact_at=timezone.now(),
    )
    today = date.today()
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-TON-1",
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=15),
        total_amount=Decimal("64000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    return org, customer, inv, today


@pytest.mark.django_db
@pytest.mark.parametrize("tone", list(MessageTone.values))
def test_all_tones_fill_db_fields(org_invoice, tone):
    org, customer, inv, today = org_invoice
    result = generate_message(
        organization=org,
        customer=customer,
        tone=tone,
        invoice=inv,
    )
    assert "INV-TON-1" in result["body"]
    assert "INV-TON-1" in result["subject"] or "INV-TON-1" in result["body"]
    # Amount from DB (remaining = total with no payments)
    assert "64.000 TL" in result["body"] or "64000" in result["body"].replace(".", "")
    assert str(15) in result["body"] or result["variables"]["overdue_days"] == "15"
    assert result["source_fields"]["invoice_number"] == "INV-TON-1"
    assert result["source_fields"]["overdue_days"] == "15"
    assert result["variables"]["due_date"]  # formatted from DB


@pytest.mark.django_db
def test_generate_rejects_invalid_tone(org_invoice):
    org, customer, inv, _ = org_invoice
    with pytest.raises(MessagingError):
        generate_toned_message(
            org,
            customer_id=customer.id,
            tone="SARCASM",
            invoice_id=inv.id,
        )


@pytest.mark.django_db
def test_no_invented_amount_without_invoice(org_invoice):
    org, customer, inv, _ = org_invoice
    # Delete open invoice path: use paid so auto-pick finds nothing if we pass None
    # and customer has only this overdue — pass invoice explicitly empty by using
    # a customer with no invoices.
    empty = Customer.objects.create(
        organization=org,
        name="Boş",
        code="MT-0",
        last_contact_at=timezone.now(),
    )
    result = generate_message(
        organization=org,
        customer=empty,
        tone=MessageTone.PROFESYONEL,
        invoice=None,
    )
    assert result["variables"]["invoice_number"] == ""
    assert result["variables"]["remaining_amount"] == ""
    assert "64.000" not in result["body"]
