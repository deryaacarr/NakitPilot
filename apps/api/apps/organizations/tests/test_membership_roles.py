import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization, Role
from apps.organizations.roles import Permission, role_has_permission

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def api_client():
    return APIClient()


def _login(client, user):
    response = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="owner@example.com", password=PASSWORD)


@pytest.fixture
def org_with_owner(owner):
    org = Organization.objects.create(name="Pilot Co", slug="pilot-co")
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.OWNER, Permission.MANAGE_USERS, True),
        (Role.ADMIN, Permission.MANAGE_USERS, True),
        (Role.FINANCE_MANAGER, Permission.MANAGE_USERS, False),
        (Role.COLLECTION_AGENT, Permission.MANAGE_USERS, False),
        (Role.VIEWER, Permission.MANAGE_USERS, False),
        (Role.OWNER, Permission.ADD_CUSTOMER, True),
        (Role.ADMIN, Permission.ADD_CUSTOMER, True),
        (Role.FINANCE_MANAGER, Permission.ADD_CUSTOMER, True),
        (Role.COLLECTION_AGENT, Permission.ADD_CUSTOMER, False),
        (Role.VIEWER, Permission.ADD_CUSTOMER, False),
        (Role.OWNER, Permission.ADD_INVOICE, True),
        (Role.ADMIN, Permission.ADD_INVOICE, True),
        (Role.FINANCE_MANAGER, Permission.ADD_INVOICE, True),
        (Role.COLLECTION_AGENT, Permission.ADD_INVOICE, False),
        (Role.VIEWER, Permission.ADD_INVOICE, False),
        (Role.OWNER, Permission.MANAGE_COLLECTION_TASK, True),
        (Role.ADMIN, Permission.MANAGE_COLLECTION_TASK, True),
        (Role.FINANCE_MANAGER, Permission.MANAGE_COLLECTION_TASK, True),
        (Role.COLLECTION_AGENT, Permission.MANAGE_COLLECTION_TASK, True),
        (Role.VIEWER, Permission.MANAGE_COLLECTION_TASK, False),
        (Role.OWNER, Permission.ADD_PAYMENT, True),
        (Role.ADMIN, Permission.ADD_PAYMENT, True),
        (Role.FINANCE_MANAGER, Permission.ADD_PAYMENT, True),
        (Role.COLLECTION_AGENT, Permission.ADD_PAYMENT, False),
        (Role.VIEWER, Permission.ADD_PAYMENT, False),
        (Role.OWNER, Permission.VIEW_REPORTS, True),
        (Role.ADMIN, Permission.VIEW_REPORTS, True),
        (Role.FINANCE_MANAGER, Permission.VIEW_REPORTS, True),
        (Role.COLLECTION_AGENT, Permission.VIEW_REPORTS, True),
        (Role.VIEWER, Permission.VIEW_REPORTS, True),
        (Role.OWNER, Permission.MANAGE_SETTINGS, True),
        (Role.ADMIN, Permission.MANAGE_SETTINGS, True),
        (Role.FINANCE_MANAGER, Permission.MANAGE_SETTINGS, False),
        (Role.COLLECTION_AGENT, Permission.MANAGE_SETTINGS, False),
        (Role.VIEWER, Permission.MANAGE_SETTINGS, False),
    ],
)
def test_role_permission_matrix(role, permission, allowed):
    assert role_has_permission(role, permission) is allowed


@pytest.mark.django_db
def test_create_organization_assigns_owner_membership(api_client, owner):
    client = _login(api_client, owner)
    response = client.post(
        "/api/organizations/",
        {"name": "Yeni Firma"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    org_id = response.data["id"]
    membership = Membership.objects.get(organization_id=org_id, user=owner)
    assert membership.role == Role.OWNER
    assert membership.is_active is True


@pytest.mark.django_db
def test_viewer_cannot_manage_users(api_client, org_with_owner):
    viewer = User.objects.create_user(email="viewer@example.com", password=PASSWORD)
    Membership.objects.create(
        organization=org_with_owner,
        user=viewer,
        role=Role.VIEWER,
        is_active=True,
    )
    client = _login(api_client, viewer)
    response = client.post(
        f"/api/organizations/{org_with_owner.id}/memberships/",
        {"user_id": viewer.id, "role": Role.VIEWER},
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org_with_owner.id),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_can_add_membership(api_client, org_with_owner, owner):
    admin_user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
    agent = User.objects.create_user(email="agent@example.com", password=PASSWORD)
    Membership.objects.create(
        organization=org_with_owner,
        user=admin_user,
        role=Role.ADMIN,
        is_active=True,
    )
    client = _login(api_client, admin_user)
    response = client.post(
        f"/api/organizations/{org_with_owner.id}/memberships/",
        {"user_id": agent.id, "role": Role.COLLECTION_AGENT},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["role"] == Role.COLLECTION_AGENT
    assert Membership.objects.filter(
        organization=org_with_owner, user=agent, role=Role.COLLECTION_AGENT
    ).exists()


@pytest.mark.django_db
def test_finance_cannot_change_settings(api_client, org_with_owner):
    finance = User.objects.create_user(email="finance@example.com", password=PASSWORD)
    Membership.objects.create(
        organization=org_with_owner,
        user=finance,
        role=Role.FINANCE_MANAGER,
        is_active=True,
    )
    client = _login(api_client, finance)
    response = client.patch(
        f"/api/organizations/{org_with_owner.id}/",
        {"name": "Hack"},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_inactive_membership_denied(api_client, org_with_owner):
    user = User.objects.create_user(email="inactive-member@example.com", password=PASSWORD)
    Membership.objects.create(
        organization=org_with_owner,
        user=user,
        role=Role.ADMIN,
        is_active=False,
    )
    client = _login(api_client, user)
    response = client.patch(
        f"/api/organizations/{org_with_owner.id}/",
        {"name": "No Access"},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_my_memberships(api_client, org_with_owner, owner):
    client = _login(api_client, owner)
    response = client.get("/api/memberships/me/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["role"] == Role.OWNER
    assert response.data[0]["organization"] == org_with_owner.id
