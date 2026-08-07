"""NP-270 payable / net cash tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization, Role
from apps.payables.models import Payable, PayableStatus, RecurringExpense
from apps.payables.services import expected_outflows_by_week, net_cash_summary

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def pay_ctx(db):
    org = Organization.objects.create(name="Pay Co", slug="pay-co")
    user = User.objects.create_user(email="pay@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=user, role=Role.ADMIN, is_active=True)
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return org, user, client


@pytest.mark.django_db
def test_payable_crud_and_net_cash(pay_ctx):
    org, user, client = pay_ctx
    cat = client.post(
        "/api/payables/categories/",
        {"name": "Kira", "code": "RENT"},
        format="json",
    )
    assert cat.status_code == 201, cat.content
    due = date.today() + timedelta(days=3)
    create = client.post(
        "/api/payables/payables/",
        {
            "vendor_name": "Landlord AŞ",
            "category": cat.data["id"],
            "due_date": due.isoformat(),
            "amount": "12000.00",
            "status": PayableStatus.OPEN,
        },
        format="json",
    )
    assert create.status_code == 201, create.content

    RecurringExpense.objects.create(
        organization=org,
        name="Maaş",
        amount=Decimal("50000.00"),
        day_of_month=min(date.today().day, 28),
        start_date=date.today().replace(day=1),
        is_active=True,
    )
    outflows = expected_outflows_by_week(org, weeks=4)
    assert any(Decimal(w["total_outflow"]) > 0 for w in outflows)

    summary = net_cash_summary(
        org,
        expected_collections=[
            {"week_start": outflows[0]["week_start"], "expected": "100000"}
        ],
        weeks=4,
    )
    assert "total_net_cash" in summary
    api = client.get("/api/payables/net-cash/?weeks=4")
    assert api.status_code == 200
    assert "total_expected_outflows" in api.data
