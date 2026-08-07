"""NP-193 — KolayBi customer sync: pagination, upsert, ownership."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer, CustomerSource, RiskStatus
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
def setup_org(db):
    org = Organization.objects.create(name="NP193 Org", slug="np193-org")
    owner = User.objects.create_user(email="np193-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


def _ready_connection(client) -> int:
    created = client.post(
        "/api/integrations/connections/",
        {"provider": "kolaybi", "external_company_id": "", "external_company_name": ""},
        format="json",
    )
    assert created.status_code == 201
    cid = created.data["id"]
    assert (
        client.put(
            f"/api/integrations/connections/{cid}/credentials/",
            {"credentials": {"api_key": "mock-np193-key", "channel_id": "ch-np193"}},
            format="json",
        ).status_code
        == 200
    )
    companies = client.get(f"/api/integrations/connections/{cid}/companies/")
    assert companies.status_code == 200
    company = companies.data[0]
    selected = client.post(
        f"/api/integrations/connections/{cid}/select-company/",
        {
            "external_company_id": company["external_id"],
            "external_company_name": company["name"],
        },
        format="json",
    )
    assert selected.status_code == 200
    return cid


@pytest.mark.django_db
def test_customer_sync_paginated_upsert_no_duplicates(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    connection_id = _ready_connection(client)

    first = client.post(
        f"/api/integrations/connections/{connection_id}/sync/",
        {"job_type": "initial"},
        format="json",
    )
    assert first.status_code == status.HTTP_201_CREATED
    stats = first.data["job"]["stats_json"]["customers"]
    assert stats["pages"] >= 2
    assert stats["fetched"] == 4
    assert stats["created"] == 4

    customers = Customer.objects.filter(organization=org, source=CustomerSource.KOLAYBI)
    assert customers.count() == 4
    assert customers.filter(external_id="kb-cust-3", is_active=False).exists()
    assert all(c.source == CustomerSource.KOLAYBI for c in customers)

    second = client.post(
        f"/api/integrations/connections/{connection_id}/sync/",
        {"job_type": "manual"},
        format="json",
    )
    assert second.status_code == status.HTTP_201_CREATED
    stats2 = second.data["job"]["stats_json"]["customers"]
    assert stats2["created"] == 0
    assert Customer.objects.filter(organization=org, source=CustomerSource.KOLAYBI).count() == 4


@pytest.mark.django_db
def test_local_overrides_and_nakitpilot_fields_preserved(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    connection_id = _ready_connection(client)
    assert (
        client.post(
            f"/api/integrations/connections/{connection_id}/sync/",
            {"job_type": "initial"},
            format="json",
        ).status_code
        == 201
    )

    customer = Customer.objects.get(organization=org, external_id="kb-cust-1")
    customer.notes = "Dahili tahsilat notu"
    customer.collection_strategy = "haftalik-arama"
    customer.risk_status = RiskStatus.HIGH
    customer.assigned_user = owner
    customer.name = "Yerel Ad Override"
    customer.local_field_overrides = ["name"]
    customer.save()

    assert (
        client.post(
            f"/api/integrations/connections/{connection_id}/sync/",
            {"job_type": "manual"},
            format="json",
        ).status_code
        == 201
    )

    customer.refresh_from_db()
    assert customer.name == "Yerel Ad Override"
    assert customer.notes == "Dahili tahsilat notu"
    assert customer.collection_strategy == "haftalik-arama"
    assert customer.risk_status == RiskStatus.HIGH
    assert customer.assigned_user_id == owner.id
    # Non-overridden KolayBi field still updates from source on later syncs
    assert customer.email == "alpha@example.com"


@pytest.mark.django_db
def test_api_edit_marks_local_override(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    connection_id = _ready_connection(client)
    client.post(
        f"/api/integrations/connections/{connection_id}/sync/",
        {"job_type": "initial"},
        format="json",
    )
    customer = Customer.objects.get(organization=org, external_id="kb-cust-2")
    patched = client.patch(
        f"/api/customers/{customer.id}/",
        {"phone": "+905559999999"},
        format="json",
    )
    assert patched.status_code == 200
    assert "phone" in patched.data["local_field_overrides"]

    client.post(
        f"/api/integrations/connections/{connection_id}/sync/",
        {"job_type": "manual"},
        format="json",
    )
    customer.refresh_from_db()
    assert customer.phone == "+905559999999"
