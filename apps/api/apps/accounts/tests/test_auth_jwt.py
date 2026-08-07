import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

PASSWORD = "SecretPass123!"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="agent@example.com",
        password=PASSWORD,
        first_name="Ali",
        last_name="Yilmaz",
    )


@pytest.fixture
def auth_client(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client, user, str(refresh)


@pytest.mark.django_db
def test_login_returns_short_lived_access_and_refresh(api_client, user):
    response = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["user"]["email"] == user.email

    access = RefreshToken(response.data["refresh"]).access_token
    # Access lifetime must be short (≤ 30 minutes) relative to refresh.
    access_lifetime = api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()
    refresh_lifetime = api_settings.REFRESH_TOKEN_LIFETIME.total_seconds()
    assert access_lifetime <= 30 * 60
    assert refresh_lifetime > access_lifetime
    assert access_lifetime == 15 * 60
    del access


@pytest.mark.django_db
def test_inactive_user_cannot_login(api_client, user):
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["code"] == "inactive_account"


@pytest.mark.django_db
def test_login_invalid_email_code(api_client):
    response = api_client.post(
        "/api/auth/login",
        {"email": "missing@example.com", "password": PASSWORD},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["code"] == "invalid_email"


@pytest.mark.django_db
def test_login_invalid_password_code(api_client, user):
    response = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": "WrongPass123!"},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["code"] == "invalid_password"


@pytest.mark.django_db
def test_refresh_issues_new_tokens(api_client, user):
    login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    refresh = login.data["refresh"]

    response = api_client.post(
        "/api/auth/refresh",
        {"refresh": refresh},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    # Rotation enabled → new refresh token returned
    assert "refresh" in response.data
    assert response.data["refresh"] != refresh


@pytest.mark.django_db
def test_me_requires_auth_and_returns_profile(api_client, user):
    anonymous = api_client.get("/api/auth/me")
    assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED

    login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    response = api_client.get("/api/auth/me")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["first_name"] == "Ali"


@pytest.mark.django_db
def test_logout_blacklists_refresh_token(api_client, user):
    login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    access = login.data["access"]
    refresh = login.data["refresh"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    logout = api_client.post("/api/auth/logout", {"refresh": refresh}, format="json")
    assert logout.status_code == status.HTTP_204_NO_CONTENT

    reused = api_client.post("/api/auth/refresh", {"refresh": refresh}, format="json")
    assert reused.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_change_password(api_client, user):
    login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    bad = api_client.post(
        "/api/auth/change-password",
        {"current_password": "wrong", "new_password": "NewSecretPass123!"},
        format="json",
    )
    assert bad.status_code == status.HTTP_400_BAD_REQUEST

    ok = api_client.post(
        "/api/auth/change-password",
        {"current_password": PASSWORD, "new_password": "NewSecretPass123!"},
        format="json",
    )
    assert ok.status_code == status.HTTP_200_OK

    old_login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert old_login.status_code == status.HTTP_401_UNAUTHORIZED

    new_login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": "NewSecretPass123!"},
        format="json",
    )
    assert new_login.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_auth_url_names_resolve():
    assert reverse("auth-login") == "/api/auth/login"
    assert reverse("auth-refresh") == "/api/auth/refresh"
    assert reverse("auth-logout") == "/api/auth/logout"
    assert reverse("auth-me") == "/api/auth/me"
    assert reverse("auth-change-password") == "/api/auth/change-password"
