"""EPIC 34/35 — offline sync + legal preparation."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
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
from apps.legal.criteria import evaluate_legal_handoff_criteria
from apps.legal.models import LegalCase, LegalCaseStatus
from apps.legal.package import generate_legal_package
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def ctx(db):
    org = Organization.objects.create(name="Legal Co", slug="legal-co")
    admin = User.objects.create_user(email="legal-admin@example.com", password=PASSWORD)
    manager = User.objects.create_user(email="legal-manager@example.com", password=PASSWORD)
    lawyer = User.objects.create_user(email="lawyer@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=admin, role=Role.ADMIN, is_active=True)
    Membership.objects.create(
        organization=org, user=manager, role=Role.FINANCE_MANAGER, is_active=True
    )
    Membership.objects.create(
        organization=org, user=lawyer, role=Role.EXTERNAL_LAWYER, is_active=True
    )
    customer = Customer.objects.create(
        organization=org,
        name="Borçlu AŞ",
        code="B001",
        phone="+905551112233",
    )
    invoice = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="F-100",
        invoice_date=date.today() - timedelta(days=120),
        due_date=date.today() - timedelta(days=100),
        total_amount=Decimal("25000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": admin.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return {
        "org": org,
        "admin": admin,
        "manager": manager,
        "lawyer": lawyer,
        "customer": customer,
        "invoice": invoice,
        "client": client,
    }


@pytest.mark.django_db
def test_offline_sync_note_and_conflict(ctx):
    org = ctx["org"]
    customer = ctx["customer"]
    admin = ctx["admin"]
    client = ctx["client"]
    task = CollectionTask.objects.create(
        organization=org,
        customer=customer,
        title="Ara",
        due_date=date.today(),
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.OPEN,
        assigned_to=admin,
        created_by=admin,
    )
    ok = client.post(
        "/api/collection-tasks/offline-sync/",
        {
            "items": [
                {
                    "client_id": "c1",
                    "kind": "NOTE",
                    "task_id": task.id,
                    "payload": {"notes": "Müşteri yarın ödeyecek"},
                }
            ]
        },
        format="json",
    )
    assert ok.status_code == 200, ok.content
    assert len(ok.data["synced"]) == 1
    assert ok.data["conflicts"] == []

    task.status = CollectionTaskStatus.COMPLETED
    task.outcome = "REACHED"
    task.outcome_notes = "Sunucuda tamamlandı"
    task.save()
    conflict = client.post(
        "/api/collection-tasks/offline-sync/",
        {
            "items": [
                {
                    "client_id": "c2",
                    "kind": "COMPLETE_TASK",
                    "task_id": task.id,
                    "base_updated_at": "2000-01-01T00:00:00Z",
                    "payload": {"outcome": "REACHED", "outcome_notes": "Offline"},
                }
            ]
        },
        format="json",
    )
    assert conflict.status_code == 200
    assert conflict.data["conflicts"]
    assert conflict.data["conflicts"][0]["reason"] == "task_already_completed"


@pytest.mark.django_db
def test_legal_case_criteria_package_lawyer_scope(ctx):
    org = ctx["org"]
    customer = ctx["customer"]
    lawyer = ctx["lawyer"]
    client = ctx["client"]

    for _ in range(2):
        PaymentPromise.objects.create(
            organization=org,
            customer=customer,
            promised_date=date.today() - timedelta(days=10),
            amount=Decimal("1000.00"),
            status=PaymentPromiseStatus.BROKEN,
        )

    criteria = evaluate_legal_handoff_criteria(customer, organization=org)
    assert criteria["operational_criteria_met"] is True
    assert criteria["eligible_for_handoff"] is False  # manager approval missing

    create = client.post(
        "/api/legal/cases/",
        {"customer": customer.id, "title": "Dosya-1"},
        format="json",
    )
    assert create.status_code == 201, create.content
    case_id = create.data["id"]

    # Dual-control: manager (not requester) approves
    manager_client = APIClient()
    mlogin = manager_client.post(
        "/api/auth/login",
        {"email": ctx["manager"].email, "password": PASSWORD},
        format="json",
    )
    manager_client.credentials(HTTP_AUTHORIZATION=f"Bearer {mlogin.data['access']}")
    manager_client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    approve = manager_client.post(f"/api/legal/cases/{case_id}/approve/", {}, format="json")
    assert approve.status_code == 200, approve.content
    assert approve.data["manager_approved"] is True

    handoff = client.post(
        f"/api/legal/cases/{case_id}/handoff/",
        {"lawyer_id": lawyer.id, "note": "İhtar için"},
        format="json",
    )
    assert handoff.status_code == 200, handoff.content
    assert handoff.data["status"] == LegalCaseStatus.HANDED_TO_LAWYER

    case = LegalCase.objects.get(pk=case_id)
    path = generate_legal_package(case)
    assert Path(path).is_file()
    assert path.suffix == ".zip"

    upload = client.post(
        f"/api/legal/cases/{case_id}/documents/",
        {
            "file": SimpleUploadedFile("kanit.txt", b"delil", content_type="text/plain"),
            "notes": "ek",
        },
        format="multipart",
    )
    assert upload.status_code == 201, upload.content

    # Lawyer client — only assigned cases, restricted serializer
    lawyer_client = APIClient()
    login = lawyer_client.post(
        "/api/auth/login",
        {"email": lawyer.email, "password": PASSWORD},
        format="json",
    )
    lawyer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    lawyer_client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    listed = lawyer_client.get("/api/legal/cases/")
    assert listed.status_code == 200, listed.content
    assert listed.data["count"] == 1
    assert "disclaimer" in listed.data["results"][0]
    assert "case_invoices" not in listed.data["results"][0]

    status_update = lawyer_client.post(
        f"/api/legal/cases/{case_id}/status/",
        {"status": LegalCaseStatus.NOTICE, "note": "İhtar gönderildi"},
        format="json",
    )
    assert status_update.status_code == 200, status_update.content
    assert status_update.data["status"] == LegalCaseStatus.NOTICE

    # Package generation forbidden for lawyer
    pkg = lawyer_client.post(f"/api/legal/cases/{case_id}/package/", {}, format="json")
    assert pkg.status_code == 403


@pytest.mark.django_db
def test_task_serializer_includes_phone(ctx):
    client = ctx["client"]
    org = ctx["org"]
    customer = ctx["customer"]
    admin = ctx["admin"]
    CollectionTask.objects.create(
        organization=org,
        customer=customer,
        title="Telefon",
        due_date=date.today(),
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.OPEN,
        assigned_to=admin,
        created_by=admin,
    )
    board = client.get("/api/collection-tasks/today/")
    assert board.status_code == 200
    tasks = board.data["today"] + board.data["overdue"] + board.data["upcoming"]
    assert tasks
    assert tasks[0]["customer_phone"] == "+905551112233"
