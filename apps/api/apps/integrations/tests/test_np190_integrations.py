import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.integrations.models import IntegrationConnection, IntegrationCredential
from apps.integrations.services import get_connection_credentials
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
def company_a(db):
    org = Organization.objects.create(name="Company A", slug="integ-company-a")
    owner = User.objects.create_user(email="integ-a-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.fixture
def company_b(db):
    org = Organization.objects.create(name="Company B", slug="integ-company-b")
    owner = User.objects.create_user(email="integ-b-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.fixture
def viewer_a(company_a):
    org, _owner = company_a
    viewer = User.objects.create_user(email="integ-a-viewer@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=viewer, role=Role.VIEWER, is_active=True)
    return org, viewer


@pytest.mark.django_db
def test_list_providers(api_client, company_a):
    org, owner = company_a
    client = _auth(api_client, owner, org)
    response = client.get("/api/integrations/providers/")
    assert response.status_code == status.HTTP_200_OK
    providers = {item["provider"] for item in response.data}
    assert "kolaybi" in providers


@pytest.mark.django_db
def test_org_can_create_multiple_connections_same_provider_different_companies(
    api_client, company_a
):
    org, owner = company_a
    client = _auth(api_client, owner, org)

    first = client.post(
        "/api/integrations/connections/",
        {
            "provider": "kolaybi",
            "external_company_id": "kb-1",
            "external_company_name": "Firma 1",
        },
        format="json",
    )
    second = client.post(
        "/api/integrations/connections/",
        {
            "provider": "kolaybi",
            "external_company_id": "kb-2",
            "external_company_name": "Firma 2",
        },
        format="json",
    )
    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    assert first.data["id"] != second.data["id"]
    assert IntegrationConnection.objects.filter(organization=org).count() == 2


@pytest.mark.django_db
def test_duplicate_provider_company_rejected(api_client, company_a):
    org, owner = company_a
    client = _auth(api_client, owner, org)
    payload = {
        "provider": "kolaybi",
        "external_company_id": "kb-dup",
        "external_company_name": "Dup",
    }
    assert client.post("/api/integrations/connections/", payload, format="json").status_code == 201
    again = client.post("/api/integrations/connections/", payload, format="json")
    assert again.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_unknown_provider_rejected(api_client, company_a):
    org, owner = company_a
    client = _auth(api_client, owner, org)
    response = client.post(
        "/api/integrations/connections/",
        {"provider": "unknown-erp", "external_company_id": "x"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_tenant_isolation_list_and_detail(api_client, company_a, company_b):
    org_a, user_a = company_a
    org_b, _user_b = company_b

    foreign = IntegrationConnection.objects.create(
        organization=org_b,
        provider="kolaybi",
        external_company_id="secret-b",
        external_company_name="Secret B Co",
    )
    IntegrationConnection.objects.create(
        organization=org_a,
        provider="kolaybi",
        external_company_id="a-1",
        external_company_name="A Co",
    )

    client = _auth(api_client, user_a, org_a)
    listed = client.get("/api/integrations/connections/")
    assert listed.status_code == status.HTTP_200_OK
    payload = listed.data["results"] if isinstance(listed.data, dict) else listed.data
    ids = [item["id"] for item in payload]
    assert foreign.id not in ids
    assert all(item["external_company_id"] != "secret-b" for item in payload)

    detail = client.get(f"/api/integrations/connections/{foreign.id}/")
    assert detail.status_code == status.HTTP_404_NOT_FOUND
    body = str(detail.data).lower()
    assert "secret" not in body


@pytest.mark.django_db
def test_credentials_encrypted_and_never_returned(api_client, company_a):
    org, owner = company_a
    client = _auth(api_client, owner, org)

    created = client.post(
        "/api/integrations/connections/",
        {
            "provider": "kolaybi",
            "external_company_id": "kb-cred",
            "external_company_name": "Cred Co",
        },
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    connection_id = created.data["id"]
    assert created.data["has_credentials"] is False
    assert "api_key" not in created.data
    assert "encrypted_payload" not in created.data

    secret = "super-secret-kolaybi-key-ABCDEFGH"
    put = client.put(
        f"/api/integrations/connections/{connection_id}/credentials/",
        {"credentials": {"api_key": secret, "channel_id": "channel-demo"}},
        format="json",
    )
    assert put.status_code == status.HTTP_200_OK
    assert put.data["has_credentials"] is True
    assert put.data["key_hint"] == secret[-4:]
    assert secret not in str(put.data)
    assert "api_key" not in put.data
    assert "encrypted_payload" not in put.data

    status_get = client.get(f"/api/integrations/connections/{connection_id}/credentials/")
    assert status_get.status_code == status.HTTP_200_OK
    assert status_get.data["has_credentials"] is True
    assert secret not in str(status_get.data)
    assert "api_key" not in status_get.data

    detail = client.get(f"/api/integrations/connections/{connection_id}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["has_credentials"] is True
    assert detail.data["status"] == "connected"
    assert secret not in str(detail.data)
    assert "encrypted_payload" not in detail.data

    cred = IntegrationCredential.objects.get(connection_id=connection_id)
    assert cred.encrypted_payload
    assert secret not in cred.encrypted_payload
    assert get_connection_credentials(cred.connection)["api_key"] == secret


@pytest.mark.django_db
def test_viewer_cannot_manage_integrations(api_client, viewer_a):
    org, viewer = viewer_a
    client = _auth(api_client, viewer, org)
    response = client.get("/api/integrations/connections/")
    assert response.status_code == status.HTTP_403_FORBIDDEN
