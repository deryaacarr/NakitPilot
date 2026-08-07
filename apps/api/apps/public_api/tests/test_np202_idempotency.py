"""NP-202 — Idempotency-Key for public API writes."""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.api_keys.services import create_api_key
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role
from apps.payments.models import Payment
from apps.public_api.models import IdempotencyRecord

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def setup(db):
    org = Organization.objects.create(name="NP202 Org", slug="np202-org")
    owner = User.objects.create_user(email="np202-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    _key, raw = create_api_key(
        organization=org,
        name="Idempotency key",
        scopes=[
            "customers:read",
            "customers:write",
            "invoices:read",
            "invoices:write",
            "payments:write",
        ],
        created_by=owner,
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    return org, client


@pytest.mark.django_db
def test_missing_idempotency_key_rejected(setup):
    _org, client = setup
    response = client.post(
        "/api/v1/customers",
        {"code": "A", "name": "No Key"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Idempotency-Key" in response.data["detail"]


@pytest.mark.django_db
def test_customer_replay_same_key_no_duplicate(setup):
    _org, client = setup
    payload = {"code": "C-IDEM", "name": "Idempotent Customer", "payment_term_days": 30}
    headers = {"HTTP_IDEMPOTENCY_KEY": "external-system-customer-1"}

    first = client.post("/api/v1/customers", payload, format="json", **headers)
    assert first.status_code == 201
    assert first["Idempotent-Replayed"] == "false"
    customer_id = first.data["id"]

    second = client.post("/api/v1/customers", payload, format="json", **headers)
    assert second.status_code == 201
    assert second["Idempotent-Replayed"] == "true"
    assert second.data["id"] == customer_id
    assert Customer.objects.filter(code="C-IDEM").count() == 1


@pytest.mark.django_db
def test_same_key_different_body_conflicts(setup):
    _org, client = setup
    headers = {"HTTP_IDEMPOTENCY_KEY": "external-system-customer-2"}
    first = client.post(
        "/api/v1/customers",
        {"code": "C-A", "name": "A", "payment_term_days": 10},
        format="json",
        **headers,
    )
    assert first.status_code == 201

    conflict = client.post(
        "/api/v1/customers",
        {"code": "C-B", "name": "B", "payment_term_days": 10},
        format="json",
        **headers,
    )
    assert conflict.status_code == status.HTTP_409_CONFLICT
    assert conflict.data["code"] == "idempotency_key_reuse"
    assert Customer.objects.filter(code__in=["C-A", "C-B"]).count() == 1


@pytest.mark.django_db
def test_invoice_and_payment_idempotency(setup):
    org, client = setup
    customer = Customer.objects.create(
        organization=org, code="PAY", name="Pay Customer", payment_term_days=15
    )

    inv_payload = {
        "customer": customer.id,
        "number": "IDEM-INV-1",
        "invoice_date": str(date.today()),
        "due_date": str(date.today() + timedelta(days=15)),
        "currency": "TRY",
        "subtotal_amount": "100.00",
        "tax_amount": "0.00",
        "total_amount": "100.00",
        "status": InvoiceStatus.OPEN,
    }
    inv_headers = {"HTTP_IDEMPOTENCY_KEY": "external-system-invoice-99"}
    first_inv = client.post("/api/v1/invoices", inv_payload, format="json", **inv_headers)
    assert first_inv.status_code == 201
    second_inv = client.post("/api/v1/invoices", inv_payload, format="json", **inv_headers)
    assert second_inv.status_code == 201
    assert second_inv.data["id"] == first_inv.data["id"]
    assert Invoice.objects.filter(number="IDEM-INV-1").count() == 1

    pay_payload = {
        "customer": customer.id,
        "payment_date": str(date.today()),
        "amount": "25.00",
        "currency": "TRY",
    }
    pay_headers = {"HTTP_IDEMPOTENCY_KEY": "external-system-payment-1842"}
    first_pay = client.post("/api/v1/payments", pay_payload, format="json", **pay_headers)
    assert first_pay.status_code == 201
    second_pay = client.post("/api/v1/payments", pay_payload, format="json", **pay_headers)
    assert second_pay.status_code == 201
    assert second_pay.data["id"] == first_pay.data["id"]
    assert second_pay["Idempotent-Replayed"] == "true"
    assert Payment.objects.filter(organization=org, amount="25.00").count() == 1
    assert IdempotencyRecord.objects.filter(key="external-system-payment-1842").count() == 1
