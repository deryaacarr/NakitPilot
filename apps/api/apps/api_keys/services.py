"""API key create / verify / revoke services (NP-200)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.api_keys.models import ApiKey
from apps.api_keys.scopes import generate_api_key, hash_api_key, normalize_scopes, parse_lookup_prefix
from apps.organizations.models import Organization


class ApiKeyError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@transaction.atomic
def create_api_key(
    *,
    organization: Organization,
    name: str,
    scopes: list[str],
    created_by=None,
) -> tuple[ApiKey, str]:
    name = (name or "").strip()
    if not name:
        raise ApiKeyError("Anahtar adı gerekli.")
    if len(name) > 128:
        raise ApiKeyError("Anahtar adı en fazla 128 karakter olabilir.")
    try:
        normalized = normalize_scopes(scopes)
    except ValueError as exc:
        raise ApiKeyError(str(exc)) from exc
    if not normalized:
        raise ApiKeyError("En az bir yetki alanı seçilmeli.")

    full_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey.objects.create(
        organization=organization,
        name=name,
        prefix=prefix,
        key_hash=key_hash,
        scopes=normalized,
        created_by=created_by,
    )
    return api_key, full_key


def authenticate_api_key(raw_key: str) -> ApiKey | None:
    """Verify a presented raw key; returns active ApiKey or None."""
    lookup = parse_lookup_prefix(raw_key)
    if lookup is None:
        return None
    digest = hash_api_key(raw_key.strip())
    api_key = (
        ApiKey.objects.select_related("organization", "created_by")
        .filter(prefix=lookup, key_hash=digest, revoked_at__isnull=True)
        .first()
    )
    return api_key


def mark_api_key_used(api_key: ApiKey, *, min_interval_seconds: int = 60) -> None:
    """Update last_used_at, throttled to avoid write amplification."""
    now = timezone.now()
    if api_key.last_used_at and (now - api_key.last_used_at).total_seconds() < min_interval_seconds:
        return
    ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=now, updated_at=now)
    api_key.last_used_at = now


def revoke_api_key(api_key: ApiKey) -> ApiKey:
    if api_key.revoked_at is not None:
        raise ApiKeyError("Anahtar zaten iptal edilmiş.", status_code=400)
    api_key.revoke()
    return api_key
