from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer, RiskStatus
from apps.invoices.models import Invoice, InvoiceStatus
from apps.reports.models import ExportJob, ExportJobStatus, ReportType
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
    org = Organization.objects.create(name="Report Co", slug="report-co")
    owner = User.objects.create_user(email="report@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(
        organization=org,
        name="Riskli Cari",
        code="R-1",
        risk_status=RiskStatus.HIGH,
        risk_score=60,
        assigned_user=owner,
    )
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="R-INV-1",
        invoice_date=date.today() - timedelta(days=40),
        due_date=date.today() - timedelta(days=20),
        total_amount=Decimal("1000.00"),
        status=InvoiceStatus.OVERDUE,
        assigned_user=owner,
    )
    return org, owner, customer


@pytest.mark.django_db
def test_overdue_preview_and_export(api_client, org_owner, tmp_path, settings):
    settings.PRIVATE_UPLOAD_ROOT = tmp_path / "private"
    org, owner, _customer = org_owner
    client = _auth(api_client, owner, org)

    preview = client.get("/api/reports/overdue-receivables/")
    assert preview.status_code == status.HTTP_200_OK
    assert preview.data["count"] >= 1
    assert "open_balance" in preview.data["results"][0]

    export = client.post(
        "/api/reports/exports/",
        {"report_type": ReportType.OVERDUE_RECEIVABLES, "filters": {}},
        format="json",
    )
    assert export.status_code == status.HTTP_202_ACCEPTED
    assert export.data["status"] == ExportJobStatus.READY
    job_id = export.data["id"]

    download = client.get(f"/api/reports/exports/{job_id}/download/")
    assert download.status_code == status.HTTP_200_OK
    assert download["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.django_db
def test_activity_and_risk_previews(api_client, org_owner):
    org, owner, _customer = org_owner
    client = _auth(api_client, owner, org)

    activity = client.get("/api/reports/collection-activity/?preset=month")
    assert activity.status_code == status.HTTP_200_OK

    risk = client.get("/api/reports/customer-risk/")
    assert risk.status_code == status.HTTP_200_OK
    assert risk.data["count"] >= 1
    assert "risk_score" in risk.data["results"][0]


@pytest.mark.django_db
def test_export_tenant_isolation(api_client, org_owner, db, tmp_path, settings):
    settings.PRIVATE_UPLOAD_ROOT = tmp_path / "private"
    org_a, owner_a, _ = org_owner
    org_b = Organization.objects.create(name="Other", slug="other-rep")
    owner_b = User.objects.create_user(email="other-rep@example.com", password=PASSWORD)
    Membership.objects.create(organization=org_b, user=owner_b, role=Role.OWNER, is_active=True)

    client_a = _auth(api_client, owner_a, org_a)
    created = client_a.post(
        "/api/reports/exports/",
        {"report_type": ReportType.CUSTOMER_RISK, "filters": {}},
        format="json",
    )
    assert created.status_code == status.HTTP_202_ACCEPTED
    job_id = created.data["id"]

    client_b = APIClient()
    _auth(client_b, owner_b, org_b)
    forbidden = client_b.get(f"/api/reports/exports/{job_id}/download/")
    assert forbidden.status_code == status.HTTP_404_NOT_FOUND
    assert ExportJob.objects.filter(pk=job_id, organization=org_a).exists()
