"""EPIC 30 / 31 — enterprise auth + KVKK governance."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.billing.models import PlanCode
from apps.billing.subscription_service import ensure_default_plans, ensure_subscription
from apps.billing.models import Subscription, SubscriptionStatus
from apps.customers.models import Customer
from apps.governance.approvals import decide_approval, request_approval
from apps.governance.masking import mask_email_display, mask_phone_display, mask_tax_display
from apps.governance.models import ApprovalActionType, DeletionRequestStatus
from apps.organizations.custom_roles import ensure_role_templates
from apps.organizations.models import Membership, Organization, Role
from apps.organizations.structure import CustomerAssignment

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def gov_ctx(db):
    org = Organization.objects.create(name="Gov Co", slug="gov-co")
    user = User.objects.create_user(email="gov@example.com", password=PASSWORD)
    other = User.objects.create_user(email="approver@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=user, role=Role.OWNER, is_active=True)
    Membership.objects.create(organization=org, user=other, role=Role.ADMIN, is_active=True)
    from apps.billing.models import SubscriptionPlan

    ensure_default_plans()
    sub = ensure_subscription(org, plan_code=PlanCode.STARTER)
    sub.plan = SubscriptionPlan.objects.get(code=PlanCode.ENTERPRISE)
    sub.status = SubscriptionStatus.ACTIVE
    sub.trial_ends_at = None
    sub.read_only = False
    sub.save()
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return org, user, other, client, login.data


@pytest.mark.django_db
def test_custom_roles_and_templates(gov_ctx):
    org, _, _, client, _ = gov_ctx
    ensure_role_templates(org)
    resp = client.get("/api/organizations/roles/")
    assert resp.status_code == 200
    names = {r["name"] for r in resp.data["results"]}
    assert "Bölge Tahsilat Uzmanı" in names
    assert "Sadece Rapor" in names

    created = client.post(
        "/api/organizations/roles/",
        {
            "name": "Özel Test Rolü",
            "permissions": ["view_reports"],
            "resource_rules": {"customers": "assigned_only", "payments": "read"},
        },
        format="json",
    )
    assert created.status_code == 201


@pytest.mark.django_db
def test_branch_team_assignment_and_scope(gov_ctx):
    org, user, _, client, _ = gov_ctx
    branch = client.post(
        "/api/organizations/branches/",
        {"name": "Ankara", "code": "ANK"},
        format="json",
    )
    assert branch.status_code == 201
    team = client.post(
        "/api/organizations/teams/",
        {"name": "Tahsilat A", "branch_id": branch.data["id"]},
        format="json",
    )
    assert team.status_code == 201

    c1 = Customer.objects.create(organization=org, name="Atanan", code="A1")
    c2 = Customer.objects.create(organization=org, name="Diğer", code="A2")
    CustomerAssignment.objects.create(organization=org, customer=c1, user=user)

    # Attach custom assigned-only role
    roles = client.get("/api/organizations/roles/")
    agent = next(r for r in roles.data["results"] if r["slug"] == "bolge-tahsilat-uzmani")
    Membership.objects.filter(organization=org, user=user).update(
        custom_role_id=agent["id"],
        role=Role.COLLECTION_AGENT,
    )
    rules = client.get("/api/organizations/resource-rules/me/")
    assert rules.status_code == 200
    assert rules.data["resource_rules"]["customers"] == "assigned_only"

    listed = client.get("/api/customers/")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.data.get("results", listed.data if isinstance(listed.data, list) else [])}
    # pagination may wrap results
    if not ids and "results" in listed.data:
        ids = {row["id"] for row in listed.data["results"]}
    assert c1.id in ids
    assert c2.id not in ids


@pytest.mark.django_db
def test_approvals_sso_sessions(gov_ctx):
    org, user, other, client, login = gov_ctx
    assert "session" in login

    sessions = client.get("/api/auth/sessions/")
    assert sessions.status_code == 200
    assert len(sessions.data["results"]) >= 1

    a = request_approval(
        org,
        action_type=ApprovalActionType.CREDIT_LIMIT_CHANGE,
        requested_by=user,
        payload={"customer_id": 1, "limit": 50000},
    )
    decided = decide_approval(a, decided_by=other, approve=True)
    assert decided.status == "APPROVED"

    sso = client.post(
        "/api/governance/sso/providers/",
        {
            "protocol": "OIDC",
            "name": "Entra",
            "is_enabled": True,
            "domains": ["gov-co.example"],
        },
        format="json",
    )
    assert sso.status_code == 201


@pytest.mark.django_db
def test_kvkk_retention_export_deletion_mask_inventory(gov_ctx):
    org, _, _, client, _ = gov_ctx
    Customer.objects.create(organization=org, name="C", code="C1", email="mehmet@firma.com")

    ret = client.get("/api/governance/retention/")
    assert ret.status_code == 200
    assert ret.data["audit_logs_days"] == 365 * 10
    assert ret.data["import_files_days"] == 90

    export = client.post(
        "/api/governance/exports/",
        {"datasets": ["customers", "audit"]},
        format="json",
    )
    assert export.status_code == 201
    assert export.data["status"] == "READY"

    deletion = client.post(
        "/api/governance/deletion-requests/",
        {"target_type": "organization", "target_id": str(org.id), "reason": "test"},
        format="json",
    )
    assert deletion.status_code == 201
    assert deletion.data["status"] == DeletionRequestStatus.WAITING

    cancel = client.post(f"/api/governance/deletion-requests/{deletion.data['id']}/cancel/")
    assert cancel.status_code == 200
    assert cancel.data["status"] == "CANCELLED"

    mask = client.post(
        "/api/governance/mask-preview/",
        {"phone": "05321234567", "email": "mehmet@firma.com", "tax_number": "1234567890"},
        format="json",
    )
    assert mask.status_code == 200
    assert "***" in mask.data["phone"]
    assert mask.data["email"] == mask_email_display("mehmet@firma.com")
    assert mask.data["tax_number"].endswith("7890")

    inv = client.get("/api/governance/inventory/")
    assert inv.status_code == 200
    assert len(inv.data["results"]) >= 5

    access = client.get("/api/governance/access-report/")
    assert access.status_code == 200

    assert mask_phone_display("05321234567").startswith("0532")
    assert mask_tax_display("1234567890") == "******7890"
