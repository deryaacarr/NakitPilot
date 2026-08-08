"""EPIC 36 — platform console, impersonation, flags, maintenance."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization, Role
from apps.platform.flags import is_feature_enabled
from apps.platform.models import FeatureFlag, MaintenanceMode, MaintenanceScope, MaintenanceWindow
from apps.platform.models import FeatureFlagKey

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def platform_ctx(db):
    org = Organization.objects.create(name="Ops Org", slug="ops-org")
    staff = User.objects.create_user(
        email="staff@nakitpilot.local", password=PASSWORD, is_staff=True
    )
    agent = User.objects.create_user(email="agent@ops-org.local", password=PASSWORD)
    Membership.objects.create(
        organization=org, user=agent, role=Role.COLLECTION_AGENT, is_active=True
    )
    staff_client = APIClient()
    login = staff_client.post(
        "/api/auth/login",
        {"email": staff.email, "password": PASSWORD},
        format="json",
    )
    staff_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    agent_client = APIClient()
    alogin = agent_client.post(
        "/api/auth/login",
        {"email": agent.email, "password": PASSWORD},
        format="json",
    )
    agent_client.credentials(HTTP_AUTHORIZATION=f"Bearer {alogin.data['access']}")
    agent_client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)

    return {
        "org": org,
        "staff": staff,
        "agent": agent,
        "staff_client": staff_client,
        "agent_client": agent_client,
    }


@pytest.mark.django_db
def test_overview_hides_customer_pii(platform_ctx):
    client = platform_ctx["staff_client"]
    res = client.get("/api/platform/overview/")
    assert res.status_code == 200, res.content
    assert res.data["privacy"]["customer_data_included"] is False
    assert "organizations" in res.data
    assert "ai_cost" in res.data
    assert "storage" in res.data
    # Must not expose customer name lists
    assert "customers" not in res.data
    assert "customer_aggregates" not in res.data


@pytest.mark.django_db
def test_feature_flag_org_and_percentage(platform_ctx):
    org = platform_ctx["org"]
    FeatureFlag.objects.create(
        key=FeatureFlagKey.LEGAL_MODULE,
        enabled=True,
        organization_ids=[org.id],
        rollout_percentage=100,
        environments=[],
    )
    assert is_feature_enabled(FeatureFlagKey.LEGAL_MODULE, organization=org) is True

    other = Organization.objects.create(name="Other", slug="other-org")
    assert is_feature_enabled(FeatureFlagKey.LEGAL_MODULE, organization=other) is False

    upsert = platform_ctx["staff_client"].post(
        "/api/platform/feature-flags/",
        {
            "key": FeatureFlagKey.WHATSAPP,
            "enabled": True,
            "rollout_percentage": 0,
        },
        format="json",
    )
    assert upsert.status_code in {200, 201}
    assert is_feature_enabled(FeatureFlagKey.WHATSAPP, organization=org) is False


@pytest.mark.django_db
def test_maintenance_read_only_blocks_writes(platform_ctx):
    org = platform_ctx["org"]
    MaintenanceWindow.objects.create(
        scope=MaintenanceScope.ORGANIZATION,
        mode=MaintenanceMode.READ_ONLY,
        organization=org,
        message="Bakım",
        is_active=True,
        starts_at=timezone.now() - timedelta(minutes=1),
    )
    client = platform_ctx["agent_client"]
    # GET should work
    board = client.get("/api/collection-tasks/today/")
    assert board.status_code == 200
    # POST should 503
    create = client.post(
        "/api/collection-tasks/",
        {
            "customer": 1,
            "due_date": timezone.localdate().isoformat(),
            "title": "x",
        },
        format="json",
    )
    assert create.status_code == 503
    assert create.json()["code"] == "maintenance_read_only"


@pytest.mark.django_db
def test_impersonation_requires_reason_and_blocks_sensitive_write(platform_ctx):
    staff_client = platform_ctx["staff_client"]
    agent = platform_ctx["agent"]
    org = platform_ctx["org"]

    bad = staff_client.post(
        "/api/platform/impersonation/start/",
        {"user_id": agent.id, "organization_id": org.id, "reason": "x"},
        format="json",
    )
    assert bad.status_code == 400

    start = staff_client.post(
        "/api/platform/impersonation/start/",
        {
            "user_id": agent.id,
            "organization_id": org.id,
            "reason": "Destek talebi #42 — oturum hatası",
            "duration_minutes": 15,
        },
        format="json",
    )
    assert start.status_code == 201, start.content
    assert start.data["sensitive_writes_blocked"] is True
    assert "banner" in start.data

    imp = APIClient()
    imp.credentials(HTTP_AUTHORIZATION=f"Bearer {start.data['access']}")
    imp.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)

    status = imp.get("/api/platform/impersonation/status/")
    assert status.status_code == 200
    assert status.data["active"] is True

    # Sensitive write blocked
    blocked = imp.post(
        "/api/payments/",
        {"customer": 1, "amount": "10.00", "payment_date": timezone.localdate().isoformat()},
        format="json",
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "impersonation_write_blocked"

    end = imp.post("/api/platform/impersonation/end/", {}, format="json")
    assert end.status_code == 200
    assert end.json()["ended"] is True
