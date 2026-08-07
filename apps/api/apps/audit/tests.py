"""NP-150 audit coverage tests."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.customers.models import Customer
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
    org = Organization.objects.create(name="Audit Co", slug="audit-co")
    owner = User.objects.create_user(email="audit@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.mark.django_db
def test_customer_and_invoice_audit(api_client, org_owner):
    org, owner = org_owner
    client = _auth(api_client, owner, org)

    created = client.post(
        "/api/customers/",
        {"name": "Audit Cari", "code": "AUD-1"},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert AuditLog.objects.filter(action="customer.create", entity_id=str(created.data["id"])).exists()

    patched = client.patch(
        f"/api/customers/{created.data['id']}/",
        {"name": "Audit Cari 2"},
        format="json",
    )
    assert patched.status_code == status.HTTP_200_OK
    assert AuditLog.objects.filter(action="customer.update").exists()

    customer = Customer.objects.get(pk=created.data["id"])
    api_inv = client.post(
        "/api/invoices/",
        {
            "customer": customer.id,
            "number": "AUD-INV-2",
            "invoice_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
            "total_amount": "75.00",
            "currency": "TRY",
        },
        format="json",
    )
    assert api_inv.status_code == status.HTTP_201_CREATED
    assert AuditLog.objects.filter(action="invoice.create", entity_id=str(api_inv.data["id"])).exists()

    cancel = client.post(f"/api/invoices/{api_inv.data['id']}/cancel/")
    assert cancel.status_code == status.HTTP_200_OK
    assert AuditLog.objects.filter(action="invoice.cancel").exists()

    detail = client.get(f"/api/invoices/{api_inv.data['id']}/")
    assert detail.status_code == status.HTTP_200_OK
    assert any(row["action"] == "invoice.cancel" for row in detail.data.get("audit_log", []))

    # role change
    member = Membership.objects.get(organization=org, user=owner)
    # create viewer to change
    viewer = User.objects.create_user(email="viewer-audit@example.com", password=PASSWORD)
    m = Membership.objects.create(
        organization=org, user=viewer, role=Role.VIEWER, is_active=True
    )
    role_change = client.patch(
        f"/api/organizations/{org.id}/memberships/{m.id}/",
        {"role": Role.FINANCE_MANAGER, "user_id": viewer.id},
        format="json",
    )
    assert role_change.status_code == status.HTTP_200_OK
    assert AuditLog.objects.filter(action="membership.role_change").exists()
