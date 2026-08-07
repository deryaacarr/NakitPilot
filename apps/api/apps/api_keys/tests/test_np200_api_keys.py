"""NP-200 — API key management."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.api_keys.models import ApiKey
from apps.api_keys.services import authenticate_api_key, create_api_key, mark_api_key_used
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
def setup_org(db):
    org = Organization.objects.create(name="NP200 Org", slug="np200-org")
    owner = User.objects.create_user(email="np200-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    viewer = User.objects.create_user(email="np200-viewer@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=viewer, role=Role.VIEWER, is_active=True)
    return org, owner, viewer


@pytest.mark.django_db
def test_create_list_revoke_and_secret_once(api_client, setup_org):
    org, owner, _viewer = setup_org
    client = _auth(api_client, owner, org)

    scopes = client.get("/api/api-keys/scopes/")
    assert scopes.status_code == 200
    values = {s["value"] for s in scopes.data["scopes"]}
    assert "customers:read" in values
    assert "forecast:read" in values

    created = client.post(
        "/api/api-keys/",
        {
            "name": "ERP",
            "scopes": ["customers:read", "invoices:read"],
        },
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["name"] == "ERP"
    assert created.data["scopes"] == ["customers:read", "invoices:read"]
    raw_key = created.data["key"]
    assert raw_key.startswith("npk_")
    assert "_" in raw_key[4:]
    key_id = created.data["id"]

    listed = client.get("/api/api-keys/")
    assert listed.status_code == 200
    rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
    assert len(rows) == 1
    assert "key" not in rows[0]
    assert rows[0]["display_prefix"].startswith("npk_")
    assert rows[0]["last_used_at"] is None
    assert rows[0]["is_active"] is True

    detail = client.get(f"/api/api-keys/{key_id}/")
    assert detail.status_code == 200
    assert "key" not in detail.data

    # Raw key authenticates and updates last_used
    assert authenticate_api_key(raw_key) is not None
    mark_api_key_used(ApiKey.objects.get(pk=key_id), min_interval_seconds=0)
    assert ApiKey.objects.get(pk=key_id).last_used_at is not None

    probe = APIClient()
    probe.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
    me = probe.get("/api/auth/me")
    assert me.status_code == 200
    assert me.data["email"] == owner.email

    # last_used refreshed via auth path
    ApiKey.objects.filter(pk=key_id).update(last_used_at=None)
    me2 = probe.get("/api/auth/me")
    assert me2.status_code == 200
    assert ApiKey.objects.get(pk=key_id).last_used_at is not None

    revoked = client.post(f"/api/api-keys/{key_id}/revoke/")
    assert revoked.status_code == 200
    assert revoked.data["is_active"] is False
    assert revoked.data["revoked_at"] is not None

    assert authenticate_api_key(raw_key) is None
    again = client.post(f"/api/api-keys/{key_id}/revoke/")
    assert again.status_code == 400


@pytest.mark.django_db
def test_viewer_cannot_manage_api_keys(api_client, setup_org):
    org, _owner, viewer = setup_org
    client = _auth(api_client, viewer, org)
    response = client.post(
        "/api/api-keys/",
        {"name": "Nope", "scopes": ["customers:read"]},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_invalid_scope_rejected(api_client, setup_org):
    org, owner, _viewer = setup_org
    client = _auth(api_client, owner, org)
    response = client.post(
        "/api/api-keys/",
        {"name": "Bad", "scopes": ["customers:read", "admin:all"]},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_api_key_service_hashes_secret(setup_org):
    org, owner, _viewer = setup_org
    api_key, raw = create_api_key(
        organization=org,
        name="Service",
        scopes=["risk:read"],
        created_by=owner,
    )
    assert raw not in (api_key.key_hash, api_key.prefix)
    assert api_key.key_hash != raw
    assert authenticate_api_key(raw).pk == api_key.pk
    assert authenticate_api_key("npk_deadbeef_not-a-real-key") is None
