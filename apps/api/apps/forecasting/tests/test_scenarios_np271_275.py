"""NP-271–275 bank, scenario, what-if, cash-gap, accuracy."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.billing.models import PlanCode
from apps.billing.subscription_service import ensure_default_plans, ensure_subscription
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role
from apps.payables.models import BankAccount, Payable, PayableStatus
from apps.payments.models import Payment

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def fc_ctx(db):
    org = Organization.objects.create(name="FC Co", slug="fc-co-np271")
    user = User.objects.create_user(email="fc@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=user, role=Role.ADMIN, is_active=True)
    ensure_default_plans()
    sub = ensure_subscription(org, plan_code=PlanCode.PROFESSIONAL)
    from apps.billing.models import SubscriptionPlan, SubscriptionStatus

    sub.plan = SubscriptionPlan.objects.get(code=PlanCode.PROFESSIONAL)
    sub.status = SubscriptionStatus.ACTIVE
    sub.save()
    customer = Customer.objects.create(
        organization=org, name="ABC Elektrik", code="ABC", phone="05551112233"
    )
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-ABC-1",
        invoice_date=date.today() - timedelta(days=10),
        due_date=date.today() + timedelta(days=5),
        total_amount=Decimal("450000.00"),
        status=InvoiceStatus.OPEN,
    )
    BankAccount.objects.create(
        organization=org,
        name="İş Bankası TL",
        bank_name="İş Bankası",
        current_balance=Decimal("200000.00"),
        blocked_amount=Decimal("10000.00"),
        as_of=date.today(),
    )
    Payable.objects.create(
        organization=org,
        vendor_name="Personel Maaş",
        description="Aylık maaş",
        due_date=date.today() + timedelta(days=10),
        amount=Decimal("180000.00"),
        status=PayableStatus.OPEN,
    )
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return org, user, customer, client


@pytest.mark.django_db
def test_bank_account_available_balance(fc_ctx):
    org, _, _, client = fc_ctx
    listing = client.get("/api/payables/bank-accounts/")
    assert listing.status_code == 200
    rows = listing.data if isinstance(listing.data, list) else listing.data["results"]
    assert len(rows) >= 1
    row = rows[0]
    assert Decimal(row["available_balance"]) == Decimal("190000.00")


@pytest.mark.django_db
def test_scenario_and_what_if(fc_ctx):
    org, _, customer, client = fc_ctx
    base = client.post(
        "/api/forecast/scenarios/run/",
        {"scenario_type": "BASE", "weeks": 8},
        format="json",
    )
    assert base.status_code == 200, base.content
    assert "minimum_cash" in base.data
    assert len(base.data["weeks"]) == 8

    crisis = client.post(
        "/api/forecast/scenarios/run/",
        {"scenario_type": "CRISIS", "weeks": 8},
        format="json",
    )
    assert crisis.status_code == 200

    whatif = client.post(
        "/api/forecast/what-if/",
        {
            "customer_id": customer.id,
            "delay_days": 30,
            "amount": "450000.00",
            "weeks": 8,
        },
        format="json",
    )
    assert whatif.status_code == 200, whatif.content
    assert whatif.data["customer"]["name"] == "ABC Elektrik"
    assert "minimum_cash" in whatif.data["scenario"]
    assert "impact" in whatif.data


@pytest.mark.django_db
def test_cash_gap_and_accuracy(fc_ctx):
    org, _, customer, client = fc_ctx
    Payment.objects.create(
        organization=org,
        customer=customer,
        amount=Decimal("10000.00"),
        unallocated_amount=Decimal("10000.00"),
        payment_date=date.today() - timedelta(days=3),
        currency="TRY",
    )
    gaps = client.post(
        "/api/forecast/cash-gap-alerts/",
        {"weeks": 8, "min_safe_balance": "500000"},
        format="json",
    )
    assert gaps.status_code == 200
    assert "findings" in gaps.data

    acc = client.get("/api/forecast/accuracy/")
    assert acc.status_code == 200
    assert "mae" in acc.data["metrics"]
    assert "mape" in acc.data["metrics"]
    assert "bias" in acc.data["metrics"]
    assert "weekly_accuracy_pct" in acc.data["metrics"]
    assert len(acc.data["weeks"]) >= 1
