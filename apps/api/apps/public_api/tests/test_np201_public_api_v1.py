"""NP-201 — Public REST API v1."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from apps.api_keys.services import create_api_key
from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def setup_org(db):
    org = Organization.objects.create(name="NP201 Org", slug="np201-org")
    owner = User.objects.create_user(email="np201-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.fixture
def api_key_full(setup_org):
    org, owner = setup_org
    key, raw = create_api_key(
        organization=org,
        name="Public full",
        scopes=[
            "customers:read",
            "customers:write",
            "invoices:read",
            "invoices:write",
            "payments:write",
            "risk:read",
            "forecast:read",
        ],
        created_by=owner,
    )
    return org, owner, key, raw


@pytest.fixture
def api_key_read_only(setup_org):
    org, owner = setup_org
    key, raw = create_api_key(
        organization=org,
        name="Read only",
        scopes=["customers:read"],
        created_by=owner,
    )
    return org, owner, key, raw


def _key_client(raw_key: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
    return client


@pytest.mark.django_db
def test_v1_customers_crud_pagination_and_audit(api_key_full):
    org, _owner, _key, raw = api_key_full
    client = _key_client(raw)

    created = client.post(
        "/api/v1/customers",
        {
            "code": "C-1",
            "name": "Public Customer",
            "email": "c1@example.com",
            "payment_term_days": 30,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="np201-customer-1",
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["name"] == "Public Customer"
    customer_id = created.data["id"]

    assert AuditLog.objects.filter(
        organization=org,
        action="customer.create",
        entity_type="Customer",
        entity_id=str(customer_id),
    ).filter(changes__via="api_v1").exists()

    listed = client.get("/api/v1/customers")
    assert listed.status_code == 200
    assert "results" in listed.data
    assert "count" in listed.data
    assert listed.data["count"] == 1
    assert listed.data["results"][0]["id"] == customer_id


@pytest.mark.django_db
def test_v1_scope_enforced(api_key_read_only):
    _org, _owner, _key, raw = api_key_read_only
    client = _key_client(raw)
    denied = client.post(
        "/api/v1/customers",
        {"code": "X", "name": "Nope"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="np201-denied",
    )
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    allowed = client.get("/api/v1/customers")
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_v1_invoices_payments_risk_forecast(api_key_full):
    org, _owner, _key, raw = api_key_full
    client = _key_client(raw)

    customer = Customer.objects.create(
        organization=org,
        code="C-RISK",
        name="Risk Customer",
        payment_term_days=15,
    )

    inv = client.post(
        "/api/v1/invoices",
        {
            "customer": customer.id,
            "number": "V1-001",
            "invoice_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=15)),
            "currency": "TRY",
            "subtotal_amount": "100.00",
            "tax_amount": "0.00",
            "total_amount": "100.00",
            "status": InvoiceStatus.OPEN,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="np201-invoice-1",
    )
    assert inv.status_code == 201
    assert AuditLog.objects.filter(
        action="invoice.create", entity_id=str(inv.data["id"]), changes__via="api_v1"
    ).exists()

    pay = client.post(
        "/api/v1/payments",
        {
            "customer": customer.id,
            "payment_date": str(date.today()),
            "amount": "50.00",
            "currency": "TRY",
            "auto_allocate": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="external-system-payment-1842",
    )
    assert pay.status_code == 201
    assert AuditLog.objects.filter(
        action="payment.create", entity_type="Payment", changes__via="api_v1"
    ).exists()

    risk = client.get(f"/api/v1/customers/{customer.id}/risk")
    assert risk.status_code == 200
    assert "score" in risk.data
    assert "level" in risk.data
    assert risk.data["customer_id"] == customer.id

    forecast = client.get("/api/v1/forecast/cash-flow?weeks=4")
    assert forecast.status_code == 200


@pytest.mark.django_db
def test_v1_requires_api_key_not_jwt_alone(setup_org, api_client):
    org, owner = setup_org
    login = api_client.post(
        "/api/auth/login",
        {"email": owner.email, "password": PASSWORD},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    api_client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    response = api_client.get("/api/v1/customers")
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.django_db
def test_v1_openapi_schema(api_key_full):
    _org, _owner, _key, raw = api_key_full
    client = _key_client(raw)
    # Schema endpoint may allow unauthenticated in spectacular — use API key anyway
    schema = client.get("/api/v1/schema")
    assert schema.status_code == 200
    body = schema.content.decode("utf-8")
    assert "/api/v1/customers" in body or "customers" in body
    assert "openapi" in body.lower() or schema["openapi"]


@pytest.mark.django_db
def test_v1_rate_limit(api_key_full, settings):
    cache.clear()
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "public_api": "2/min",
        },
    }
    _org, _owner, _key, raw = api_key_full
    client = _key_client(raw)
    assert client.get("/api/v1/customers").status_code == 200
    assert client.get("/api/v1/customers").status_code == 200
    limited = client.get("/api/v1/customers")
    assert limited.status_code == status.HTTP_429_TOO_MANY_REQUESTS
