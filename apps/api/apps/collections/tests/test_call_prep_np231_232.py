"""NP-231 call prep + NP-232 note parsing tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.collections.call_prep import build_call_preparation
from apps.collections.models import (
    CallOutcome,
    CollectionActivity,
    CollectionActivityType,
    CollectionTask,
    CollectionTaskStatus,
    CollectionTaskType,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.collections.note_parser import parse_call_notes
from apps.collections.services import confirm_structured_call_notes
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization

User = get_user_model()


@pytest.fixture
def org_ctx(db):
    org = Organization.objects.create(name="Call Prep Co", slug="call-prep-co")
    user = User.objects.create_user(email="agent@callprep.local", password="x")
    customer = Customer.objects.create(
        organization=org,
        name="ABC Elektrik",
        code="CP-1",
        last_contact_at=timezone.now() - timedelta(days=5),
    )
    task = CollectionTask.objects.create(
        organization=org,
        customer=customer,
        title="Ara",
        due_date=timezone.localdate(),
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.OPEN,
        created_by=user,
        assigned_to=user,
    )
    return org, user, customer, task


@pytest.mark.django_db
def test_call_prep_includes_sections(org_ctx):
    org, user, customer, task = org_ctx
    today = timezone.localdate()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="CP-INV",
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=20),
        total_amount=Decimal("10000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=3),
        amount=Decimal("2000.00"),
        status=PaymentPromiseStatus.BROKEN,
        notes="Tutmadı",
        created_by=user,
    )
    CollectionTask.objects.create(
        organization=org,
        customer=customer,
        title="Eski itiraz",
        due_date=today - timedelta(days=10),
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.COMPLETED,
        outcome=CallOutcome.DISPUTED,
        outcome_notes="Fatura tutarına itiraz",
        completed_at=timezone.now() - timedelta(days=10),
        created_by=user,
    )
    CollectionActivity.objects.create(
        organization=org,
        customer=customer,
        activity_type=CollectionActivityType.CALL,
        summary="Önceki arama",
        notes="Müşteri meşguldü",
        occurred_at=timezone.now() - timedelta(days=2),
        created_by=user,
    )

    prep = build_call_preparation(customer, organization=org, task=task, as_of=today)
    assert prep["open_invoices"]
    assert prep["last_payment_promise"]["status"] == PaymentPromiseStatus.BROKEN
    assert prep["last_objection"]["notes"] == "Fatura tutarına itiraz"
    assert prep["previous_call_notes"]
    assert prep["suggested_payment_plan"] is not None
    assert prep["talking_points"]
    assert prep["sources"]


@pytest.mark.django_db
def test_parse_notes_example_fixture():
    # Monday 2026-08-03 → next Friday is 2026-08-07
    as_of = date(2026, 8, 3)
    text = (
        "Müşteri cuma günü 80 bin ödeyeceğini söyledi, "
        "kalanını ay sonuna bırakmak istiyor."
    )
    result = parse_call_notes(text, as_of=as_of)
    draft = result["draft"]
    assert result["needs_confirm"] is True
    assert draft["promised_amount"] == "80000.00"
    assert draft["promised_date"] == "2026-08-07"
    assert draft["next_action_date"] == "2026-08-08"
    assert draft["sentiment"] == "neutral"
    assert draft["objection"] == "remaining_balance_deferred"


@pytest.mark.django_db
def test_parse_does_not_create_records(org_ctx):
    _, _, _, task = org_ctx
    before_promises = PaymentPromise.objects.count()
    before_acts = CollectionActivity.objects.count()
    parse_call_notes("Cuma 50 bin ödeyecek", as_of=date(2026, 8, 3))
    assert PaymentPromise.objects.count() == before_promises
    assert CollectionActivity.objects.count() == before_acts


@pytest.mark.django_db
def test_confirm_creates_promise_only_when_confirmed(org_ctx):
    _, user, customer, task = org_ctx
    result = confirm_structured_call_notes(
        task,
        actor=user,
        raw_notes="Cuma 80 bin",
        promised_amount=Decimal("80000.00"),
        promised_date=date(2026, 8, 7),
        next_action_date=date(2026, 8, 8),
        sentiment="neutral",
        objection="remaining_balance_deferred",
        complete_task_flag=False,
    )
    assert result["promise"] is not None
    assert result["promise"].amount == Decimal("80000.00")
    assert result["follow_up"] is not None
    assert result["follow_up"].due_date == date(2026, 8, 8)
    assert result["completed"] is False
    task.refresh_from_db()
    assert task.status == CollectionTaskStatus.OPEN
    act = CollectionActivity.objects.get(pk=result["activity_id"])
    assert act.metadata["structured_notes"]["confirmed"] is True
