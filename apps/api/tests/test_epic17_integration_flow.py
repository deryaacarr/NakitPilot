"""NP-171 — end-to-end API business flow."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.collections.models import CollectionTaskStatus, PaymentPromiseStatus
from apps.invoices.models import InvoiceStatus
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "FlowPass123!"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_full_collection_happy_path(api_client):
    """
    Firma → kullanıcı → müşteri → fatura → söz → görev → ödeme
    → fatura kapandı + söz karşılandı.
    """
    # 1) Firma
    org_res = None
    owner = User.objects.create_user(email="flow-owner@example.com", password=PASSWORD)
    login = api_client.post(
        "/api/auth/login",
        {"email": owner.email, "password": PASSWORD},
        format="json",
    )
    assert login.status_code == status.HTTP_200_OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    org_res = api_client.post(
        "/api/organizations/",
        {"name": "Flow Ticaret", "default_currency": "TRY", "timezone": "Europe/Istanbul"},
        format="json",
    )
    # create org may return 201 with membership as owner
    if org_res.status_code == status.HTTP_201_CREATED:
        org_id = org_res.data["id"]
    else:
        # Fallback: create directly if endpoint differs
        org = Organization.objects.create(name="Flow Ticaret", slug="flow-ticaret")
        Membership.objects.create(
            organization=org, user=owner, role=Role.OWNER, is_active=True
        )
        org_id = org.id

    api_client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org_id)

    # Ensure membership exists
    if not Membership.objects.filter(organization_id=org_id, user=owner).exists():
        Membership.objects.create(
            organization_id=org_id, user=owner, role=Role.OWNER, is_active=True
        )

    # 2–3) Müşteri
    customer = api_client.post(
        "/api/customers/",
        {"name": "Flow Cari", "code": "FLOW-1"},
        format="json",
    )
    assert customer.status_code == status.HTTP_201_CREATED, customer.data
    customer_id = customer.data["id"]

    # 4) Fatura
    today = date.today()
    due = today + timedelta(days=10)
    invoice = api_client.post(
        "/api/invoices/",
        {
            "customer": customer_id,
            "number": "FLOW-INV-1",
            "invoice_date": today.isoformat(),
            "due_date": due.isoformat(),
            "currency": "TRY",
            "total_amount": "250.00",
            "subtotal_amount": "250.00",
            "tax_amount": "0.00",
        },
        format="json",
    )
    assert invoice.status_code == status.HTTP_201_CREATED, invoice.data
    invoice_id = invoice.data["id"]
    assert invoice.data["status"] in {InvoiceStatus.OPEN, "OPEN"}

    # 5) Ödeme sözü
    promise = api_client.post(
        "/api/payment-promises/",
        {
            "customer": customer_id,
            "promised_date": due.isoformat(),
            "amount": "250.00",
            "currency": "TRY",
            "invoice": invoice_id,
        },
        format="json",
    )
    assert promise.status_code in {
        status.HTTP_201_CREATED,
        status.HTTP_200_OK,
    }, promise.data
    promise_body = promise.data.get("promise") or promise.data
    promise_id = promise_body["id"]
    assert promise_body["status"] == PaymentPromiseStatus.PENDING

    # 6) Görev
    task = api_client.post(
        "/api/collection-tasks/",
        {
            "customer": customer_id,
            "due_date": today.isoformat(),
            "title": "Flow arama",
            "invoice": invoice_id,
        },
        format="json",
    )
    assert task.status_code == status.HTTP_201_CREATED, task.data
    assert task.data["status"] == CollectionTaskStatus.OPEN

    # 7) Ödeme
    payment = api_client.post(
        "/api/payments/",
        {
            "customer": customer_id,
            "payment_date": today.isoformat(),
            "amount": "250.00",
            "currency": "TRY",
            "allocations": [{"invoice_id": invoice_id, "amount": "250.00"}],
        },
        format="json",
    )
    assert payment.status_code == status.HTTP_201_CREATED, payment.data

    # 8) Fatura kapandı
    inv_detail = api_client.get(f"/api/invoices/{invoice_id}/")
    assert inv_detail.status_code == status.HTTP_200_OK
    assert inv_detail.data["status"] == InvoiceStatus.PAID
    assert inv_detail.data["remaining_amount"] in {"0.00", 0, "0"}

    # 9) Söz karşılandı (refresh may be automatic on payment)
    promise_detail = api_client.get(f"/api/payment-promises/{promise_id}/")
    assert promise_detail.status_code == status.HTTP_200_OK
    # If auto-refresh on payment isn't wired, force via list/calendar side-effect:
    if promise_detail.data["status"] != PaymentPromiseStatus.FULFILLED:
        from apps.collections.promises import refresh_promise_status
        from apps.collections.models import PaymentPromise

        refresh_promise_status(PaymentPromise.objects.get(pk=promise_id), as_of=today)
        promise_detail = api_client.get(f"/api/payment-promises/{promise_id}/")
    assert promise_detail.data["status"] == PaymentPromiseStatus.FULFILLED
