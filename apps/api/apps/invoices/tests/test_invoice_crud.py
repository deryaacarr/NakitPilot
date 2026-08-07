import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role

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
    org = Organization.objects.create(name="Inv Co", slug="inv-co")
    owner = User.objects.create_user(email="inv-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(organization=org, name="Cari A", code="C-1")
    return org, owner, customer


@pytest.fixture
def other_org(db):
    org = Organization.objects.create(name="Other Inv", slug="other-inv")
    owner = User.objects.create_user(email="other-inv@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(organization=org, name="Foreign", code="F-1")
    return org, owner, customer


@pytest.mark.django_db
def test_create_list_retrieve_patch(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)

    create = client.post(
        "/api/invoices/",
        {
            "customer": customer.id,
            "number": "FTR-2026-001",
            "invoice_date": "2026-07-01",
            "due_date": "2026-07-31",
            "currency": "try",
            "total_amount": "1500.00",
            "status": "OPEN",
            "description": "Temmuz",
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED
    assert create.data["currency"] == "TRY"
    assert create.data["remaining_amount"] == "1500.00"
    assert create.data["allocated_amount"] == "0.00"
    invoice_id = create.data["id"]

    listing = client.get("/api/invoices/")
    assert listing.status_code == status.HTTP_200_OK
    assert listing.data["count"] == 1

    detail = client.get(f"/api/invoices/{invoice_id}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["number"] == "FTR-2026-001"
    assert detail.data["customer_name"] == "Cari A"

    patch = client.patch(
        f"/api/invoices/{invoice_id}/",
        {"notes": "Güncellendi", "total_amount": "1600.50"},
        format="json",
    )
    assert patch.status_code == status.HTTP_200_OK
    assert patch.data["notes"] == "Güncellendi"
    assert patch.data["total_amount"] == "1600.50"
    assert patch.data["remaining_amount"] == "1600.50"


@pytest.mark.django_db
def test_unique_number_and_negative_amount(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="DUP-1",
        invoice_date="2026-07-01",
        due_date="2026-07-15",
        total_amount="100.00",
        status=InvoiceStatus.OPEN,
    )

    dup = client.post(
        "/api/invoices/",
        {
            "customer": customer.id,
            "number": "DUP-1",
            "invoice_date": "2026-07-02",
            "due_date": "2026-07-20",
            "total_amount": "50.00",
        },
        format="json",
    )
    assert dup.status_code == status.HTTP_400_BAD_REQUEST
    assert "number" in dup.data

    neg = client.post(
        "/api/invoices/",
        {
            "customer": customer.id,
            "number": "NEG-1",
            "invoice_date": "2026-07-02",
            "due_date": "2026-07-20",
            "total_amount": "-10.00",
        },
        format="json",
    )
    assert neg.status_code == status.HTTP_400_BAD_REQUEST
    assert "total_amount" in neg.data


@pytest.mark.django_db
def test_due_date_before_invoice_date(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    response = client.post(
        "/api/invoices/",
        {
            "customer": customer.id,
            "number": "DATE-1",
            "invoice_date": "2026-07-20",
            "due_date": "2026-07-01",
            "total_amount": "10.00",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "due_date" in response.data


@pytest.mark.django_db
def test_cancel_invoice(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    invoice = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="CNL-1",
        invoice_date="2026-07-01",
        due_date="2026-07-15",
        total_amount="200.00",
        status=InvoiceStatus.OPEN,
    )

    response = client.post(f"/api/invoices/{invoice.id}/cancel/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == InvoiceStatus.CANCELLED
    assert response.data["cancelled_at"] is not None

    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.CANCELLED

    again = client.post(f"/api/invoices/{invoice.id}/cancel/")
    assert again.status_code == status.HTTP_400_BAD_REQUEST

    patch = client.patch(
        f"/api/invoices/{invoice.id}/",
        {"notes": "should fail"},
        format="json",
    )
    assert patch.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cannot_cancel_paid(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    invoice = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="PAID-1",
        invoice_date="2026-07-01",
        due_date="2026-07-15",
        total_amount="200.00",
        status=InvoiceStatus.PAID,
    )
    response = client.post(f"/api/invoices/{invoice.id}/cancel/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_tenant_isolation(api_client, org_owner, other_org):
    org_a, owner_a, customer_a = org_owner
    org_b, _owner_b, customer_b = other_org

    foreign = Invoice.objects.create(
        organization=org_b,
        customer=customer_b,
        number="SEC-1",
        invoice_date="2026-07-01",
        due_date="2026-07-15",
        total_amount="999.00",
        status=InvoiceStatus.OPEN,
    )
    Invoice.objects.create(
        organization=org_a,
        customer=customer_a,
        number="OWN-1",
        invoice_date="2026-07-01",
        due_date="2026-07-15",
        total_amount="10.00",
        status=InvoiceStatus.OPEN,
    )

    client = _auth(api_client, owner_a, org_a)
    listing = client.get("/api/invoices/")
    numbers = [row["number"] for row in listing.data["results"]]
    assert numbers == ["OWN-1"]

    detail = client.get(f"/api/invoices/{foreign.id}/")
    assert detail.status_code == status.HTTP_404_NOT_FOUND

    create_foreign_customer = client.post(
        "/api/invoices/",
        {
            "customer": customer_b.id,
            "number": "HACK-1",
            "invoice_date": "2026-07-01",
            "due_date": "2026-07-15",
            "total_amount": "1.00",
        },
        format="json",
    )
    assert create_foreign_customer.status_code == status.HTTP_400_BAD_REQUEST
