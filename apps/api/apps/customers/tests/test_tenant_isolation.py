import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.customers.models import Customer
from apps.organizations.middleware import TenantMiddleware
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
    org = Organization.objects.create(name="Company A", slug="company-a")
    owner = User.objects.create_user(email="a-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.fixture
def company_b(db):
    org = Organization.objects.create(name="Company B", slug="company-b")
    owner = User.objects.create_user(email="b-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.mark.django_db
def test_user_cannot_list_other_company_customers(api_client, company_a, company_b):
    org_a, user_a = company_a
    org_b, _user_b = company_b

    Customer.objects.create(organization=org_a, name="A Customer", code="A-1")
    Customer.objects.create(organization=org_b, name="B Customer", code="B-1")

    client = _auth(api_client, user_a, org_a)
    response = client.get("/api/customers/")
    assert response.status_code == status.HTTP_200_OK
    payload = response.data["results"] if isinstance(response.data, dict) else response.data
    names = [item["name"] for item in payload]
    assert names == ["A Customer"]
    assert "B Customer" not in names


@pytest.mark.django_db
def test_url_id_from_other_tenant_returns_404(api_client, company_a, company_b):
    org_a, user_a = company_a
    org_b, _user_b = company_b

    foreign = Customer.objects.create(organization=org_b, name="Secret B", code="B-SECRET")

    client = _auth(api_client, user_a, org_a)
    response = client.get(f"/api/customers/{foreign.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    body = str(response.data).lower()
    assert "secret b" not in body
    assert "b-secret" not in body


@pytest.mark.django_db
def test_cannot_create_customer_into_other_organization(api_client, company_a, company_b):
    org_a, user_a = company_a
    org_b, _user_b = company_b

    client = _auth(api_client, user_a, org_a)
    response = client.post(
        "/api/customers/",
        {
            "name": "Should Stay In A",
            "code": "A-NEW",
            "organization": org_b.id,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    customer = Customer.objects.get(id=response.data["id"])
    assert customer.organization_id == org_a.id
    assert customer.organization_id != org_b.id


@pytest.mark.django_db
def test_missing_organization_header_denied(api_client, company_a):
    _org_a, user_a = company_a
    login = api_client.post(
        "/api/auth/login",
        {"email": user_a.email, "password": PASSWORD},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    response = api_client.get("/api/customers/")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_middleware_sets_current_organization(company_a):
    org_a, user_a = company_a
    factory = RequestFactory()
    token = str(RefreshToken.for_user(user_a).access_token)
    request = factory.get(
        "/api/customers/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_ORGANIZATION_ID=str(org_a.id),
    )
    request.user = AnonymousUser()

    seen = {}

    def _view(req):
        seen["organization_id"] = req.organization.id
        seen["current_organization_id"] = req.user.current_organization.id
        return req

    TenantMiddleware(_view)(request)
    assert seen["organization_id"] == org_a.id
    assert seen["current_organization_id"] == org_a.id
