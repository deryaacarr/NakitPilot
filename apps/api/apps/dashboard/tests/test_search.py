from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.collections.models import (
    CollectionTask,
    CollectionTaskStatus,
    CollectionTaskType,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role
from apps.payments.models import Payment, PaymentMethod

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
def search_setup(db):
    org = Organization.objects.create(name="Search Co", slug="search-co")
    user = User.objects.create_user(email="search@test.local", password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(
        organization=org,
        name="ABC Elektrik",
        code="ABC-1",
        tax_number="1234567890",
        phone="05551234567",
    )
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-2026-184",
        invoice_date="2026-01-01",
        due_date="2026-02-01",
        total_amount=Decimal("1000.00"),
        status=InvoiceStatus.OPEN,
    )
    CollectionTask.objects.create(
        organization=org,
        customer=customer,
        title="Tahsilat araması",
        due_date="2026-08-08",
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.OPEN,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date="2026-08-10",
        amount=Decimal("500.00"),
        status=PaymentPromiseStatus.PENDING,
        notes="hafta sonu ödeyecek",
    )
    Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date="2026-08-01",
        amount=Decimal("250.00"),
        currency="TRY",
        method=PaymentMethod.BANK_TRANSFER,
        reference="EFT-99",
        recorded_by=user,
    )
    return org, user, customer


@pytest.mark.django_db
def test_global_search_groups(api_client, search_setup):
    org, user, _customer = search_setup
    client = _auth(api_client, user, org)

    by_name = client.get("/api/search/", {"q": "ABC"})
    assert by_name.status_code == 200
    body = by_name.json()
    assert len(body["customers"]) >= 1
    assert body["customers"][0]["label"] == "ABC Elektrik"
    assert body["customers"][0]["href"].startswith("/customers/")

    by_tax = client.get("/api/search/", {"q": "1234567890"})
    assert by_tax.status_code == 200
    assert len(by_tax.json()["customers"]) >= 1

    by_invoice = client.get("/api/search/", {"q": "INV-2026"})
    assert by_invoice.status_code == 200
    assert any(i["label"] == "INV-2026-184" for i in by_invoice.json()["invoices"])

    by_phone = client.get("/api/search/", {"q": "0555123"})
    assert by_phone.status_code == 200
    assert len(by_phone.json()["customers"]) >= 1

    by_task = client.get("/api/search/", {"q": "Tahsilat"})
    assert by_task.status_code == 200
    assert len(by_task.json()["tasks"]) >= 1

    by_payment = client.get("/api/search/", {"q": "EFT-99"})
    assert by_payment.status_code == 200
    assert len(by_payment.json()["payments"]) >= 1

    by_promise = client.get("/api/search/", {"q": "hafta sonu"})
    assert by_promise.status_code == 200
    assert len(by_promise.json()["promises"]) >= 1


@pytest.mark.django_db
def test_global_search_short_query(api_client, search_setup):
    org, user, _ = search_setup
    client = _auth(api_client, user, org)
    response = client.get("/api/search/", {"q": "A"})
    assert response.status_code == 200
    body = response.json()
    assert body["customers"] == []
    assert body["invoices"] == []
