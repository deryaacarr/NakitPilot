"""NP-251–254 dispute workflow, attachments, balances, report."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.collections.dispute_workflow import transition_dispute
from apps.collections.models import (
    Dispute,
    DisputeAttachmentKind,
    DisputeCategory,
    DisputeStatus,
)
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.messaging.frequency import check_frequency
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def ctx(db):
    org = Organization.objects.create(name="D251", slug="d251")
    user = User.objects.create_user(email="d251@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=user, role=Role.ADMIN, is_active=True)
    customer = Customer.objects.create(organization=org, name="Cust", code="C1")
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-D251",
        invoice_date=date.today() - timedelta(days=40),
        due_date=date.today() - timedelta(days=10),
        total_amount=Decimal("5000.00"),
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
def test_workflow_transitions(ctx):
    org, user, customer, inv, client = ctx
    create = client.post(
        "/api/disputes/",
        {
            "customer": customer.id,
            "invoice": inv.id,
            "category": DisputeCategory.PRICE_DISPUTE,
            "amount": "5000.00",
            "description": "Fiyat",
        },
        format="json",
    )
    assert create.status_code == 201, create.content
    did = create.data["id"]
    tr = client.post(
        f"/api/disputes/{did}/transition/",
        {"status": DisputeStatus.UNDER_REVIEW, "note": "İncelemeye alındı"},
        format="json",
    )
    assert tr.status_code == 200
    assert tr.data["status"] == DisputeStatus.UNDER_REVIEW
    wait = client.post(
        f"/api/disputes/{did}/transition/",
        {"status": DisputeStatus.WAITING_CUSTOMER},
        format="json",
    )
    assert wait.status_code == 200
    statuses = client.get("/api/disputes/statuses/")
    assert DisputeStatus.WAITING_INTERNAL in {
        r["value"] for r in statuses.data["results"]
    }


@pytest.mark.django_db
def test_disputed_balance_split_and_auto_block(ctx):
    org, user, customer, inv, _ = ctx
    before = customer_financial_metrics(customer)
    assert before["overdue_balance"] == Decimal("5000.00")
    assert before["disputed_balance"] == Decimal("0.00")

    Dispute.objects.create(
        organization=org,
        customer=customer,
        invoice=inv,
        category=DisputeCategory.INVOICE_ERROR,
        status=DisputeStatus.OPEN,
        amount=Decimal("5000.00"),
    )
    after = customer_financial_metrics(customer)
    assert after["disputed_balance"] == Decimal("5000.00")
    assert after["overdue_balance"] == Decimal("0.00")
    assert after["open_balance"] == Decimal("0.00")

    freq = check_frequency(customer, is_automatic=True, invoice_id=inv.id)
    assert freq.allowed is False
    assert freq.code == "invoice_disputed"


@pytest.mark.django_db
def test_attachment_upload(ctx):
    org, user, customer, inv, client = ctx
    create = client.post(
        "/api/disputes/",
        {
            "customer": customer.id,
            "invoice": inv.id,
            "category": DisputeCategory.OTHER,
            "description": "Ek test",
        },
        format="json",
    )
    did = create.data["id"]
    upload = SimpleUploadedFile(
        "kanit.pdf", b"%PDF-1.4 test content", content_type="application/pdf"
    )
    resp = client.post(
        f"/api/disputes/{did}/attachments/",
        {"kind": DisputeAttachmentKind.PDF, "file": upload},
        format="multipart",
    )
    assert resp.status_code == 201, resp.content
    assert resp.data["kind"] == "PDF"
    listing = client.get(f"/api/disputes/{did}/attachments/")
    assert len(listing.data["results"]) == 1


@pytest.mark.django_db
def test_resolution_report(ctx):
    org, user, customer, inv, client = ctx
    d = Dispute.objects.create(
        organization=org,
        customer=customer,
        invoice=inv,
        category=DisputeCategory.DUPLICATE_INVOICE,
        status=DisputeStatus.OPEN,
        amount=Decimal("1000.00"),
        opened_at=timezone.now() - timedelta(days=5),
    )
    transition_dispute(
        d, to_status=DisputeStatus.RESOLVED, actor=user, resolution_note="OK"
    )
    report = client.get("/api/disputes/resolution-report/")
    assert report.status_code == 200
    assert report.data["resolved_count"] >= 1
    assert "avg_resolution_hours" in report.data
    assert len(report.data["by_category"]) >= 1
