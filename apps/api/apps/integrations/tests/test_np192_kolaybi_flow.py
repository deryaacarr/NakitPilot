"""NP-192 — KolayBi connection wizard API flow."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.integrations.models import IntegrationConnection
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
def owner_org(db):
    org = Organization.objects.create(name="KB Org", slug="kb-org-np192")
    owner = User.objects.create_user(email="kb-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


def _create_connection_with_mock_creds(client):
    created = client.post(
        "/api/integrations/connections/",
        {"provider": "kolaybi", "external_company_id": "", "external_company_name": ""},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    connection_id = created.data["id"]
    put = client.put(
        f"/api/integrations/connections/{connection_id}/credentials/",
        {
            "credentials": {
                "api_key": "mock-demo-key-1234",
                "channel_id": "mock-channel",
            }
        },
        format="json",
    )
    assert put.status_code == status.HTTP_200_OK
    return connection_id


@pytest.mark.django_db
def test_wizard_flow_test_companies_select_settings_sync(api_client, owner_org):
    org, owner = owner_org
    client = _auth(api_client, owner, org)
    connection_id = _create_connection_with_mock_creds(client)

    tested = client.post(f"/api/integrations/connections/{connection_id}/test/")
    assert tested.status_code == status.HTTP_200_OK
    assert tested.data["result"]["ok"] is True

    companies = client.get(f"/api/integrations/connections/{connection_id}/companies/")
    assert companies.status_code == status.HTTP_200_OK
    assert len(companies.data) >= 2
    company = companies.data[0]

    selected = client.post(
        f"/api/integrations/connections/{connection_id}/select-company/",
        {
            "external_company_id": company["external_id"],
            "external_company_name": company["name"],
        },
        format="json",
    )
    assert selected.status_code == status.HTTP_200_OK
    assert selected.data["external_company_id"] == company["external_id"]
    assert selected.data["external_company_name"] == company["name"]

    settings_resp = client.patch(
        f"/api/integrations/connections/{connection_id}/sync-settings/",
        {"sync_frequency": "daily"},
        format="json",
    )
    assert settings_resp.status_code == status.HTTP_200_OK
    assert settings_resp.data["sync_frequency"] == "daily"
    assert settings_resp.data["next_sync_at"]

    sync = client.post(
        f"/api/integrations/connections/{connection_id}/sync/",
        {"job_type": "initial"},
        format="json",
    )
    assert sync.status_code == status.HTTP_201_CREATED
    assert sync.data["job"]["status"] == "completed"
    assert sync.data["connection"]["last_successful_sync_at"]
    assert sync.data["connection"]["last_error"] == ""
    assert sync.data["connection"]["status"] == "connected"

    detail = client.get(f"/api/integrations/connections/{connection_id}/")
    assert detail.data["last_error"] == ""
    assert detail.data["external_company_name"] == company["name"]


@pytest.mark.django_db
def test_manual_sync_requires_company(api_client, owner_org):
    org, owner = owner_org
    client = _auth(api_client, owner, org)
    connection_id = _create_connection_with_mock_creds(client)
    sync = client.post(
        f"/api/integrations/connections/{connection_id}/sync/",
        {"job_type": "manual"},
        format="json",
    )
    assert sync.status_code == status.HTTP_400_BAD_REQUEST
