from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from apps.organizations.models import Invitation, InvitationStatus, Membership

User = get_user_model()


def build_invite_link(token: str) -> str:
    base = getattr(settings, "INVITE_BASE_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/invitations/{token}"


def create_invitation(
    *,
    organization,
    email: str,
    role: str,
    invited_by,
) -> Invitation:
    email = User.objects.normalize_email(email)
    if Membership.objects.filter(
        organization=organization,
        user__email__iexact=email,
        is_active=True,
    ).exists():
        raise ValueError("User is already an active member of this organization.")

    pending = Invitation.objects.filter(
        organization=organization,
        email__iexact=email,
        status=InvitationStatus.PENDING,
        expires_at__gt=timezone.now(),
    ).first()
    if pending:
        return pending

    expiry_days = getattr(settings, "INVITE_EXPIRY_DAYS", 7)
    return Invitation.objects.create(
        organization=organization,
        email=email,
        role=role,
        token=secrets.token_urlsafe(32),
        invited_by=invited_by,
        status=InvitationStatus.PENDING,
        expires_at=timezone.now() + timedelta(days=expiry_days),
    )


@transaction.atomic
def accept_invitation(
    invitation: Invitation,
    *,
    password: str,
    first_name: str = "",
    last_name: str = "",
) -> tuple:
    """
    Accept invite: create user if needed, ensure membership, mark invitation accepted.

    Returns (user, membership, created_user).
    """
    invitation.mark_expired_if_needed()
    if not invitation.is_acceptable:
        raise ValueError("Invitation is not acceptable.")

    validate_password(password)

    email = User.objects.normalize_email(invitation.email)
    user = User.objects.filter(email__iexact=email).first()
    created_user = False
    if user is None:
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        created_user = True
    else:
        if not user.check_password(password):
            raise ValueError("Invalid password for existing account.")
        if not user.is_active:
            raise ValueError("User account is inactive.")
        updates = []
        if first_name and not user.first_name:
            user.first_name = first_name
            updates.append("first_name")
        if last_name and not user.last_name:
            user.last_name = last_name
            updates.append("last_name")
        if updates:
            user.save(update_fields=updates)

    membership, _created = Membership.objects.get_or_create(
        organization=invitation.organization,
        user=user,
        defaults={"role": invitation.role, "is_active": True},
    )
    if not membership.is_active:
        membership.is_active = True
        membership.role = invitation.role
        membership.save(update_fields=["is_active", "role"])
    elif _created is False and membership.role != invitation.role:
        # Keep existing role if already a member; invitation still closes.
        pass

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at"])

    return user, membership, created_user
