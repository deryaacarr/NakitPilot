"""NP-170 — payments / promises tenant isolation."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.collections.models import PaymentPromise, PaymentPromiseStatus
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role
from apps.payments.models import Payment

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
def two_orgs(db):
    org_a = Organization.objects.create(name="Ten A", slug="ten-a")
    org_b = Organization.objects.create(name="Ten B", slug="ten-b")
    user_a = User.objects.create_user(email="ten-a@example.com", password=PASSWORD)
    user_b = User.objects.create_user(email="ten-b@example.com", password=PASSWORD)
    Membership.objects.create(organization=org_a, user=user_a, role=Role.OWNER, is_active=True)
    Membership.objects.create(organization=org_b, user=user_b, role=Role.OWNER, is_active=True)
    cust_b = Customer.objects.create(organization=org_b, name="Secret", code="TB-1")
    inv_b = Invoice.objects.create(
        organization=org_b,
        customer=cust_b,
        number="TB-INV",
        invoice_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OPEN,
    )
    payment_b = Payment.objects.create(
        organization=org_b,
        customer=cust_b,
        payment_date=date.today(),
        amount=Decimal("50.00"),
        unallocated_amount=Decimal("50.00"),
        recorded_by=user_b,
    )
    promise_b = PaymentPromise.objects.create(
        organization=org_b,
        customer=cust_b,
        invoice=inv_b,
        promised_date=date.today(),
        amount=Decimal("50.00"),
        status=PaymentPromiseStatus.PENDING,
        created_by=user_b,
    )
    return {
        "org_a": org_a,
        "user_a": user_a,
        "payment_b": payment_b,
        "promise_b": promise_b,
    }


@pytest.mark.django_db
def test_cannot_read_or_cancel_other_org_payment(api_client, two_orgs):
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    pk = two_orgs["payment_b"].id
    assert client.get(f"/api/payments/{pk}/").status_code == status.HTTP_404_NOT_FOUND
    assert (
        client.post(f"/api/payments/{pk}/cancel/", {"reason": "x"}, format="json").status_code
        == status.HTTP_404_NOT_FOUND
    )


@pytest.mark.django_db
def test_cannot_read_other_org_promise(api_client, two_orgs):
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    pk = two_orgs["promise_b"].id
    assert client.get(f"/api/payment-promises/{pk}/").status_code == status.HTTP_404_NOT_FOUND
