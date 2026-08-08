"""NP-520 — Financial invariant tests (service + DB write path)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.services import compute_invoice_status, recalculate_invoice_status
from apps.organizations.models import Membership, Organization, Role
from apps.payments.invariants import (
    FinancialInvariantError,
    assert_invoice_remaining_non_negative,
    assert_overdue_invoice_remaining_positive,
    assert_paid_invoice_remaining_zero,
    assert_payment_allocations_within_amount,
    audit_organization_financial_invariants,
    enforce_invoice_financial_invariants,
)
from apps.payments.models import Payment, PaymentAllocation, ZERO
from apps.payments.services import PaymentValidationError, create_payment, replace_allocations

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def org_owner(db):
    org = Organization.objects.create(name="Inv Co", slug="inv-co-np520")
    owner = User.objects.create_user(email="np520@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(organization=org, name="Inv Cari", code="INV-520")
    return org, owner, customer


def _open_invoice(org, customer, *, number="INV-1", total="100.00", due=None, status=InvoiceStatus.OPEN):
    today = timezone.localdate()
    return Invoice.objects.create(
        organization=org,
        customer=customer,
        number=number,
        invoice_date=today - timedelta(days=30),
        due_date=due or (today + timedelta(days=10)),
        total_amount=Decimal(total),
        subtotal_amount=Decimal(total),
        status=status,
    )


# --- Pure / service rules -----------------------------------------------------


@pytest.mark.django_db
def test_remaining_never_negative_after_valid_payment(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer)
    create_payment(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("40.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("40.00")}],
    )
    inv.refresh_from_db()
    assert inv.remaining_amount() == Decimal("60.00")
    assert inv.remaining_amount_raw() == Decimal("60.00")
    assert_invoice_remaining_non_negative(inv)


@pytest.mark.django_db
def test_service_rejects_allocation_exceeding_invoice_remaining(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00")
    with pytest.raises(PaymentValidationError) as exc:
        create_payment(
            organization=org,
            customer=customer,
            payment_date=timezone.localdate(),
            amount=Decimal("150.00"),
            recorded_by=owner,
            allocations=[{"invoice_id": inv.id, "amount": Decimal("150.00")}],
        )
    assert exc.value.code == "allocation_exceeds_remaining"
    assert Payment.objects.filter(organization=org).count() == 0
    assert PaymentAllocation.objects.filter(organization=org).count() == 0
    inv.refresh_from_db()
    assert inv.remaining_amount() == Decimal("100.00")


@pytest.mark.django_db
def test_service_rejects_allocation_sum_exceeding_payment_amount(org_owner):
    org, owner, customer = org_owner
    a = _open_invoice(org, customer, number="A", total="80.00")
    b = _open_invoice(org, customer, number="B", total="80.00")
    with pytest.raises(PaymentValidationError) as exc:
        create_payment(
            organization=org,
            customer=customer,
            payment_date=timezone.localdate(),
            amount=Decimal("100.00"),
            recorded_by=owner,
            allocations=[
                {"invoice_id": a.id, "amount": Decimal("60.00")},
                {"invoice_id": b.id, "amount": Decimal("50.00")},
            ],
        )
    assert exc.value.code == "allocation_exceeds_payment"
    assert PaymentAllocation.objects.filter(organization=org).count() == 0


@pytest.mark.django_db
def test_paid_invoice_remaining_is_zero(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00")
    create_payment(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("100.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("100.00")}],
    )
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    assert inv.remaining_amount() == ZERO
    assert_paid_invoice_remaining_zero(inv)
    enforce_invoice_financial_invariants(inv)


@pytest.mark.django_db
def test_overdue_invoice_remaining_must_be_positive(org_owner):
    org, _owner, customer = org_owner
    today = timezone.localdate()
    inv = _open_invoice(
        org,
        customer,
        total="100.00",
        due=today - timedelta(days=5),
        status=InvoiceStatus.OPEN,
    )
    new_status = recalculate_invoice_status(inv, as_of=today, save=True)
    assert new_status == InvoiceStatus.OVERDUE
    inv.refresh_from_db()
    assert inv.remaining_amount() > ZERO
    assert_overdue_invoice_remaining_positive(inv)


@pytest.mark.django_db
def test_status_invariant_rejects_paid_with_nonzero_remaining(org_owner):
    org, _owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00")
    inv.status = InvoiceStatus.PAID
    inv.save(update_fields=["status", "updated_at"])
    with pytest.raises(FinancialInvariantError) as exc:
        assert_paid_invoice_remaining_zero(inv)
    assert exc.value.code == "paid_invoice_nonzero_remaining"


@pytest.mark.django_db
def test_status_invariant_rejects_overdue_with_zero_remaining(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00", due=timezone.localdate() - timedelta(days=3))
    create_payment(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("100.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("100.00")}],
    )
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    # Force corrupt status for invariant assertion
    inv.status = InvoiceStatus.OVERDUE
    with pytest.raises(FinancialInvariantError) as exc:
        assert_overdue_invoice_remaining_positive(inv)
    assert exc.value.code == "overdue_invoice_zero_remaining"


# --- DB write path (PaymentAllocation.save) -----------------------------------


@pytest.mark.django_db
def test_db_save_rejects_allocation_exceeding_payment_amount(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="200.00")
    payment = Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("50.00"),
        currency="TRY",
        recorded_by=owner,
        unallocated_amount=Decimal("50.00"),
    )
    with pytest.raises(FinancialInvariantError) as exc:
        PaymentAllocation.objects.create(
            organization=org,
            payment=payment,
            invoice=inv,
            amount=Decimal("60.00"),
        )
    assert exc.value.code == "allocation_exceeds_payment"
    assert PaymentAllocation.objects.filter(payment=payment).count() == 0


@pytest.mark.django_db
def test_db_save_rejects_allocation_exceeding_invoice_total(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00")
    p1 = Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("80.00"),
        currency="TRY",
        recorded_by=owner,
        unallocated_amount=Decimal("80.00"),
    )
    PaymentAllocation.objects.create(
        organization=org,
        payment=p1,
        invoice=inv,
        amount=Decimal("80.00"),
    )
    p1.refresh_unallocated(save=True)

    p2 = Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("50.00"),
        currency="TRY",
        recorded_by=owner,
        unallocated_amount=Decimal("50.00"),
    )
    with pytest.raises(FinancialInvariantError) as exc:
        PaymentAllocation.objects.create(
            organization=org,
            payment=p2,
            invoice=inv,
            amount=Decimal("30.00"),  # 80+30 > 100
        )
    assert exc.value.code in {
        "allocation_exceeds_invoice_total",
        "invoice_remaining_negative",
    }
    assert PaymentAllocation.objects.filter(payment=p2).count() == 0
    inv.refresh_from_db()
    assert inv.allocated_amount() == Decimal("80.00")
    assert_invoice_remaining_non_negative(inv)


@pytest.mark.django_db
def test_db_violation_rolls_back_inside_atomic(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00")
    payment = Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("40.00"),
        currency="TRY",
        recorded_by=owner,
        unallocated_amount=Decimal("40.00"),
    )
    with pytest.raises(FinancialInvariantError):
        with transaction.atomic():
            PaymentAllocation.objects.create(
                organization=org,
                payment=payment,
                invoice=inv,
                amount=Decimal("40.00"),
            )
            # Second allocation on same payment → exceeds payment.amount
            PaymentAllocation.objects.create(
                organization=org,
                payment=payment,
                invoice=_open_invoice(org, customer, number="INV-2", total="100.00"),
                amount=Decimal("10.00"),
            )
    assert PaymentAllocation.objects.filter(payment=payment).count() == 0


@pytest.mark.django_db
def test_refresh_unallocated_raises_instead_of_clamping(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="200.00")
    payment = Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("50.00"),
        currency="TRY",
        recorded_by=owner,
        unallocated_amount=Decimal("50.00"),
    )
    # Bypass save() invariant with skip, then refresh must raise.
    alloc = PaymentAllocation(
        organization=org,
        payment=payment,
        invoice=inv,
        amount=Decimal("70.00"),
    )
    alloc.save(skip_financial_invariants=True)

    with pytest.raises(FinancialInvariantError) as exc:
        payment.refresh_unallocated(save=True)
    assert exc.value.code == "allocation_exceeds_payment"


@pytest.mark.django_db
def test_replace_allocations_enforces_invariants(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00")
    payment = create_payment(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("50.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("50.00")}],
    )
    with pytest.raises(PaymentValidationError) as exc:
        replace_allocations(
            payment,
            [{"invoice_id": inv.id, "amount": Decimal("120.00")}],
            actor=owner,
        )
    assert exc.value.code == "allocation_exceeds_remaining"
    payment.refresh_from_db()
    assert payment.allocated_total() == Decimal("50.00")


@pytest.mark.django_db
def test_recalculate_enforces_paid_and_overdue_invariants(org_owner):
    org, owner, customer = org_owner
    today = timezone.localdate()
    inv = _open_invoice(org, customer, total="100.00", due=today - timedelta(days=2))
    create_payment(
        organization=org,
        customer=customer,
        payment_date=today,
        amount=Decimal("100.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("100.00")}],
    )
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    # Recalculate again stays PAID and passes enforce
    assert recalculate_invoice_status(inv, as_of=today, save=True) == InvoiceStatus.PAID

    overdue = _open_invoice(
        org,
        customer,
        number="OD-1",
        total="40.00",
        due=today - timedelta(days=1),
    )
    assert recalculate_invoice_status(overdue, as_of=today, save=True) == InvoiceStatus.OVERDUE
    enforce_invoice_financial_invariants(overdue)


@pytest.mark.django_db
def test_audit_organization_reports_corrupt_allocation(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer, total="100.00")
    payment = Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("50.00"),
        currency="TRY",
        recorded_by=owner,
        unallocated_amount=Decimal("50.00"),
    )
    alloc = PaymentAllocation(
        organization=org,
        payment=payment,
        invoice=inv,
        amount=Decimal("90.00"),
    )
    alloc.save(skip_financial_invariants=True)

    violations = audit_organization_financial_invariants(org)
    codes = {v["code"] for v in violations}
    assert "allocation_exceeds_payment" in codes


def test_compute_status_overdue_requires_positive_remaining_conceptually():
    today = date(2026, 8, 1)
    assert (
        compute_invoice_status(
            total_amount=Decimal("100.00"),
            remaining_amount=Decimal("100.00"),
            due_date=date(2026, 7, 1),
            as_of=today,
        )
        == InvoiceStatus.OVERDUE
    )
    assert (
        compute_invoice_status(
            total_amount=Decimal("100.00"),
            remaining_amount=ZERO,
            due_date=date(2026, 7, 1),
            as_of=today,
        )
        == InvoiceStatus.PAID
    )


@pytest.mark.django_db
def test_payment_allocation_within_amount_helper(org_owner):
    org, owner, customer = org_owner
    inv = _open_invoice(org, customer)
    payment = create_payment(
        organization=org,
        customer=customer,
        payment_date=timezone.localdate(),
        amount=Decimal("25.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("25.00")}],
    )
    assert_payment_allocations_within_amount(payment)
