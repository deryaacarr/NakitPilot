"""NP-234 payment plan suggestion tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import PaymentPromise
from apps.collections.payment_plans import (
    OPTION_OLDEST,
    OPTION_UPFRONT,
    OPTION_WEEKLY,
    PaymentPlanError,
    accept_payment_plan,
    suggest_payment_plans,
)
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Organization
from apps.payments.models import Payment


@pytest.fixture
def plan_ctx(db):
    org = Organization.objects.create(name="Plan Co", slug="plan-co-np234")
    customer = Customer.objects.create(
        organization=org,
        name="Plan Müşteri",
        code="PP-1",
        last_contact_at=timezone.now(),
    )
    today = date.today()
    inv1 = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-OLD-1",
        invoice_date=today - timedelta(days=60),
        due_date=today - timedelta(days=30),
        total_amount=Decimal("100000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    inv2 = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-OLD-2",
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
        total_amount=Decimal("125000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=today - timedelta(days=5),
        amount=Decimal("50000.00"),
        unallocated_amount=Decimal("50000.00"),
    )
    return org, customer, inv1, inv2, today


@pytest.mark.django_db
def test_three_non_binding_options_from_balance(plan_ctx):
    org, customer, inv1, inv2, _ = plan_ctx
    result = suggest_payment_plans(customer, organization=org)
    assert result["is_binding"] is False
    assert result["requires_approval"] is True
    assert "bağlayıcı" in result["disclaimer"].lower() or "onay" in result["disclaimer"].lower()
    assert Decimal(result["open_balance"]) == Decimal("225000.00")
    ids = {o["id"] for o in result["options"]}
    assert ids == {OPTION_UPFRONT, OPTION_WEEKLY, OPTION_OLDEST}
    upfront = next(o for o in result["options"] if o["id"] == OPTION_UPFRONT)
    assert "peşin" in upfront["summary"].lower()
    assert len(upfront["steps"]) == 3
    weekly = next(o for o in result["options"] if o["id"] == OPTION_WEEKLY)
    assert "hafta" in weekly["summary"].lower()
    oldest = next(o for o in result["options"] if o["id"] == OPTION_OLDEST)
    assert oldest["steps"][0]["invoice_number"] == "INV-OLD-1"
    assert oldest["steps"][1]["invoice_number"] == "INV-OLD-2"
    # Amounts come from DB — no invented total
    for opt in result["options"]:
        assert opt["is_binding"] is False
        assert opt["requires_approval"] is True
        assert opt["total_amount"] == "225000.00"


@pytest.mark.django_db
def test_accept_requires_confirmation(plan_ctx):
    org, customer, *_ = plan_ctx
    with pytest.raises(PaymentPlanError) as exc:
        accept_payment_plan(
            customer,
            organization=org,
            option_id=OPTION_UPFRONT,
            confirmed=False,
        )
    assert exc.value.code == "confirmation_required"
    assert PaymentPromise.objects.filter(customer=customer).count() == 0


@pytest.mark.django_db
def test_accept_creates_promises(plan_ctx):
    org, customer, *_ = plan_ctx
    result = accept_payment_plan(
        customer,
        organization=org,
        option_id=OPTION_OLDEST,
        confirmed=True,
    )
    assert result["accepted"] is True
    assert len(result["promise_ids"]) == 2
    assert PaymentPromise.objects.filter(customer=customer).count() == 2
