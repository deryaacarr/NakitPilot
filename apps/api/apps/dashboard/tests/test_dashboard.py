from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.collections.models import (
    CollectionTask,
    CollectionTaskStatus,
    CollectionTaskType,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.models import Customer, RiskStatus
from apps.dashboard.services import aging_report, dashboard_summary, today_call_list
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
def org_setup(db):
    org = Organization.objects.create(name="Dash Co", slug="dash-co")
    user = User.objects.create_user(email="dash@test.local", password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=Role.OWNER, is_active=True)
    today = date.today()

    critical = Customer.objects.create(
        organization=org,
        name="Kritik AŞ",
        code="K-1",
        risk_status=RiskStatus.CRITICAL,
        risk_score=90,
        last_contact_at=timezone.now() - timedelta(days=20),
    )
    mid = Customer.objects.create(
        organization=org,
        name="Orta Ltd",
        code="O-1",
        risk_status=RiskStatus.MEDIUM,
        risk_score=40,
        last_contact_at=timezone.now(),
    )

    # Not due
    Invoice.objects.create(
        organization=org,
        customer=mid,
        number="ND-1",
        invoice_date=today,
        due_date=today + timedelta(days=20),
        total_amount=Decimal("1000.00"),
        status=InvoiceStatus.OPEN,
    )
    # 10 days overdue
    Invoice.objects.create(
        organization=org,
        customer=critical,
        number="OV-10",
        invoice_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
        total_amount=Decimal("6000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    # 100 days overdue
    Invoice.objects.create(
        organization=org,
        customer=critical,
        number="OV-100",
        invoice_date=today - timedelta(days=130),
        due_date=today - timedelta(days=100),
        total_amount=Decimal("2000.00"),
        status=InvoiceStatus.OVERDUE,
    )

    PaymentPromise.objects.create(
        organization=org,
        customer=critical,
        promised_date=today,
        amount=Decimal("500.00"),
        status=PaymentPromiseStatus.PENDING,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=mid,
        promised_date=today - timedelta(days=5),
        amount=Decimal("100.00"),
        status=PaymentPromiseStatus.BROKEN,
    )
    CollectionTask.objects.create(
        organization=org,
        customer=mid,
        title="Eski görev",
        due_date=today - timedelta(days=2),
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.OPEN,
    )
    return org, user, critical, mid, today


@pytest.mark.django_db
def test_summary_cards(org_setup):
    org, _user, _c, _m, today = org_setup
    summary = dashboard_summary(
        org.id,
        as_of=today,
        date_from=today - timedelta(days=30),
        date_to=today,
    )
    cards = summary["cards"]
    assert cards["open_receivables"] == "9000.00"
    assert cards["overdue_receivables"] == "8000.00"
    assert cards["promises_today"] == 1
    assert cards["promises_broken"] == 1
    assert cards["critical_customers"] == 1
    assert cards["overdue_tasks"] == 1
    assert Decimal(cards["expected_this_week"]) >= 0


@pytest.mark.django_db
def test_aging_groups(org_setup):
    org, *_rest = org_setup
    report = aging_report(org.id)
    by_code = {g["code"]: g for g in report["groups"]}
    assert by_code["not_due"]["invoice_count"] == 1
    assert by_code["not_due"]["open_amount"] == "1000.00"
    assert by_code["d1_15"]["invoice_count"] == 1
    assert by_code["d90_plus"]["invoice_count"] == 1
    assert report["total_open_amount"] == "9000.00"
    shares = sum(Decimal(g["share"]) for g in report["groups"])
    assert shares == Decimal("1.0000") or abs(shares - Decimal("1")) < Decimal("0.01")


@pytest.mark.django_db
def test_call_list_top_priority(org_setup):
    org, *_rest = org_setup
    result = today_call_list(org.id, limit=10)
    assert len(result["results"]) >= 1
    assert result["results"][0]["customer_name"] == "Kritik AŞ"
    assert result["results"][0]["priority_score"] >= result["results"][-1]["priority_score"]
    row = result["results"][0]
    assert "overdue_balance" in row
    assert "oldest_overdue_days" in row
    assert "risk_status" in row
    assert "last_contact_at" in row
    assert "payment_promise" in row


@pytest.mark.django_db
def test_dashboard_api(api_client, org_setup):
    org, user, *_rest = org_setup
    client = _auth(api_client, user, org)
    response = client.get("/api/dashboard/", {"range": "last_30"})
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body and "aging" in body and "call_list" in body
    assert "performance" in body and "range" in body
    assert body["range"]["preset"] == "last_30"
    assert len(body["aging"]["groups"]) == 6
    assert "weekly" in body["performance"]
    assert "tasks_by_user" in body["performance"]
    assert "promises" in body["performance"]


@pytest.mark.django_db
def test_performance_and_date_presets(org_setup):
    from apps.dashboard.performance import performance_report, resolve_date_range
    from apps.payments.models import Payment, PaymentMethod

    org, user, critical, _mid, today = org_setup
    Payment.objects.create(
        organization=org,
        customer=critical,
        payment_date=today,
        amount=Decimal("250.00"),
        currency="TRY",
        method=PaymentMethod.BANK_TRANSFER,
        recorded_by=user,
    )
    task = CollectionTask.objects.create(
        organization=org,
        customer=critical,
        title="Bitti",
        due_date=today,
        task_type=CollectionTaskType.CALL,
        status=CollectionTaskStatus.COMPLETED,
        assigned_to=user,
        completed_at=timezone.now(),
    )
    assert task.completed_at is not None

    rng = resolve_date_range(preset="today", today=today)
    perf = performance_report(org.id, date_from=rng["date_from"], date_to=rng["date_to"])
    assert any(Decimal(w["actual"]) > 0 for w in perf["weekly"])
    assert perf["promises"]["broken"] >= 0
    assert any(r["completed_count"] >= 1 for r in perf["tasks_by_user"])

    custom = resolve_date_range(
        preset="custom",
        date_from=today - timedelta(days=7),
        date_to=today,
        today=today,
    )
    assert custom["date_from"] == today - timedelta(days=7)


@pytest.mark.django_db
def test_invalid_custom_range(api_client, org_setup):
    org, user, *_rest = org_setup
    client = _auth(api_client, user, org)
    response = client.get("/api/dashboard/", {"range": "custom"})
    assert response.status_code == 400
