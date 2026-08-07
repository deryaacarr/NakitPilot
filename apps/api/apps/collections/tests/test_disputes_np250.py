"""NP-250 dispute model API tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.collections.models import Dispute, DisputeCategory, DisputeStatus
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def dispute_ctx(db):
    org = Organization.objects.create(name="Dispute Co", slug="dispute-co-np250")
    user = User.objects.create_user(email="disp@example.com", password=PASSWORD)
    Membership.objects.create(
        organization=org, user=user, role=Role.ADMIN, is_active=True
    )
    customer = Customer.objects.create(
        organization=org, name="İtiraz Müşteri", code="D-1"
    )
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-D-1",
        invoice_date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=5),
        total_amount=Decimal("2500.00"),
        status=InvoiceStatus.OVERDUE,
    )
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return org, user, customer, inv, client


@pytest.mark.django_db
def test_create_list_resolve_dispute(dispute_ctx):
    _, _, customer, inv, client = dispute_ctx
    create = client.post(
        "/api/disputes/",
        {
            "customer": customer.id,
            "invoice": inv.id,
            "category": DisputeCategory.DUPLICATE_INVOICE,
            "amount": "2500.00",
            "description": "Aynı fatura iki kez kesilmiş",
        },
        format="json",
    )
    assert create.status_code == 201, create.content
    dispute_id = create.data["id"]
    assert create.data["status"] == DisputeStatus.OPEN
    assert create.data["category_label"] == "Mükerrer fatura"

    listing = client.get(f"/api/disputes/?customer_id={customer.id}&open=true")
    assert listing.status_code == 200
    rows = listing.data["results"] if isinstance(listing.data, dict) else listing.data
    assert len(rows) == 1

    resolve = client.post(
        f"/api/disputes/{dispute_id}/resolve/",
        {"status": DisputeStatus.RESOLVED, "resolution_note": "İptal edildi"},
        format="json",
    )
    assert resolve.status_code == 200
    assert resolve.data["status"] == DisputeStatus.RESOLVED
    assert resolve.data["resolution_note"] == "İptal edildi"
    assert Dispute.objects.get(pk=dispute_id).resolved_at is not None


@pytest.mark.django_db
def test_dispute_categories(dispute_ctx):
    _, _, _, _, client = dispute_ctx
    resp = client.get("/api/disputes/categories/")
    assert resp.status_code == 200
    values = {r["value"] for r in resp.data["results"]}
    assert DisputeCategory.INVOICE_ERROR in values
    assert DisputeCategory.OTHER in values
