from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.collections.models import CollectionTask, PaymentPromise, PaymentPromiseStatus
from apps.collections.promises import compute_promise_status, process_broken_promises
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.notifications.models import DashboardAlert
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
def org_owner(db):
    org = Organization.objects.create(name="Promise Co", slug="promise-co")
    owner = User.objects.create_user(email="promise@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(
        organization=org, name="Sözlü Cari", code="P-1", assigned_user=owner
    )
    return org, owner, customer


@pytest.mark.django_db
def test_promise_crud_and_validations(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    today = date.today()

    past = client.post(
        "/api/payment-promises/",
        {
            "customer": customer.id,
            "promised_date": (today - timedelta(days=1)).isoformat(),
            "amount": "100.00",
        },
        format="json",
    )
    assert past.status_code == status.HTTP_400_BAD_REQUEST
    assert past.data["code"] == "past_promised_date"

    zero = client.post(
        "/api/payment-promises/",
        {"customer": customer.id, "promised_date": today.isoformat(), "amount": "0"},
        format="json",
    )
    assert zero.status_code == status.HTTP_400_BAD_REQUEST

    closed = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="PAID-1",
        invoice_date=today,
        due_date=today,
        total_amount=Decimal("50.00"),
        status=InvoiceStatus.PAID,
    )
    closed_resp = client.post(
        "/api/payment-promises/",
        {
            "customer": customer.id,
            "invoice": closed.id,
            "promised_date": (today + timedelta(days=3)).isoformat(),
            "amount": "50.00",
        },
        format="json",
    )
    assert closed_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert closed_resp.data["code"] == "invoice_closed"

    # open balance 0 → warning when amount > 0
    create = client.post(
        "/api/payment-promises/",
        {
            "customer": customer.id,
            "promised_date": (today + timedelta(days=5)).isoformat(),
            "amount": "2500.00",
            "notes": "Cuma ödeme",
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED, create.data
    if "warnings" in create.data:
        assert "amount_exceeds_open_balance" in create.data["warnings"]
        promise_id = create.data["promise"]["id"]
    else:
        promise_id = create.data["id"]

    # NP-430 follow-up + same-date warning
    follow = client.post(
        "/api/payment-promises/",
        {
            "customer": customer.id,
            "promised_date": (today + timedelta(days=5)).isoformat(),
            "amount": "100.00",
            "create_follow_up": True,
            "assigned_to": owner.id,
        },
        format="json",
    )
    assert follow.status_code == status.HTTP_201_CREATED, follow.data
    assert follow.data.get("follow_up_task_id")
    assert "same_date_promises" in (follow.data.get("warnings") or {})
    assert CollectionTask.objects.filter(id=follow.data["follow_up_task_id"]).exists()

    board = client.get("/api/payment-promises/board/")
    assert board.status_code == status.HTTP_200_OK
    assert set(board.data.keys()) >= {
        "pending",
        "today",
        "upcoming",
        "partial",
        "fulfilled",
        "broken",
    }

    patch = client.patch(
        f"/api/payment-promises/{promise_id}/",
        {"amount": "2000.00"},
        format="json",
    )
    assert patch.status_code == status.HTTP_200_OK

    cancel = client.post(
        f"/api/payment-promises/{promise_id}/cancel/",
        {"reason": "Müşteri vazgeçti"},
        format="json",
    )
    assert cancel.status_code == status.HTTP_200_OK
    assert cancel.data["status"] == PaymentPromiseStatus.CANCELLED


@pytest.mark.django_db
def test_promise_status_rules(org_owner):
    org, owner, customer = org_owner
    today = date.today()

    past_due = PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=1),
        amount=Decimal("10.00"),
        status=PaymentPromiseStatus.PENDING,
    )
    assert compute_promise_status(past_due) == PaymentPromiseStatus.BROKEN

    other = Customer.objects.create(organization=org, name="Diğer", code="P-2")
    promise = PaymentPromise.objects.create(
        organization=org,
        customer=other,
        promised_date=today + timedelta(days=2),
        amount=Decimal("100.00"),
        status=PaymentPromiseStatus.PENDING,
    )
    assert compute_promise_status(promise) == PaymentPromiseStatus.PENDING

    Payment.objects.create(
        organization=org,
        customer=other,
        payment_date=today,
        amount=Decimal("40.00"),
        currency="TRY",
        recorded_by=owner,
    )
    assert compute_promise_status(promise) == PaymentPromiseStatus.PARTIALLY_FULFILLED

    Payment.objects.create(
        organization=org,
        customer=other,
        payment_date=today,
        amount=Decimal("60.00"),
        currency="TRY",
        recorded_by=owner,
    )
    assert compute_promise_status(promise) == PaymentPromiseStatus.FULFILLED


@pytest.mark.django_db
def test_process_broken_creates_task_alert_risk(org_owner):
    org, owner, customer = org_owner
    today = date.today()
    promise = PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=2),
        amount=Decimal("500.00"),
        status=PaymentPromiseStatus.PENDING,
    )
    result = process_broken_promises(organization=org, as_of=today)
    assert result["broken"] == 1
    assert result["tasks_created"] == 1
    assert result["alerts_created"] == 1
    promise.refresh_from_db()
    assert promise.status == PaymentPromiseStatus.BROKEN
    assert CollectionTask.objects.filter(related_promise=promise).exists()
    assert DashboardAlert.objects.filter(category="broken_promise").exists()
    customer.refresh_from_db()
    assert customer.risk_score >= 0


@pytest.mark.django_db
def test_promise_calendar(api_client, org_owner):
    org, owner, customer = org_owner
    client = _auth(api_client, owner, org)
    today = date.today()
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today,
        amount=Decimal("10"),
        status=PaymentPromiseStatus.PENDING,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today + timedelta(days=7),
        amount=Decimal("20"),
        status=PaymentPromiseStatus.PENDING,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=3),
        amount=Decimal("30"),
        status=PaymentPromiseStatus.BROKEN,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today - timedelta(days=10),
        amount=Decimal("40"),
        status=PaymentPromiseStatus.FULFILLED,
    )
    cal = client.get("/api/payment-promises/calendar/")
    assert cal.status_code == status.HTTP_200_OK
    assert len(cal.data["today"]) >= 1
    assert len(cal.data["upcoming"]) >= 1
    assert len(cal.data["broken"]) >= 1
    assert len(cal.data["fulfilled"]) >= 1
