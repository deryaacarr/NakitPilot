"""NP-282–286 usage, trial, payments, admin revenue."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.billing.models import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PlanCode,
    SubscriptionStatus,
    UsageMetric,
)
from apps.billing.payments import handle_payment_failure, process_webhook, start_checkout
from apps.billing.subscription_service import ensure_default_plans, ensure_subscription
from apps.billing.usage import record_usage, usage_summary
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def bill_ctx(db):
    org = Organization.objects.create(name="Meter Co", slug="meter-co")
    user = User.objects.create_user(email="meter@example.com", password=PASSWORD)
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
def test_usage_metering(bill_ctx):
    org, _, client = bill_ctx
    record_usage(org, UsageMetric.EMAILS_SENT, 3)
    record_usage(org, UsageMetric.WHATSAPP_SENT, 2)
    record_usage(org, UsageMetric.API_REQUESTS, 10)
    summary = usage_summary(org)
    assert summary["metrics"][UsageMetric.EMAILS_SENT] == 3
    assert summary["metrics"][UsageMetric.WHATSAPP_SENT] == 2
    assert summary["metrics"][UsageMetric.API_REQUESTS] == 10

    resp = client.get("/api/billing/usage/")
    assert resp.status_code == 200
    assert "active_customers" in resp.data["metrics"]


@pytest.mark.django_db
def test_trial_progress_and_readonly(bill_ctx):
    org, _, client = bill_ctx
    trial = client.get("/api/billing/trial/")
    assert trial.status_code == 200
    assert trial.data["card_required"] is False
    assert trial.data["read_only"] is False
    assert len(trial.data["steps"]) == 4

    sub = ensure_subscription(org)
    sub.trial_ends_at = timezone.now() - timedelta(hours=1)
    sub.save(update_fields=["trial_ends_at"])
    trial2 = client.get("/api/billing/trial/")
    assert trial2.data["read_only"] is True


@pytest.mark.django_db
def test_checkout_webhook_activate(bill_ctx):
    org, _, client = bill_ctx
    checkout = client.post(
        "/api/billing/checkout/",
        {"plan_code": PlanCode.PROFESSIONAL},
        format="json",
    )
    assert checkout.status_code == 201
    ref = checkout.data["checkout_id"]

    wh = client.post(
        "/api/billing/webhooks/payments/",
        {
            "event": "payment.succeeded",
            "checkout_id": ref,
            "plan_code": PlanCode.PROFESSIONAL,
        },
        format="json",
    )
    assert wh.status_code == 200
    assert wh.data["status"] == "activated"
    me = client.get("/api/billing/subscription/")
    assert me.data["status"] == SubscriptionStatus.ACTIVE
    assert me.data["plan"]["code"] == PlanCode.PROFESSIONAL


@pytest.mark.django_db
def test_dunning_steps(bill_ctx):
    org, _, _ = bill_ctx
    result = start_checkout(org, plan_code=PlanCode.PROFESSIONAL)
    attempt = PaymentAttempt.objects.get(provider_reference=result["checkout_id"])
    out1 = handle_payment_failure(attempt)
    assert out1["dunning_step"] == 1
    assert out1["next_retry_at"] is not None

    # second failure
    result2 = start_checkout(org, plan_code=PlanCode.PROFESSIONAL)
    attempt2 = PaymentAttempt.objects.get(provider_reference=result2["checkout_id"])
    out2 = handle_payment_failure(attempt2)
    assert out2["dunning_step"] == 2

    result3 = start_checkout(org, plan_code=PlanCode.PROFESSIONAL)
    attempt3 = PaymentAttempt.objects.get(provider_reference=result3["checkout_id"])
    out3 = handle_payment_failure(attempt3)
    assert out3["dunning_step"] == 3
    assert out3["grace_ends_at"] is not None


@pytest.mark.django_db
def test_subscription_management(bill_ctx):
    org, _, client = bill_ctx
    # upgrade first so downgrade is valid
    client.post("/api/billing/subscription/", {"plan_code": PlanCode.BUSINESS}, format="json")
    down = client.post(
        "/api/billing/subscription/schedule-downgrade/",
        {"plan_code": PlanCode.STARTER},
        format="json",
    )
    assert down.status_code == 200
    assert down.data["scheduled_plan"]["code"] == PlanCode.STARTER

    pm = client.post(
        "/api/billing/subscription/payment-method/",
        {"brand": "visa", "last4": "4242"},
        format="json",
    )
    assert pm.status_code == 200
    assert pm.data["payment_method"]["last4"] == "4242"

    cancel = client.post(
        "/api/billing/subscription/cancel/",
        {"at_period_end": True},
        format="json",
    )
    assert cancel.status_code == 200
    assert cancel.data["cancel_at_period_end"] is True


@pytest.mark.django_db
def test_admin_revenue(bill_ctx):
    org, user, client = bill_ctx
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    resp = client.get("/api/billing/admin/revenue/")
    assert resp.status_code == 200
    assert "mrr" in resp.data
    assert "arr" in resp.data
    assert "churn" in resp.data
    assert "plan_distribution" in resp.data
