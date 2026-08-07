import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer, CustomerContact
from apps.customers.tests.tax_helpers import find_valid_tckn, find_valid_vkn
from apps.customers.validators import validate_turkish_tax_number
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
def org_owner(db):
    org = Organization.objects.create(name="Acme", slug="acme")
    owner = User.objects.create_user(
        email="owner@acme.com",
        password=PASSWORD,
        first_name="Ali",
        last_name="Yılmaz",
    )
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.mark.django_db
def test_soft_delete_sets_inactive(api_client, org_owner):
    org, owner = org_owner
    customer = Customer.objects.create(organization=org, name="Silinecek", code="DEL-1")
    client = _auth(api_client, owner, org)
    response = client.delete(f"/api/customers/{customer.id}/")
    assert response.status_code == status.HTTP_200_OK
    customer.refresh_from_db()
    assert customer.is_active is False
    assert Customer.objects.filter(pk=customer.pk).exists()


@pytest.mark.django_db
def test_unique_code_per_organization(api_client, org_owner):
    org, owner = org_owner
    Customer.objects.create(organization=org, name="Bir", code="SAME")
    client = _auth(api_client, owner, org)
    response = client.post(
        "/api/customers/",
        {"name": "İki", "code": "SAME"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "code" in response.data


@pytest.mark.django_db
def test_negative_credit_limit_rejected(api_client, org_owner):
    org, owner = org_owner
    client = _auth(api_client, owner, org)
    response = client.post(
        "/api/customers/",
        {"name": "Negatif", "credit_limit": "-10.00"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "credit_limit" in response.data


@pytest.mark.django_db
def test_negative_payment_term_rejected(api_client, org_owner):
    org, owner = org_owner
    client = _auth(api_client, owner, org)
    response = client.post(
        "/api/customers/",
        {"name": "Negatif Vade", "payment_term_days": -1},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_invalid_email_rejected(api_client, org_owner):
    org, owner = org_owner
    client = _auth(api_client, owner, org)
    response = client.post(
        "/api/customers/",
        {"name": "Mail", "email": "not-an-email"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


@pytest.mark.django_db
def test_tax_number_format(api_client, org_owner):
    org, owner = org_owner
    client = _auth(api_client, owner, org)

    bad = client.post(
        "/api/customers/",
        {"name": "Bad Tax", "tax_number": "123"},
        format="json",
    )
    assert bad.status_code == status.HTTP_400_BAD_REQUEST

    vkn = find_valid_vkn()
    ok = client.post(
        "/api/customers/",
        {"name": "Good Tax", "tax_number": vkn, "code": "TAX-1"},
        format="json",
    )
    assert ok.status_code == status.HTTP_201_CREATED

    tckn = find_valid_tckn()
    ok2 = client.post(
        "/api/customers/",
        {"name": "Good TCKN", "tax_number": tckn, "code": "TAX-2"},
        format="json",
    )
    assert ok2.status_code == status.HTTP_201_CREATED


def test_validator_rejects_bad_vkn():
    with pytest.raises(ValidationError):
        validate_turkish_tax_number("1111111111")


@pytest.mark.django_db
def test_list_filters_and_pagination(api_client, org_owner):
    org, owner = org_owner
    Customer.objects.create(
        organization=org,
        name="Riskli",
        code="R1",
        risk_status="HIGH",
        city="İstanbul",
        sector="Tekstil",
        assigned_user=owner,
    )
    Customer.objects.create(
        organization=org,
        name="Sakin",
        code="R2",
        risk_status="LOW",
        city="Ankara",
        sector="Gıda",
        is_active=False,
    )
    client = _auth(api_client, owner, org)
    response = client.get("/api/customers/", {"risk_status": "HIGH", "city": "İstanbul"})
    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] == "Riskli"

    inactive = client.get("/api/customers/", {"is_active": "false"})
    assert len(inactive.data["results"]) == 1
    assert inactive.data["results"][0]["name"] == "Sakin"


@pytest.mark.django_db
def test_contacts_primary_and_crud(api_client, org_owner):
    org, owner = org_owner
    customer = Customer.objects.create(organization=org, name="Contact Co", code="C1")
    client = _auth(api_client, owner, org)

    first = client.post(
        f"/api/customers/{customer.id}/contacts/",
        {
            "full_name": "Ayşe",
            "email": "ayse@example.com",
            "phone": "5551112233",
            "is_primary": True,
        },
        format="json",
    )
    assert first.status_code == status.HTTP_201_CREATED

    second = client.post(
        f"/api/customers/{customer.id}/contacts/",
        {
            "full_name": "Mehmet",
            "phone": "5554445566",
            "is_primary": True,
        },
        format="json",
    )
    assert second.status_code == status.HTTP_201_CREATED

    assert CustomerContact.objects.filter(customer=customer, is_primary=True).count() == 1
    primary = CustomerContact.objects.get(customer=customer, is_primary=True)
    assert primary.full_name == "Mehmet"

    detail = client.get(f"/api/customers/{customer.id}/")
    assert detail.status_code == status.HTTP_200_OK
    assert len(detail.data["contacts"]) == 2
