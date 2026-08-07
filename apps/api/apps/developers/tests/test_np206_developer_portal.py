"""NP-206 — Developer portal APIs."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.api_keys.models import ApiRequestLog
from apps.api_keys.services import create_api_key
from apps.organizations.models import Membership, Organization, Role
from apps.webhooks.services import create_endpoint

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def setup(db):
    org = Organization.objects.create(name="NP206 Org", slug="np206-org")
    owner = User.objects.create_user(email="np206-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


def _auth(client, user, org):
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return client


@pytest.mark.django_db
def test_developer_docs_catalog(setup):
    org, owner = setup
    client = _auth(APIClient(), owner, org)
    res = client.get("/api/developers/docs/")
    assert res.status_code == 200
    assert res.data["openapi_docs_url"] == "/api/v1/docs"
    assert any(e["path"] == "/api/v1/customers" for e in res.data["endpoints"])
    assert any(e["value"] == "payment.created" for e in res.data["webhook_events"])


@pytest.mark.django_db
def test_usage_and_errors(setup):
    org, owner = setup
    key, raw = create_api_key(
        organization=org,
        name="Portal",
        scopes=["customers:read"],
        created_by=owner,
    )
    ApiRequestLog.objects.create(
        organization=org,
        api_key=key,
        method="GET",
        path="/api/v1/customers",
        status_code=200,
        duration_ms=12,
    )
    ApiRequestLog.objects.create(
        organization=org,
        api_key=key,
        method="POST",
        path="/api/v1/customers",
        status_code=400,
        error_detail="bad",
        duration_ms=8,
    )
    client = _auth(APIClient(), owner, org)
    usage = client.get("/api/developers/usage/?days=7")
    assert usage.status_code == 200
    assert usage.data["totals"]["total"] == 2
    assert usage.data["totals"]["errors"] == 1
    assert len(usage.data["series"]) == 7

    errors = client.get("/api/developers/errors/")
    assert errors.status_code == 200
    assert any(r["source"] == "api" and r["status_code"] == 400 for r in errors.data["results"])


@pytest.mark.django_db
def test_webhook_test_send(setup):
    org, owner = setup
    endpoint, _secret, _subs = create_endpoint(
        organization=org,
        name="Test EP",
        url="https://example.com/hook",
        event_types=["payment.created"],
        created_by=owner,
    )
    client = _auth(APIClient(), owner, org)
    with patch("apps.webhooks.delivery.urllib.request.urlopen") as urlopen:
        mock = urlopen.return_value.__enter__.return_value
        mock.status = 200
        mock.getcode.return_value = 200
        mock.read.return_value = b"ok"
        res = client.post(
            f"/api/webhooks/endpoints/{endpoint.id}/test/",
            {"event_type": "payment.created"},
            format="json",
        )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.data["deliveries"][0]["status"] == "succeeded"
