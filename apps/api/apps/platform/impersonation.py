"""NP-361 — impersonation start/end + sensitive op guards."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import write_audit_log
from apps.organizations.models import Membership
from apps.platform.audit import write_platform_audit
from apps.platform.models import ImpersonationSession

User = get_user_model()

MAX_DURATION_MINUTES = 60
DEFAULT_DURATION_MINUTES = 30

# Path prefixes blocked for mutating methods while impersonating
SENSITIVE_WRITE_PREFIXES = (
    "/api/payments/",
    "/api/billing/",
    "/api/invoices/",
    "/api/collection-tasks/",  # complete can create promises — still allow GET
    "/api/payment-promises/",
    "/api/legal/cases/",
    "/api/payables/",
    "/api/imports/",
)

# Even more strict: block these paths entirely for writes
SENSITIVE_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ImpersonationError(Exception):
    def __init__(self, message: str, code: str = "impersonation_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def start_impersonation(
    *,
    staff_user,
    target_user_id: int,
    organization_id: int,
    reason: str,
    duration_minutes: int = DEFAULT_DURATION_MINUTES,
    notify_target: bool = True,
) -> tuple[ImpersonationSession, dict[str, Any]]:
    if not staff_user or not (staff_user.is_staff or staff_user.is_superuser):
        raise ImpersonationError("Yetkisiz.", code="forbidden")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ImpersonationError("Gerekçe zorunlu (en az 5 karakter).", code="reason_required")

    duration_minutes = max(5, min(int(duration_minutes or DEFAULT_DURATION_MINUTES), MAX_DURATION_MINUTES))

    try:
        target = User.objects.get(pk=target_user_id, is_active=True)
    except User.DoesNotExist as exc:
        raise ImpersonationError("Hedef kullanıcı bulunamadı.", code="user_not_found") from exc

    if target.pk == staff_user.pk:
        raise ImpersonationError("Kendi hesabınıza geçiş yapılamaz.", code="self_impersonation")

    membership = Membership.objects.filter(
        organization_id=organization_id,
        user=target,
        is_active=True,
    ).select_related("organization").first()
    if membership is None:
        raise ImpersonationError(
            "Hedef kullanıcının bu organizasyonda aktif üyeliği yok.",
            code="no_membership",
        )

    # End any previous active sessions for this staff
    ImpersonationSession.objects.filter(
        staff_user=staff_user, is_active=True, ended_at__isnull=True
    ).update(is_active=False, ended_at=timezone.now(), end_reason="replaced")

    expires_at = timezone.now() + timedelta(minutes=duration_minutes)
    session = ImpersonationSession.objects.create(
        staff_user=staff_user,
        target_user=target,
        organization=membership.organization,
        reason=reason,
        expires_at=expires_at,
        notify_target=notify_target,
        is_active=True,
    )

    refresh = RefreshToken.for_user(target)
    refresh["impersonation_id"] = str(session.id)
    refresh["impersonator_id"] = staff_user.pk
    refresh["impersonation"] = True
    access = refresh.access_token
    access["impersonation_id"] = str(session.id)
    access["impersonator_id"] = staff_user.pk
    access["impersonation"] = True

    write_platform_audit(
        actor=staff_user,
        action="impersonation.start",
        entity_type="ImpersonationSession",
        entity_id=session.id,
        organization=membership.organization,
        summary=f"{staff_user.email} → {target.email}",
        changes={
            "reason": reason,
            "duration_minutes": duration_minutes,
            "notify_target": notify_target,
            "expires_at": expires_at.isoformat(),
        },
    )
    write_audit_log(
        organization=membership.organization,
        actor=staff_user,
        action="impersonation.start",
        entity_type="User",
        entity_id=target.pk,
        summary=f"Destek impersonation başladı: {reason[:120]}",
        changes={
            "session_id": str(session.id),
            "impersonator_id": staff_user.pk,
            "expires_at": expires_at.isoformat(),
        },
    )

    if notify_target:
        try:
            from apps.notifications.models import (
                AlertSeverity,
                create_dashboard_alert,
            )

            create_dashboard_alert(
                organization=membership.organization,
                title="Destek erişimi aktif",
                body=(
                    f"NakitPilot destek personeli hesabınıza sınırlı süreyle geçiş yaptı. "
                    f"Gerekçe: {reason[:160]}"
                ),
                severity=AlertSeverity.WARNING,
                notification_type="",
                category="impersonation",
                entity_type="ImpersonationSession",
                entity_id=str(session.id),
                created_for=target,
                href="/dashboard/settings",
            )
        except Exception:
            pass

    tokens = {
        "access": str(access),
        "refresh": str(refresh),
        "session_id": str(session.id),
        "expires_at": expires_at.isoformat(),
        "duration_minutes": duration_minutes,
        "organization_id": membership.organization_id,
        "target_user": {
            "id": target.pk,
            "email": target.email,
            "name": f"{target.first_name} {target.last_name}".strip() or target.email,
        },
        "staff_user": {"id": staff_user.pk, "email": staff_user.email},
        "reason": reason,
        "banner": (
            f"Destek modu: {staff_user.email} olarak {target.email} hesabındasınız. "
            f"Süre: {duration_minutes} dk. Hassas finansal işlemler engellenir."
        ),
        "sensitive_writes_blocked": True,
    }
    return session, tokens


def end_impersonation(
    *,
    session: ImpersonationSession,
    ended_by=None,
    end_reason: str = "manual",
) -> ImpersonationSession:
    if not session.is_active or session.ended_at is not None:
        return session
    session.is_active = False
    session.ended_at = timezone.now()
    session.end_reason = end_reason
    session.save(update_fields=["is_active", "ended_at", "end_reason"])
    actor = ended_by or session.staff_user
    write_platform_audit(
        actor=actor,
        action="impersonation.end",
        entity_type="ImpersonationSession",
        entity_id=session.id,
        organization=session.organization,
        summary=f"Impersonation sonlandı ({end_reason})",
        changes={"end_reason": end_reason},
    )
    write_audit_log(
        organization=session.organization,
        actor=actor,
        action="impersonation.end",
        entity_type="User",
        entity_id=session.target_user_id,
        summary=f"Destek impersonation sonlandı ({end_reason})",
        changes={"session_id": str(session.id)},
    )
    return session


def get_active_session_from_token(auth) -> ImpersonationSession | None:
    if auth is None:
        return None
    payload = getattr(auth, "payload", None) or {}
    if not payload.get("impersonation"):
        return None
    session_id = payload.get("impersonation_id")
    if not session_id:
        return None
    session = (
        ImpersonationSession.objects.select_related(
            "staff_user", "target_user", "organization"
        )
        .filter(pk=session_id)
        .first()
    )
    if session is None or not session.is_valid():
        if session and session.is_active:
            end_impersonation(session=session, end_reason="expired")
        return None
    return session


def is_sensitive_write(path: str, method: str) -> bool:
    if method.upper() not in SENSITIVE_MUTATION_METHODS:
        return False
    # Allow ending impersonation / reading platform self status
    if path.startswith("/api/platform/impersonation/"):
        return False
    return any(path.startswith(prefix) for prefix in SENSITIVE_WRITE_PREFIXES)
