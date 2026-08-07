from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.services import (
    compute_invoice_status,
    recalculate_all_invoice_statuses,
    recalculate_invoice_status,
    recalculate_invoices_after_payment,
)
from apps.invoices.tasks import (
    recalculate_invoice_statuses,
    recalculate_invoices_after_payment_task,
)
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"
TODAY = date(2026, 7, 31)


@pytest.mark.parametrize(
    ("remaining", "total", "due", "expected"),
    [
        (Decimal("0.00"), Decimal("100.00"), date(2026, 8, 15), InvoiceStatus.PAID),
        (Decimal("0.00"), Decimal("0.00"), date(2026, 8, 15), InvoiceStatus.PAID),
        (Decimal("40.00"), Decimal("100.00"), date(2026, 8, 15), InvoiceStatus.PARTIALLY_PAID),
        (Decimal("40.00"), Decimal("100.00"), date(2026, 7, 1), InvoiceStatus.PARTIALLY_PAID),
        (Decimal("100.00"), Decimal("100.00"), date(2026, 7, 1), InvoiceStatus.OVERDUE),
        (Decimal("100.00"), Decimal("100.00"), date(2026, 7, 31), InvoiceStatus.OPEN),
        (Decimal("100.00"), Decimal("100.00"), date(2026, 8, 15), InvoiceStatus.OPEN),
    ],
)
def test_compute_invoice_status_rules(remaining, total, due, expected):
    assert (
        compute_invoice_status(
            total_amount=total,
            remaining_amount=remaining,
            due_date=due,
            as_of=TODAY,
        )
        == expected
    )


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Status Co", slug="status-co")
    owner = User.objects.create_user(email="status@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(organization=org, name="Cari", code="S-1")
    return org, customer


def _invoice(org, customer, **kwargs) -> Invoice:
    defaults = {
        "organization": org,
        "customer": customer,
        "number": kwargs.pop("number", f"N-{Invoice.objects.count() + 1}"),
        "invoice_date": date(2026, 7, 1),
        "due_date": date(2026, 8, 15),
        "total_amount": Decimal("100.00"),
        "status": InvoiceStatus.OPEN,
    }
    defaults.update(kwargs)
    return Invoice.objects.create(**defaults)


@pytest.mark.django_db
def test_skips_draft_and_cancelled(org_customer):
    org, customer = org_customer
    draft = _invoice(org, customer, status=InvoiceStatus.DRAFT, number="D1")
    cancelled = _invoice(
        org,
        customer,
        status=InvoiceStatus.CANCELLED,
        number="C1",
        due_date=date(2026, 7, 1),
    )

    assert recalculate_invoice_status(draft, as_of=TODAY) is None
    draft.refresh_from_db()
    assert draft.status == InvoiceStatus.DRAFT

    assert recalculate_invoice_status(cancelled, as_of=TODAY) is None
    cancelled.refresh_from_db()
    assert cancelled.status == InvoiceStatus.CANCELLED


@pytest.mark.django_db
def test_open_becomes_overdue_when_due_passed(org_customer):
    org, customer = org_customer
    invoice = _invoice(
        org,
        customer,
        status=InvoiceStatus.OPEN,
        due_date=TODAY - timedelta(days=1),
    )
    result = recalculate_invoice_status(invoice, as_of=TODAY)
    assert result == InvoiceStatus.OVERDUE
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.OVERDUE


@pytest.mark.django_db
def test_paid_when_remaining_zero_via_mock_allocation(org_customer):
    org, customer = org_customer
    invoice = _invoice(org, customer, status=InvoiceStatus.OPEN)

    with patch.object(Invoice, "allocated_amount", return_value=Decimal("100.00")):
        result = recalculate_invoice_status(invoice, as_of=TODAY)

    assert result == InvoiceStatus.PAID
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.PAID


@pytest.mark.django_db
def test_partially_paid_beats_overdue(org_customer):
    org, customer = org_customer
    invoice = _invoice(
        org,
        customer,
        status=InvoiceStatus.OPEN,
        due_date=TODAY - timedelta(days=5),
    )

    with patch.object(Invoice, "allocated_amount", return_value=Decimal("30.00")):
        result = recalculate_invoice_status(invoice, as_of=TODAY)

    assert result == InvoiceStatus.PARTIALLY_PAID


@pytest.mark.django_db
def test_after_payment_and_daily_bulk(org_customer):
    org, customer = org_customer
    overdue_candidate = _invoice(
        org,
        customer,
        number="O1",
        status=InvoiceStatus.OPEN,
        due_date=TODAY - timedelta(days=2),
    )
    still_open = _invoice(
        org,
        customer,
        number="O2",
        status=InvoiceStatus.OPEN,
        due_date=TODAY + timedelta(days=10),
    )

    payment_result = recalculate_invoices_after_payment(
        [overdue_candidate.id, still_open.id],
        as_of=TODAY,
    )
    assert payment_result["checked"] == 2
    assert payment_result["updated"] == 1
    overdue_candidate.refresh_from_db()
    still_open.refresh_from_db()
    assert overdue_candidate.status == InvoiceStatus.OVERDUE
    assert still_open.status == InvoiceStatus.OPEN

    # Reset one for daily job
    still_open.status = InvoiceStatus.OPEN
    still_open.due_date = TODAY - timedelta(days=1)
    still_open.save(update_fields=["status", "due_date", "updated_at"])

    daily = recalculate_all_invoice_statuses(as_of=TODAY)
    assert daily["checked"] >= 2
    assert daily["updated"] >= 1
    still_open.refresh_from_db()
    assert still_open.status == InvoiceStatus.OVERDUE


@pytest.mark.django_db
def test_celery_tasks_run(org_customer, settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    org, customer = org_customer
    invoice = _invoice(
        org,
        customer,
        status=InvoiceStatus.OPEN,
        due_date=TODAY - timedelta(days=3),
    )

    with patch("apps.invoices.services.timezone.localdate", return_value=TODAY):
        daily = recalculate_invoice_statuses()
        after = recalculate_invoices_after_payment_task([invoice.id])

    assert daily["checked"] >= 1
    assert after["checked"] == 1
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.OVERDUE
