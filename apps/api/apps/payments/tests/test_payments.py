from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role
from apps.payments.models import Payment
from apps.risk.models import RiskSnapshot

User = get_user_model()
PASSWORD = "SecretPass123!"


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
    org = Organization.objects.create(name="Pay Co", slug="pay-co")
    owner = User.objects.create_user(email="pay-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(organization=org, name="Cari Pay", code="P-1")
    return org, owner, customer


def _invoice(org, customer, *, number, total, due, status=InvoiceStatus.OPEN):
    return Invoice.objects.create(
        organization=org,
        customer=customer,
        number=number,
        invoice_date=date(2026, 1, 1),
        due_date=due,
        total_amount=Decimal(total),
        subtotal_amount=Decimal(total),
        status=status,
    )


@pytest.mark.django_db
def test_payment_crud_list_retrieve(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inv = _invoice(org, customer, number="A", total="100.00", due=date(2026, 7, 1))

    create = client.post(
        "/api/payments/",
        {
            "customer": customer.id,
            "payment_date": "2026-07-15",
            "amount": "100.00",
            "method": "BANK_TRANSFER",
            "allocations": [{"invoice_id": inv.id, "amount": "100.00"}],
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED, create.data
    payment_id = create.data["id"]
    assert create.data["unallocated_amount"] == "0.00"
    assert len(create.data["allocations"]) == 1

    listing = client.get("/api/payments/")
    assert listing.status_code == status.HTTP_200_OK
    assert listing.data["count"] == 1

    detail = client.get(f"/api/payments/{payment_id}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["customer_name"] == "Cari Pay"


@pytest.mark.django_db
def test_manual_allocation_split(api_client, org_owner):
    """NP-071: 100k → A 60k + B 40k."""
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inv_a = _invoice(org, customer, number="FA", total="60000.00", due=date(2026, 6, 1))
    inv_b = _invoice(org, customer, number="FB", total="40000.00", due=date(2026, 7, 1))

    create = client.post(
        "/api/payments/",
        {
            "customer": customer.id,
            "payment_date": "2026-07-20",
            "amount": "100000.00",
            "allocations": [
                {"invoice_id": inv_a.id, "amount": "60000.00"},
                {"invoice_id": inv_b.id, "amount": "40000.00"},
            ],
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED, create.data
    assert create.data["unallocated_amount"] == "0.00"

    inv_a.refresh_from_db()
    inv_b.refresh_from_db()
    assert inv_a.status == InvoiceStatus.PAID
    assert inv_b.status == InvoiceStatus.PAID
    assert inv_a.remaining_amount() == Decimal("0.00")


@pytest.mark.django_db
def test_auto_allocate_oldest_first_with_leftover(api_client, org_owner):
    """NP-072: oldest due first; leftover → unallocated."""
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    older = _invoice(org, customer, number="OLD", total="60.00", due=date(2026, 1, 10))
    newer = _invoice(org, customer, number="NEW", total="40.00", due=date(2026, 3, 10))

    create = client.post(
        "/api/payments/",
        {
            "customer": customer.id,
            "payment_date": "2026-07-20",
            "amount": "120.00",
            "auto_allocate": True,
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED, create.data
    assert create.data["unallocated_amount"] == "20.00"
    assert {a["invoice"] for a in create.data["allocations"]} == {older.id, newer.id}

    older.refresh_from_db()
    newer.refresh_from_db()
    assert older.status == InvoiceStatus.PAID
    assert newer.status == InvoiceStatus.PAID


@pytest.mark.django_db
def test_replace_allocations_manual(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inv_a = _invoice(org, customer, number="RA", total="70.00", due=date(2026, 5, 1))
    inv_b = _invoice(org, customer, number="RB", total="30.00", due=date(2026, 6, 1))

    create = client.post(
        "/api/payments/",
        {
            "customer": customer.id,
            "payment_date": "2026-07-20",
            "amount": "100.00",
            "auto_allocate": True,
        },
        format="json",
    )
    payment_id = create.data["id"]

    # User changes distribution: all to A partially leaving B open? amount 70+30=100
    updated = client.put(
        f"/api/payments/{payment_id}/allocations/",
        {
            "allocations": [
                {"invoice_id": inv_a.id, "amount": "50.00"},
                {"invoice_id": inv_b.id, "amount": "30.00"},
            ]
        },
        format="json",
    )
    assert updated.status_code == status.HTTP_200_OK, updated.data
    assert updated.data["unallocated_amount"] == "20.00"
    inv_a.refresh_from_db()
    assert inv_a.status == InvoiceStatus.PARTIALLY_PAID


@pytest.mark.django_db
def test_post_payment_side_effects(api_client, org_owner):
    """NP-073: audit + promise + risk."""
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inv = _invoice(org, customer, number="FX", total="100.00", due=date(2026, 7, 1))
    promise = PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=date(2026, 7, 10),
        amount=Decimal("100.00"),
        status=PaymentPromiseStatus.PENDING,
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

    promise.refresh_from_db()
    assert promise.status == PaymentPromiseStatus.FULFILLED
    assert AuditLog.objects.filter(entity_type="Payment", action="payment.create").exists()
    assert RiskSnapshot.objects.filter(customer=customer).exists()
    customer.refresh_from_db()
    # risk fields updated
    assert customer.risk_score is not None


@pytest.mark.django_db
def test_soft_cancel_recalculates_invoices(api_client, org_owner):
    """NP-074."""
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inv = _invoice(org, customer, number="CX", total="80.00", due=date(2026, 8, 1))

    create = client.post(
        "/api/payments/",
        {
            "customer": customer.id,
            "payment_date": "2026-07-15",
            "amount": "80.00",
            "allocations": [{"invoice_id": inv.id, "amount": "80.00"}],
        },
        format="json",
    )
    payment_id = create.data["id"]
    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID

    cancel = client.post(
        f"/api/payments/{payment_id}/cancel/",
        {"reason": "Yanlış kayıt"},
        format="json",
    )
    assert cancel.status_code == status.HTTP_200_OK, cancel.data
    assert cancel.data["cancelled_at"] is not None
    assert cancel.data["cancellation_reason"] == "Yanlış kayıt"
    assert Payment.objects.filter(pk=payment_id).exists()

    inv.refresh_from_db()
    assert inv.remaining_amount() == Decimal("80.00")
    assert inv.status in {InvoiceStatus.OPEN, InvoiceStatus.OVERDUE}
    assert AuditLog.objects.filter(action="payment.cancel").exists()
