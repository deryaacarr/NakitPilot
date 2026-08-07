from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.forecasting.weekly import cash_flow_api_payload, format_tr_money
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
def api_org(db):
    org = Organization.objects.create(name="API Fc", slug="api-fc")
    user = User.objects.create_user(email="fc@test.local", password=PASSWORD)
    Membership.objects.create(
        user=user, organization=org, role=Role.OWNER, is_active=True
    )
    customer = Customer.objects.create(
        organization=org,
        name="ABC Elektrik",
        code="ABC",
        risk_score=82,
        risk_status="HIGH",
        last_contact_at=timezone.now(),
    )
    return org, user, customer


@pytest.mark.django_db
def test_cash_flow_api_shape(api_client, api_org):
    org, user, customer = api_org
    client = _auth(api_client, user, org)
    today = date.today()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="API-1",
        invoice_date=today,
        due_date=today + timedelta(days=3),
        total_amount=Decimal("450000.00"),
        status=InvoiceStatus.OPEN,
        currency="TRY",
    )
    response = client.get("/api/forecast/cash-flow", {"weeks": 13})
    assert response.status_code == 200
    body = response.json()
    assert "weeks" in body
    assert len(body["weeks"]) == 13
    week = body["weeks"][0]
    assert set(week.keys()) == {
        "week_start",
        "nominal",
        "expected",
        "optimistic",
        "pessimistic",
    }
    assert isinstance(week["nominal"], str)


@pytest.mark.django_db
def test_cash_flow_week_detail(api_client, api_org):
    org, user, customer = api_org
    client = _auth(api_client, user, org)
    today = date.today()
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="API-2",
        invoice_date=today,
        due_date=today + timedelta(days=2),
        total_amount=Decimal("450000.00"),
        status=InvoiceStatus.OPEN,
        currency="TRY",
    )
    payload = cash_flow_api_payload(org.id, weeks=13)
    week_start = payload["weeks"][0]["week_start"]
    response = client.get(
        "/api/forecast/cash-flow",
        {"weeks": 13, "week_start": week_start},
    )
    assert response.status_code == 200
    detail = response.json()["detail"]
    assert detail["summary"].startswith("Bu hafta")
    assert detail["open_total"] == "450000.00"
    assert detail["expected"] == "405000.00"  # 90%
    assert detail["risk_reduction"] == "45000.00"
    assert detail["highest_risk_customer"]["name"] == "ABC Elektrik"
    assert len(detail["top_invoices"]) >= 1
    assert detail["top_invoices"][0]["number"] == "API-2"


def test_format_tr_money():
    assert format_tr_money(Decimal("327500.00")) == "327.500 TL"
    assert format_tr_money(Decimal("45000.50")) == "45.000,50 TL"
