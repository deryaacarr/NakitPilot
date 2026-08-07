"""EPIC 29 — NP-290–294 onboarding & analytics."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.onboarding.analytics import AnalyticsError, track_event
from apps.onboarding.sample_data import enable_sample_data
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def ob_ctx(db):
    org = Organization.objects.create(
        name="Onboard Co",
        slug="onboard-co",
        tax_number="1234567890",
        email="ops@onboard.example",
    )
    user = User.objects.create_user(email="onboard@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=user, role=Role.OWNER, is_active=True)
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
def test_wizard_steps(ob_ctx):
    _, _, client = ob_ctx
    state = client.get("/api/onboarding/")
    assert state.status_code == 200
    assert len(state.data["steps"]) == 7
    assert state.data["current_step"] == "company"

    patch = client.patch(
        "/api/onboarding/",
        {"current_step": "invite", "completed_steps": ["company"]},
        format="json",
    )
    assert patch.status_code == 200
    assert "company" in patch.data["completed_steps"]


@pytest.mark.django_db
def test_sample_data_separated(ob_ctx):
    org, _, client = ob_ctx
    result = enable_sample_data(org)
    assert result["customers"] == 20
    assert result["invoices"] == 50
    assert Customer.objects.filter(organization=org, is_sample=True).count() == 20
    assert Customer.objects.filter(organization=org, is_sample=False).count() == 0
    assert all(c.name.startswith("[ÖRNEK]") for c in Customer.objects.filter(is_sample=True))

    api = client.post("/api/onboarding/sample-data/", {}, format="json")
    assert api.status_code == 201

    deleted = client.delete("/api/onboarding/sample-data/")
    assert deleted.status_code == 200
    assert Customer.objects.filter(organization=org, is_sample=True).count() == 0


@pytest.mark.django_db
def test_progress_score(ob_ctx):
    org, _, client = ob_ctx
    Customer.objects.create(organization=org, name="Real", code="R1", is_sample=False)
    prog = client.get("/api/onboarding/progress/")
    assert prog.status_code == 200
    assert prog.data["score"] >= 30  # company 10 + first customer 20
    keys = {i["key"]: i["done"] for i in prog.data["items"]}
    assert keys["company_completed"] is True
    assert keys["first_customer"] is True


@pytest.mark.django_db
def test_guidance_and_analytics(ob_ctx):
    org, _, client = ob_ctx
    g = client.get("/api/onboarding/guidance/")
    assert g.status_code == 200
    assert "empty_states" in g.data
    assert "tooltips" in g.data
    assert "checklist" in g.data
    assert "sample_report" in g.data
    assert "help_links" in g.data
    assert "announcements" in g.data

    ok = client.post(
        "/api/onboarding/events/",
        {"event_name": "integration_connected", "properties": {"provider": "kolaybi"}},
        format="json",
    )
    assert ok.status_code == 201

    # Reject PII-ish properties silently (sanitized away) but allow event
    ok2 = client.post(
        "/api/onboarding/events/",
        {
            "event_name": "invoice_imported",
            "properties": {"email": "x@y.com", "amount": 1000, "source": "csv"},
        },
        format="json",
    )
    assert ok2.status_code == 201
    assert "email" not in ok2.data["properties"]
    assert "amount" not in ok2.data["properties"]
    assert ok2.data["properties"].get("source") == "csv"

    with pytest.raises(AnalyticsError):
        track_event(org, "password_leaked", {})
