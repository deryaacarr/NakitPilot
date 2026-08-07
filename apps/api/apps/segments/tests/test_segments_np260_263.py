"""NP-260–263 segment rules, strategies, A/B tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.customers.models import Customer, RiskStatus
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role
from apps.segments.rules import customer_matches_rules, validate_rules
from apps.segments.services import ensure_default_segments

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def seg_ctx(db):
    org = Organization.objects.create(name="Seg Co", slug="seg-co")
    user = User.objects.create_user(email="seg@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=user, role=Role.ADMIN, is_active=True)
    low = Customer.objects.create(
        organization=org,
        name="Low Risk Big",
        code="L1",
        risk_status=RiskStatus.LOW,
    )
    high = Customer.objects.create(
        organization=org,
        name="High Risk Big",
        code="H1",
        risk_status=RiskStatus.CRITICAL,
    )
    for cust, amt in ((low, "300000"), (high, "300000")):
        Invoice.objects.create(
            organization=org,
            customer=cust,
            number=f"INV-{cust.code}",
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=20),
            total_amount=Decimal(amt),
            status=InvoiceStatus.OVERDUE,
        )
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return org, user, low, high, client


@pytest.mark.django_db
def test_default_segments_and_rule_match(seg_ctx):
    org, _, low, high, client = seg_ctx
    ensure_default_segments(org)
    listing = client.get("/api/segments/")
    assert listing.status_code == 200
    slugs = {r["slug"] for r in listing.data["results"]}
    assert "high-balance-high-risk" in slugs
    assert "strategic" in slugs

    rules = {
        "all": [
            {"field": "overdue_balance", "operator": "greater_than", "value": 250000},
            {"field": "risk_level", "operator": "in", "value": ["HIGH", "CRITICAL"]},
        ]
    }
    validate_rules(rules)
    assert customer_matches_rules(high, rules) is True
    assert customer_matches_rules(low, rules) is False

    preview = client.post("/api/segments/preview/", {"rules": rules}, format="json")
    assert preview.status_code == 200
    assert high.id in preview.data["customer_ids"]
    assert low.id not in preview.data["customer_ids"]


@pytest.mark.django_db
def test_strategy_and_ab_test(seg_ctx):
    org, _, low, high, client = seg_ctx
    ensure_default_segments(org)
    strategies = client.get("/api/segments/strategies/")
    assert strategies.status_code == 200
    assert len(strategies.data["results"]) >= 1

    create = client.post(
        "/api/segments/ab-tests/",
        {
            "name": "Tone test",
            "variant_a": {
                "subject": "Hatırlatma",
                "tone": "polite",
                "channel": "EMAIL",
                "send_hour": 10,
                "reminder_interval_days": 7,
            },
            "variant_b": {
                "subject": "Son uyarı",
                "tone": "firm",
                "channel": "WHATSAPP",
                "send_hour": 16,
                "reminder_interval_days": 3,
            },
        },
        format="json",
    )
    assert create.status_code == 201, create.content
    tid = create.data["id"]
    assign = client.post(
        f"/api/segments/ab-tests/{tid}/assign/",
        {"customer_ids": [low.id, high.id]},
        format="json",
    )
    assert assign.status_code == 200
    assert assign.data["assigned"] == 2
    assert "payment_rate_7d" in assign.data["metrics"]["variants"]["A"]
