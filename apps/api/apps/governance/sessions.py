"""NP-305 — session / device management."""

from __future__ import annotations

from typing import Any

from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.governance.models import UserSession


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def register_session(
    user,
    refresh: RefreshToken,
    request,
    *,
    organization=None,
) -> UserSession:
    jti = str(refresh.get("jti", ""))
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    ip = client_ip(request)
    device = _device_label(ua)
    # Suspicious: new IP vs recent sessions
    suspicious = False
    recent = (
        UserSession.objects.filter(user=user, revoked_at__isnull=True)
        .exclude(ip_address=ip)
        .exists()
    )
    if recent and UserSession.objects.filter(user=user).exists():
        # Only flag if user already had sessions from other IPs
        prior_ips = (
            UserSession.objects.filter(user=user, revoked_at__isnull=True)
            .exclude(ip_address__isnull=True)
            .values_list("ip_address", flat=True)
            .distinct()
        )
        if prior_ips and ip and ip not in set(prior_ips):
            suspicious = True

    org_id = None
    if organization is not None:
        org_id = organization.pk if hasattr(organization, "pk") else organization

    session, _ = UserSession.objects.update_or_create(
        refresh_jti=jti,
        defaults={
            "user": user,
            "organization_id": org_id,
            "device_label": device,
            "user_agent": ua,
            "ip_address": ip,
            "last_seen_at": timezone.now(),
            "revoked_at": None,
            "is_suspicious": suspicious,
        },
    )
    return session


def _device_label(ua: str) -> str:
    ua_l = ua.lower()
    if "iphone" in ua_l or "ios" in ua_l:
        return "iPhone"
    if "android" in ua_l:
        return "Android"
    if "macintosh" in ua_l or "mac os" in ua_l:
        return "Mac"
    if "windows" in ua_l:
        return "Windows"
    if "linux" in ua_l:
        return "Linux"
    return "Bilinmeyen cihaz"


def list_sessions(user) -> list[dict[str, Any]]:
    rows = UserSession.objects.filter(user=user, revoked_at__isnull=True)
    return [
        {
            "id": s.id,
            "device_label": s.device_label,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent[:120],
            "last_seen_at": s.last_seen_at.isoformat(),
            "created_at": s.created_at.isoformat(),
            "is_suspicious": s.is_suspicious,
        }
        for s in rows
    ]


def revoke_session(user, session_id: int) -> bool:
    session = UserSession.objects.filter(user=user, pk=session_id, revoked_at__isnull=True).first()
    if session is None:
        return False
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at"])
    try:
        # Best-effort blacklist if outstanding token exists
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )

        outstanding = OutstandingToken.objects.filter(jti=session.refresh_jti).first()
        if outstanding:
            BlacklistedToken.objects.get_or_create(token=outstanding)
    except Exception:  # noqa: BLE001
        pass
    return True


def revoke_all_sessions(user, *, except_jti: str | None = None) -> int:
    qs = UserSession.objects.filter(user=user, revoked_at__isnull=True)
    if except_jti:
        qs = qs.exclude(refresh_jti=except_jti)
    count = 0
    for session in qs:
        if revoke_session(user, session.id):
            count += 1
    return count


def blacklist_refresh_raw(refresh_str: str) -> None:
    try:
        token = RefreshToken(refresh_str)
        token.blacklist()
    except TokenError:
        pass
