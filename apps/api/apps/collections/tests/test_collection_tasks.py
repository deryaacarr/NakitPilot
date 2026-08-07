from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.collections.models import (
    CollectionTask,
    CollectionTaskSource,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.collections.services import (
    auto_generate_collection_tasks,
    compute_priority_score,
)
from apps.customers.models import Customer, RiskStatus
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
def org_owner(db):
    org = Organization.objects.create(name="Col Co", slug="col-co")
    owner = User.objects.create_user(
        email="col-owner@example.com",
        password=PASSWORD,
        first_name="Ayşe",
        last_name="Yılmaz",
    )
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(
        organization=org,
        name="Riskli Cari",
        code="R-1",
        assigned_user=owner,
        risk_status=RiskStatus.HIGH,
    )
    return org, owner, customer


@pytest.mark.django_db
def test_task_crud_complete_cancel(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)

    create = client.post(
        "/api/collection-tasks/",
        {
            "customer": customer.id,
            "due_date": date.today().isoformat(),
            "title": "Ara",
            "task_type": "CALL",
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED, create.data
    task_id = create.data["id"] if "id" in create.data else create.data["task"]["id"]

    detail = client.get(f"/api/collection-tasks/{task_id}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["customer_name"] == "Riskli Cari"

    complete = client.post(
        f"/api/collection-tasks/{task_id}/complete/",
        {
            "outcome": "CALLBACK",
            "outcome_notes": "Yarın tekrar aranacak",
            "create_follow_up": True,
            "callback_date": (date.today() + timedelta(days=1)).isoformat(),
            "promise_given": True,
            "promise_amount": "1500.00",
            "promise_date": (date.today() + timedelta(days=5)).isoformat(),
        },
        format="json",
    )
    assert complete.status_code == status.HTTP_200_OK, complete.data
    assert complete.data["task"]["status"] == CollectionTaskStatus.COMPLETED
    assert complete.data["follow_up"] is not None
    assert complete.data["promise_id"] is not None

    follow_id = complete.data["follow_up"]["id"]
    cancel = client.post(
        f"/api/collection-tasks/{follow_id}/cancel/",
        {"reason": "Gerek kalmadı"},
        format="json",
    )
    assert cancel.status_code == status.HTTP_200_OK
    assert cancel.data["status"] == CollectionTaskStatus.CANCELLED


@pytest.mark.django_db
def test_today_board_and_priority(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    today = date.today()

    client.post(
        "/api/collection-tasks/",
        {
            "customer": customer.id,
            "due_date": (today - timedelta(days=2)).isoformat(),
            "title": "Gecikmiş",
        },
        format="json",
    )
    client.post(
        "/api/collection-tasks/",
        {"customer": customer.id, "due_date": today.isoformat(), "title": "Bugün"},
        format="json",
    )
    client.post(
        "/api/collection-tasks/",
        {
            "customer": customer.id,
            "due_date": (today + timedelta(days=3)).isoformat(),
            "title": "Yaklaşan",
        },
        format="json",
    )

    board = client.get("/api/collection-tasks/today/")
    assert board.status_code == status.HTTP_200_OK
    assert len(board.data["overdue"]) >= 1
    assert len(board.data["today"]) >= 1
    assert len(board.data["upcoming"]) >= 1

    score, level, details = compute_priority_score(customer)
    assert "high_risk" in details
    assert score >= 20
    assert level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@pytest.mark.django_db
def test_bulk_assign_warns_inactive(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    inactive = User.objects.create_user(
        email="inactive-agent@example.com", password=PASSWORD, is_active=False
    )
    Membership.objects.create(
        organization=org, user=inactive, role=Role.COLLECTION_AGENT, is_active=False
    )

    create = client.post(
        "/api/collection-tasks/",
        {"customer": customer.id, "due_date": date.today().isoformat(), "title": "Ata"},
        format="json",
    )
    task_id = create.data["id"] if "id" in create.data else create.data["task"]["id"]

    bulk = client.post(
        "/api/collection-tasks/bulk-assign/",
        {"task_ids": [task_id], "assigned_to": inactive.id},
        format="json",
    )
    assert bulk.status_code == status.HTTP_200_OK
    assert bulk.data["warning"] == "assigned_user_inactive"
    assert bulk.data["updated"] == 1


@pytest.mark.django_db
def test_auto_generate_skips_duplicate_invoice_task(org_owner):
    org, owner, customer = org_owner
    invoice = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="OV-1",
        invoice_date=date.today() - timedelta(days=40),
        due_date=date.today() - timedelta(days=10),
        total_amount=Decimal("8000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    first = auto_generate_collection_tasks(organization=org)
    assert first["tasks_from_overdue"] >= 1
    assert (
        CollectionTask.objects.filter(invoice=invoice, status=CollectionTaskStatus.OPEN).count()
        == 1
    )

    second = auto_generate_collection_tasks(organization=org)
    assert second["tasks_from_overdue"] == 0

    promise = PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=date.today() - timedelta(days=2),
        amount=Decimal("100.00"),
        status=PaymentPromiseStatus.PENDING,
    )
    auto_generate_collection_tasks(organization=org)
    promise.refresh_from_db()
    assert promise.status == PaymentPromiseStatus.BROKEN
    assert CollectionTask.objects.filter(
        related_promise=promise, source=CollectionTaskSource.BROKEN_PROMISE
    ).exists()


@pytest.mark.django_db
def test_customer_timeline(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    create = client.post(
        "/api/collection-tasks/",
        {"customer": customer.id, "due_date": date.today().isoformat(), "title": "TL"},
        format="json",
    )
    task_id = create.data["id"] if "id" in create.data else create.data["task"]["id"]
    client.post(
        f"/api/collection-tasks/{task_id}/complete/",
        {"outcome": "REACHED", "outcome_notes": "Konuşuldu"},
        format="json",
    )
    timeline = client.get(f"/api/customers/{customer.id}/timeline/")
    assert timeline.status_code == status.HTTP_200_OK
    kinds = {e["kind"] for e in timeline.data["results"]}
    assert "TASK_COMPLETED" in kinds
