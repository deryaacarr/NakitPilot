"""NP-170/174 — financial decimal & payment edge cases."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.services import compute_invoice_status
from apps.organizations.models import Membership, Organization, Role
from apps.payments.models import Payment, ZERO
from apps.payments.services import auto_allocate_oldest_first, create_payment

User = get_user_model()
PASSWORD = "SecretPass123!"
Q = Decimal("0.01")


@pytest.fixture
def api_client():
    return APIClient()


def _auth(client, user, organization):
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(organization.id)
    return client


@pytest.fixture
def org_owner(db):
    org = Organization.objects.create(name="Fin Co", slug="fin-co")
    owner = User.objects.create_user(email="fin@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(organization=org, name="Fin Cari", code="F-1")
    return org, owner, customer


def test_decimal_0_1_plus_0_2_not_float():
    """NP-174: never use binary float for money."""
    bad = 0.1 + 0.2
    assert bad != 0.3  # classic float trap
    good = (Decimal("0.1") + Decimal("0.2")).quantize(Q)
    assert good == Decimal("0.30")


def test_kurus_rounding_half_up():
    assert (Decimal("10.005")).quantize(Q, rounding=ROUND_HALF_UP) == Decimal("10.01")
    assert (Decimal("10.004")).quantize(Q, rounding=ROUND_HALF_UP) == Decimal("10.00")


def test_compute_status_partial_and_overpay_remaining():
    today = date(2026, 7, 31)
    total = Decimal("100.00")
    assert (
        compute_invoice_status(
            total_amount=total, remaining_amount=Decimal("40.00"), due_date=today, as_of=today
        )
        == InvoiceStatus.PARTIALLY_PAID
    )
    # remaining clamped to zero → PAID even if "over-allocated" conceptually
    assert (
        compute_invoice_status(
            total_amount=total, remaining_amount=Decimal("0.00"), due_date=today, as_of=today
        )
        == InvoiceStatus.PAID
    )
    assert (
        compute_invoice_status(
            total_amount=total, remaining_amount=Decimal("-5.00"), due_date=today, as_of=today
        )
        == InvoiceStatus.PAID
    )


@pytest.mark.django_db
def test_partial_payment_leaves_invoice_partially_paid(api_client, org_owner):
    """NP-170/174: partial payment create path."""
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="PART-1",
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 8, 1),
        total_amount=Decimal("100.00"),
        subtotal_amount=Decimal("100.00"),
        status=InvoiceStatus.OPEN,
    )
    create = client.post(
        "/api/payments/",
        {
            "customer": customer.id,
            "payment_date": "2026-07-15",
            "amount": "40.00",
            "currency": "TRY",
            "allocations": [{"invoice_id": inv.id, "amount": "40.00"}],
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED, create.data
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PARTIALLY_PAID
    assert inv.remaining_amount() == Decimal("60.00")


@pytest.mark.django_db
def test_multiple_payments_same_invoice_then_paid(org_owner):
    """NP-174: aynı faturaya birden fazla ödeme."""
    org, owner, customer = org_owner
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="MULTI-1",
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 8, 1),
        total_amount=Decimal("100.00"),
        subtotal_amount=Decimal("100.00"),
        status=InvoiceStatus.OPEN,
    )
    create_payment(
        organization=org,
        customer=customer,
        payment_date=date(2026, 7, 10),
        amount=Decimal("30.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("30.00")}],
    )
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PARTIALLY_PAID
    assert inv.remaining_amount() == Decimal("70.00")

    create_payment(
        organization=org,
        customer=customer,
        payment_date=date(2026, 7, 12),
        amount=Decimal("70.00"),
        recorded_by=owner,
        allocations=[{"invoice_id": inv.id, "amount": Decimal("70.00")}],
    )
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    assert inv.remaining_amount() == ZERO


@pytest.mark.django_db
def test_payment_exceeds_invoice_leaves_unallocated(org_owner):
    """NP-174: fatura tutarından fazla ödeme → unallocated."""
    org, owner, customer = org_owner
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OVER-1",
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 8, 1),
        total_amount=Decimal("50.00"),
        subtotal_amount=Decimal("50.00"),
        status=InvoiceStatus.OPEN,
    )
    payment = create_payment(
        organization=org,
        customer=customer,
        payment_date=date(2026, 7, 10),
        amount=Decimal("80.00"),
        recorded_by=owner,
        auto_allocate=True,
    )
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    assert payment.unallocated_amount == Decimal("30.00")


@pytest.mark.django_db
def test_different_currency_payments_isolated(org_owner):
    """NP-174: farklı para birimi — auto allocate aynı currency."""
    org, owner, customer = org_owner
    inv_try = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="TRY-1",
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 8, 1),
        total_amount=Decimal("100.00"),
        currency="TRY",
        status=InvoiceStatus.OPEN,
    )
    inv_usd = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="USD-1",
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 8, 1),
        total_amount=Decimal("100.00"),
        currency="USD",
        status=InvoiceStatus.OPEN,
    )
    plan = auto_allocate_oldest_first(
        organization=org,
        customer=customer,
        payment_amount=Decimal("100.00"),
        currency="USD",
    )
    ids = {row["invoice_id"] for row in plan}
    assert inv_usd.id in ids
    assert inv_try.id not in ids


@pytest.mark.django_db
def test_payment_cancel_reopens_invoice(api_client, org_owner):
    """NP-170: ödeme iptali."""
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="CAN-1",
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 8, 1),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OPEN,
    )
    create = client.post(
        "/api/payments/",
        {
            "customer": customer.id,
            "payment_date": "2026-07-15",
            "amount": "100.00",
            "allocations": [{"invoice_id": inv.id, "amount": "100.00"}],
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID

    cancel = client.post(
        f"/api/payments/{create.data['id']}/cancel/",
        {"reason": "test"},
        format="json",
    )
    assert cancel.status_code == status.HTTP_200_OK
    inv.refresh_from_db()
    assert inv.status in {InvoiceStatus.OPEN, InvoiceStatus.OVERDUE}
    assert inv.remaining_amount() == Decimal("100.00")
    assert Payment.objects.get(pk=create.data["id"]).cancelled_at is not None
