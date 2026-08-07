"""NP-153 — cross-tenant / IDOR security tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.imports.models import ImportJob, ImportJobStatus, ImportType
from apps.imports.schema import CANONICAL_COLUMNS
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
def two_orgs(db):
    org_a = Organization.objects.create(name="Sec A", slug="sec-a")
    org_b = Organization.objects.create(name="Sec B", slug="sec-b")
    user_a = User.objects.create_user(email="sec-a@example.com", password=PASSWORD)
    user_b = User.objects.create_user(email="sec-b@example.com", password=PASSWORD)
    Membership.objects.create(organization=org_a, user=user_a, role=Role.OWNER, is_active=True)
    Membership.objects.create(organization=org_b, user=user_b, role=Role.OWNER, is_active=True)
    cust_a = Customer.objects.create(organization=org_a, name="A Cari", code="SA-1")
    cust_b = Customer.objects.create(organization=org_b, name="B Secret", code="SB-1")
    inv_a = Invoice.objects.create(
        organization=org_a,
        customer=cust_a,
        number="SA-INV-1",
        invoice_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OPEN,
    )
    inv_b = Invoice.objects.create(
        organization=org_b,
        customer=cust_b,
        number="SB-INV-SECRET",
        invoice_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("999.00"),
        status=InvoiceStatus.OPEN,
    )
    job_b = ImportJob.objects.create(
        organization=org_b,
        import_type=ImportType.INVOICES,
        status=ImportJobStatus.READY,
        original_filename="secret.xlsx",
        stored_path="/tmp/does-not-matter.xlsx",
        file_hash="abc",
        headers=list(CANONICAL_COLUMNS),
        uploaded_by=user_b,
    )
    return {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": user_a,
        "user_b": user_b,
        "cust_a": cust_a,
        "cust_b": cust_b,
        "inv_a": inv_a,
        "inv_b": inv_b,
        "job_b": job_b,
    }


@pytest.mark.django_db
def test_cannot_read_other_org_customer(api_client, two_orgs):
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    response = client.get(f"/api/customers/{two_orgs['cust_b'].id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "b secret" not in str(response.data).lower()


@pytest.mark.django_db
def test_cannot_edit_other_org_invoice(api_client, two_orgs):
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    response = client.patch(
        f"/api/invoices/{two_orgs['inv_b'].id}/",
        {"description": "hacked"},
        format="json",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    two_orgs["inv_b"].refresh_from_db()
    assert two_orgs["inv_b"].description != "hacked"


@pytest.mark.django_db
def test_cannot_download_other_org_import_export(api_client, two_orgs):
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    response = client.get(f"/api/imports/{two_orgs['job_b'].id}/errors/export/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_cannot_read_other_org_import_job(api_client, two_orgs):
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    response = client.get(f"/api/imports/{two_orgs['job_b'].id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_idor_guessed_ids_do_not_leak(api_client, two_orgs):
    """Sequential ID guessing must not reveal foreign tenant data."""
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    guessed = [
        two_orgs["cust_b"].id,
        two_orgs["inv_b"].id,
        two_orgs["job_b"].id,
        999_999_999,
    ]
    for pk in guessed:
        for path in (
            f"/api/customers/{pk}/",
            f"/api/invoices/{pk}/",
            f"/api/imports/{pk}/",
            f"/api/imports/{pk}/errors/export/",
        ):
            response = client.get(path)
            assert response.status_code in {
                status.HTTP_404_NOT_FOUND,
                status.HTTP_403_FORBIDDEN,
            }, path
            body = str(response.data).lower()
            assert "sb-inv-secret" not in body
            assert "b secret" not in body


@pytest.mark.django_db
def test_upload_rejects_mismatched_mime(api_client, two_orgs):
    client = _auth(api_client, two_orgs["user_a"], two_orgs["org_a"])
    wb = Workbook()
    ws = wb.active
    ws.append(list(CANONICAL_COLUMNS))
    buf = __import__("io").BytesIO()
    wb.save(buf)
    # Claim CSV but send Excel bytes — must fail MIME/content check
    response = client.post(
        "/api/imports/invoices/upload/",
        {
            "file": SimpleUploadedFile(
                "rows.csv",
                buf.getvalue(),
                content_type="text/csv",
            )
        },
        format="multipart",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "invalid_file_type"
