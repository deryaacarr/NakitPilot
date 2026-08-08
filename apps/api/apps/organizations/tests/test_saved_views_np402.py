import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization, Role
from apps.organizations.saved_views import SavedTableView

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
def org_user(db):
    org = Organization.objects.create(name="Views Co", slug="views-co")
    user = User.objects.create_user(email="views@test.local", password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=Role.OWNER, is_active=True)
    return org, user


@pytest.mark.django_db
def test_saved_view_crud_share_and_default(api_client, org_user):
    org, user = org_user
    client = _auth(api_client, user, org)

    create = client.post(
        "/api/saved-views/",
        {
            "resource": "invoices",
            "name": "90+ gün",
            "filters": {"overdue_days_min": "90", "status": "OVERDUE"},
            "hidden_columns": ["invoice_date"],
            "sort": {"id": "due_date", "direction": "asc"},
            "is_shared": True,
            "is_default": True,
        },
        format="json",
    )
    assert create.status_code == 201
    view_id = create.data["id"]
    assert create.data["is_shared"] is True
    assert create.data["share_token"]

    listed = client.get("/api/saved-views/", {"resource": "invoices"})
    assert listed.status_code == 200
    rows = listed.data if isinstance(listed.data, list) else listed.data["results"]
    assert any(r["id"] == view_id for r in rows)

    token = create.data["share_token"]
    by_token = client.get(f"/api/saved-views/by-token/{token}/")
    assert by_token.status_code == 200
    assert by_token.data["name"] == "90+ gün"

    other = client.post(
        "/api/saved-views/",
        {
            "resource": "invoices",
            "name": "Kritik",
            "filters": {"risk_status": "CRITICAL"},
            "is_default": True,
        },
        format="json",
    )
    assert other.status_code == 201
    assert SavedTableView.objects.filter(
        organization=org, resource="invoices", is_default=True
    ).count() == 1
    assert SavedTableView.objects.get(pk=other.data["id"]).is_default is True
