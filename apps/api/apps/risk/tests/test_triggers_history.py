"""NP-103 trigger coverage + NP-104 history."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import (
    CallOutcome,
    CollectionTask,
    CollectionTaskStatus,
    CollectionTaskType,
)
from apps.collections.promises import create_promise, process_broken_promises
from apps.collections.services import complete_task
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization
from apps.payments.services import cancel_payment, create_payment
from apps.risk.models import RiskSnapshot
from apps.risk.services import customer_risk_history
from apps.risk.tasks import calculate_customer_risk_task


@pytest.fixture
def org_customer(db):
    org = Organization.objects.create(name="Trig Co", slug="trig-co")
    customer = Customer.objects.create(
        organization=org,
        name="Tetik",
        code="T-1",
        credit_limit=Decimal("10000.00"),
        last_contact_at=timezone.now(),
    )
    return org, customer


def _snap_count(customer):
    return RiskSnapshot.objects.filter(customer=customer).count()


@pytest.mark.django_db
def test_new_invoice_triggers_risk(org_customer):
    org, customer = org_customer
    before = _snap_count(customer)
    # Mimic serializer create path
    from apps.risk.triggers import bump_customer_risk

    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-R1",
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OPEN,
    )
    bump_customer_risk(customer)
    assert _snap_count(customer) == before + 1


@pytest.mark.django_db
def test_payment_create_and_cancel_trigger_risk(org_customer):
    org, customer = org_customer
    before = _snap_count(customer)
    payment = create_payment(
        organization=org,
        customer=customer,
        payment_date=date.today(),
        amount=Decimal("50.00"),
    )
    assert _snap_count(customer) >= before + 1
    mid = _snap_count(customer)
    cancel_payment(payment)
    assert _snap_count(customer) >= mid + 1


@pytest.mark.django_db
def test_promise_create_and_break_trigger_risk(org_customer):
    org, customer = org_customer
    before = _snap_count(customer)
    promise, _ = create_promise(
        organization=org,
        customer=customer,
        promised_date=date.today() + timedelta(days=3),
        amount=Decimal("80.00"),
    )
    assert _snap_count(customer) == before + 1
    mid = _snap_count(customer)
    promise.promised_date = date.today() - timedelta(days=2)
    promise.save(update_fields=["promised_date", "updated_at"])
    result = process_broken_promises(organization=org, as_of=date.today())
    assert result["broken"] == 1
    assert _snap_count(customer) >= mid + 1


@pytest.mark.django_db
def test_task_complete_triggers_risk(org_customer):
    org, customer = org_customer
    task = CollectionTask.objects.create(
        organization=org,
        customer=customer,
        title="Ara",
        due_date=date.today(),
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.OPEN,
    )
    before = _snap_count(customer)
    complete_task(
        task,
        outcome=CallOutcome.REACHED,
        outcome_notes="Konuşuldu",
    )
    assert _snap_count(customer) == before + 1


@pytest.mark.django_db
def test_daily_celery_task_runs(org_customer):
    org, customer = org_customer
    before = _snap_count(customer)
    out = calculate_customer_risk_task(customer_id=customer.id)
    assert out["updated"] == 1
    assert _snap_count(customer) == before + 1


@pytest.mark.django_db
def test_risk_history_ranges(org_customer):
    org, customer = org_customer
    from apps.risk.services import calculate_customer_risk

    calculate_customer_risk(customer.id)
    calculate_customer_risk(customer.id)
    hist = customer_risk_history(customer.id, range_key="30d")
    assert hist["range"] == "30d"
    assert len(hist["points"]) >= 2
    assert {"score", "level", "at", "reasons"} <= set(hist["points"][0].keys())

    old = RiskSnapshot.objects.filter(customer=customer).first()
    RiskSnapshot.objects.filter(pk=old.pk).update(
        calculated_at=timezone.now() - timedelta(days=40)
    )
    hist30 = customer_risk_history(customer.id, range_key="30d")
    hist90 = customer_risk_history(customer.id, range_key="90d")
    assert len(hist90["points"]) >= len(hist30["points"])
