from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.organizations.models import Invitation, InvitationStatus, Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"
NEW_PASSWORD = "InvitePass123!"


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
    org = Organization.objects.create(name="Invite Co", slug="invite-co")
    owner = User.objects.create_user(email="owner@invite.example", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.mark.django_db
def test_create_invitation_returns_link(api_client, org_owner):
    org, owner = org_owner
    client = _auth(api_client, owner, org)

    response = client.post(
        "/api/organizations/invitations",
        {"email": "agent@invite.example", "role": Role.COLLECTION_AGENT},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["email"] == "agent@invite.example"
    assert response.data["role"] == Role.COLLECTION_AGENT
    assert response.data["status"] == InvitationStatus.PENDING
    assert "token" in response.data
    assert response.data["invite_link"].endswith(f"/invitations/{response.data['token']}")
    assert Invitation.objects.filter(token=response.data["token"]).exists()


@pytest.mark.django_db
def test_get_invitation_by_token_is_public(api_client, org_owner):
    org, owner = org_owner
    invite = Invitation.objects.create(
        organization=org,
        email="viewer@invite.example",
        role=Role.VIEWER,
        token="public-token-123",
        invited_by=owner,
        expires_at=timezone.now() + timedelta(days=3),
    )

    response = api_client.get(f"/api/organizations/invitations/{invite.token}")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["organization_name"] == "Invite Co"
    assert response.data["email"] == "viewer@invite.example"
    assert "token" not in response.data


@pytest.mark.django_db
def test_accept_invitation_creates_user_and_membership(api_client, org_owner):
    org, owner = org_owner
    client = _auth(api_client, owner, org)
    created = client.post(
        "/api/organizations/invitations",
        {"email": "newbie@invite.example", "role": Role.FINANCE_MANAGER},
        format="json",
    )
    token = created.data["token"]

    accept = api_client.post(
        f"/api/organizations/invitations/{token}/accept",
        {
            "password": NEW_PASSWORD,
            "first_name": "Yeni",
            "last_name": "Üye",
        },
        format="json",
    )
    assert accept.status_code == status.HTTP_200_OK
    assert accept.data["created_user"] is True
    assert accept.data["role"] == Role.FINANCE_MANAGER

    user = User.objects.get(email="newbie@invite.example")
    assert user.check_password(NEW_PASSWORD)
    assert Membership.objects.filter(
        organization=org, user=user, role=Role.FINANCE_MANAGER, is_active=True
    ).exists()
    invite = Invitation.objects.get(token=token)
    assert invite.status == InvitationStatus.ACCEPTED
    assert invite.accepted_at is not None


@pytest.mark.django_db
def test_viewer_cannot_create_invitation(api_client, org_owner):
    org, _owner = org_owner
    viewer = User.objects.create_user(email="viewer@invite.example", password=PASSWORD)
    Membership.objects.create(organization=org, user=viewer, role=Role.VIEWER, is_active=True)
    client = _auth(api_client, viewer, org)
    response = client.post(
        "/api/organizations/invitations",
        {"email": "x@invite.example", "role": Role.VIEWER},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_invitation_url_names():
    assert reverse("invitation-create") == "/api/organizations/invitations"
    assert (
        reverse("invitation-detail", kwargs={"token": "abc"})
        == "/api/organizations/invitations/abc"
    )
    assert (
        reverse("invitation-accept", kwargs={"token": "abc"})
        == "/api/organizations/invitations/abc/accept"
    )
