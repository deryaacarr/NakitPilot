import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="owner@example.com", password=PASSWORD)


@pytest.fixture
def auth_client(api_client, user):
    login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return api_client


@pytest.mark.django_db
def test_create_organization(auth_client):
    response = auth_client.post(
        "/api/organizations/",
        {
            "name": "Acme Ticaret A.Ş.",
            "tax_number": "1234567890",
            "phone": "+905551112233",
            "email": "finance@acme.example",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Acme Ticaret A.Ş."
    assert response.data["slug"] == "acme-ticaret-as"
    assert response.data["default_currency"] == "TRY"
    assert response.data["timezone"] == "Europe/Istanbul"
    assert response.data["is_active"] is True
    assert Organization.objects.filter(slug="acme-ticaret-as").exists()


@pytest.mark.django_db
def test_update_organization_info(auth_client, user):
    org = Organization.objects.create(name="Eski Unvan", slug="eski-unvan")
    Membership.objects.create(organization=org, user=user, role=Role.OWNER, is_active=True)
    response = auth_client.patch(
        f"/api/organizations/{org.id}/",
        {
            "name": "Yeni Unvan Ltd.",
            "email": "yeni@example.com",
            "phone": "+905559998877",
            "tax_number": "9876543210",
            "timezone": "Europe/Istanbul",
            "default_currency": "try",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    org.refresh_from_db()
    assert org.name == "Yeni Unvan Ltd."
    assert org.email == "yeni@example.com"
    assert org.default_currency == "TRY"


@pytest.mark.django_db
def test_deactivate_and_reactivate_organization(auth_client, user):
    org = Organization.objects.create(name="Aktif Firma", slug="aktif-firma")
    Membership.objects.create(organization=org, user=user, role=Role.OWNER, is_active=True)
    assert org.is_active is True

    deactivated = auth_client.patch(
        f"/api/organizations/{org.id}/",
        {"is_active": False},
        format="json",
    )
    assert deactivated.status_code == status.HTTP_200_OK
    org.refresh_from_db()
    assert org.is_active is False

    reactivated = auth_client.patch(
        f"/api/organizations/{org.id}/",
        {"is_active": True},
        format="json",
    )
    assert reactivated.status_code == status.HTTP_200_OK
    org.refresh_from_db()
    assert org.is_active is True


@pytest.mark.django_db
def test_create_organization_requires_auth(api_client):
    response = api_client.post(
        "/api/organizations/",
        {"name": "Yetkisiz"},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_slug_uniqueness_on_save():
    Organization.objects.create(name="Demo Co", slug="demo-co")
    second = Organization(name="Demo Co")
    second.save()
    assert second.slug == "demo-co-2"


@pytest.mark.django_db
def test_organization_url_names():
    assert reverse("organization-list-create") == "/api/organizations/"
    assert reverse("organization-detail", kwargs={"pk": 1}) == "/api/organizations/1/"
