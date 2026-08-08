from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.collections.models import (
    CollectionTask,
    CollectionTaskSource,
    CollectionTaskStatus,
    CollectionTaskType,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.models import Customer
from apps.notifications.models import (
    DashboardAlert,
    NotificationType,
    create_dashboard_alert,
    resolve_notification_href,
)
from apps.notifications.services import generate_daily_task_promise_reminders
from apps.notifications.tasks import _in_window
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
    org = Organization.objects.create(
        name="Notify Co", slug="notify-co", timezone="Europe/Istanbul"
    )
    owner = User.objects.create_user(email="notify@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(
        organization=org, name="Bildirim Cari", code="N-1", assigned_user=owner
    )
    return org, owner, customer


@pytest.mark.django_db
def test_notification_types_and_href(org_owner):
    org, owner, customer = org_owner
    alert = create_dashboard_alert(
        organization=org,
        title="Kritik risk",
        notification_type=NotificationType.HIGH_RISK_CUSTOMER,
        entity_type="Customer",
        entity_id=customer.id,
        created_for=owner,
    )
    assert alert.notification_type == NotificationType.HIGH_RISK_CUSTOMER
    assert alert.href == f"/customers/{customer.id}"
    assert resolve_notification_href(
        NotificationType.TASK_DUE, entity_id=12
    ) == "/collections/field?task=12"


@pytest.mark.django_db
def test_daily_reminders_create_task_due(org_owner):
    org, owner, customer = org_owner
    today = date.today()
    CollectionTask.objects.create(
        organization=org,
        customer=customer,
        title="Ara",
        due_date=today,
        status=CollectionTaskStatus.OPEN,
        task_type=CollectionTaskType.CALL,
        assigned_to=owner,
        source=CollectionTaskSource.MANUAL,
    )
    PaymentPromise.objects.create(
        organization=org,
        customer=customer,
        promised_date=today,
        amount=Decimal("100.00"),
        currency="TRY",
        status=PaymentPromiseStatus.PENDING,
        created_by=owner,
    )
    result = generate_daily_task_promise_reminders(org, as_of=today)
    assert result["task_due"] == 1
    assert result["promise_due"] == 1
    types = set(
        DashboardAlert.objects.filter(organization=org).values_list(
            "notification_type", flat=True
        )
    )
    assert NotificationType.TASK_DUE in types
    assert NotificationType.PROMISE_DUE in types


@pytest.mark.django_db
def test_alerts_list_mark_read_and_mark_all(api_client, org_owner):
    org, owner, _customer = org_owner
    client = _auth(api_client, owner, org)
    a1 = create_dashboard_alert(
        organization=org,
        title="Bir",
        notification_type=NotificationType.IMPORT_COMPLETED,
        created_for=owner,
    )
    create_dashboard_alert(
        organization=org,
        title="İki",
        notification_type=NotificationType.IMPORT_FAILED,
        created_for=owner,
    )

    listed = client.get("/api/notifications/alerts/")
    assert listed.status_code == status.HTTP_200_OK
    assert listed.data["unread_count"] == 2
    assert len(listed.data["results"]) == 2
    assert "href" in listed.data["results"][0]
    assert "notification_type" in listed.data["results"][0]
    assert "importance_group" in listed.data["results"][0]
    assert "actions" in listed.data["results"][0]

    read = client.post(f"/api/notifications/alerts/{a1.id}/read/")
    assert read.status_code == status.HTTP_200_OK
    assert read.data["is_read"] is True

    listed2 = client.get("/api/notifications/alerts/")
    assert listed2.data["unread_count"] == 1

    mark_all = client.post("/api/notifications/alerts/read-all/")
    assert mark_all.status_code == status.HTTP_200_OK
    assert mark_all.data["updated"] == 1
    assert mark_all.data.get("critical_preserved") is True

    listed3 = client.get("/api/notifications/alerts/")
    assert listed3.data["unread_count"] == 0

    # NP-462 preferences
    prefs = client.get("/api/notifications/preferences/")
    assert prefs.status_code == status.HTTP_200_OK
    patch = client.patch(
        "/api/notifications/preferences/",
        {"mute_system": True, "group_by_customer": True},
        format="json",
    )
    assert patch.status_code == status.HTTP_200_OK
    assert patch.data["mute_system"] is True


def test_schedule_window_org_local():
    tz = ZoneInfo("Europe/Istanbul")
    local = datetime(2026, 7, 31, 8, 2, tzinfo=tz)  # Friday
    assert _in_window(local, 8, 0, None) is True
    assert _in_window(local, 0, 15, None) is False
    monday = datetime(2026, 7, 27, 1, 32, tzinfo=tz)  # Monday
    assert _in_window(monday, 1, 30, 0) is True
    assert _in_window(local, 1, 30, 0) is False
