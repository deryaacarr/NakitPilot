"""NP-280 / NP-281 subscription & entitlements."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.billing.models import PlanCode
from apps.billing.subscription_service import (
    Feature,
    can_use,
    ensure_default_plans,
    ensure_subscription,
)
from apps.customers.models import Customer
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def bill_ctx(db):
    org = Organization.objects.create(name="Bill Co", slug="bill-co")
    user = User.objects.create_user(email="bill@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=user, role=Role.ADMIN, is_active=True)
    ensure_default_plans()
    ensure_subscription(org, plan_code=PlanCode.STARTER)
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
def test_plans_subscription_and_can_use(bill_ctx):
    org, _, client = bill_ctx
    plans = client.get("/api/billing/plans/")
    assert plans.status_code == 200
    codes = {p["code"] for p in plans.data["results"]}
    assert codes >= {PlanCode.STARTER, PlanCode.PROFESSIONAL, PlanCode.BUSINESS, PlanCode.ENTERPRISE}

    me = client.get("/api/billing/subscription/")
    assert me.status_code == 200
    assert me.data["plan"]["code"] == PlanCode.STARTER
    assert me.data["entitlements"]["api_access"] is False

    denied = can_use(org, Feature.ADVANCED_WORKFLOWS)
    assert denied.allowed is False

    upgrade = client.post(
        "/api/billing/subscription/",
        {"plan_code": PlanCode.PROFESSIONAL},
        format="json",
    )
    assert upgrade.status_code == 200
    assert upgrade.data["plan"]["code"] == PlanCode.PROFESSIONAL
    assert can_use(org, Feature.ADVANCED_WORKFLOWS).allowed is True
    assert can_use(org, Feature.API_ACCESS).allowed is True

    check = client.get("/api/billing/can-use/?feature=max_customers")
    assert check.status_code == 200
    assert check.data["allowed"] is True
    assert check.data["limit"] == 2000


@pytest.mark.django_db
def test_max_customers_limit(bill_ctx):
    org, _, client = bill_ctx
    # Starter max 200 — create one and check quantity
    Customer.objects.create(organization=org, name="C1", code="C1")
    result = can_use(org, Feature.MAX_CUSTOMERS, quantity=1)
    assert result.allowed is True
    assert result.current == 1
    assert result.limit == 200
