"""API key scopes and helpers (NP-200)."""

from __future__ import annotations

import hashlib
import secrets
from typing import Iterable

# Public API scopes — extend carefully; clients may depend on exact strings.
AVAILABLE_SCOPES: tuple[str, ...] = (
    "customers:read",
    "customers:write",
    "invoices:read",
    "invoices:write",
    "payments:read",
    "payments:write",
    "risk:read",
    "forecast:read",
)

AVAILABLE_SCOPE_SET = frozenset(AVAILABLE_SCOPES)

KEY_PREFIX = "npk_"
LOOKUP_PREFIX_LEN = 8


def normalize_scopes(scopes: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in scopes:
        scope = str(raw).strip()
        if not scope or scope in seen:
            continue
        if scope not in AVAILABLE_SCOPE_SET:
            raise ValueError(f"Geçersiz yetki alanı: {scope}")
        seen.add(scope)
        cleaned.append(scope)
    return cleaned


def generate_api_key() -> tuple[str, str, str]:
    """
    Returns (full_key, lookup_prefix, key_hash).

    Full key format: npk_<8hex>_<token>
    Only the hash is stored; full key is shown once at creation.
    """
    lookup = secrets.token_hex(LOOKUP_PREFIX_LEN // 2)
    secret = secrets.token_urlsafe(32)
    full_key = f"{KEY_PREFIX}{lookup}_{secret}"
    return full_key, lookup, hash_api_key(full_key)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def parse_lookup_prefix(raw_key: str) -> str | None:
    key = (raw_key or "").strip()
    if not key.startswith(KEY_PREFIX):
        return None
    rest = key[len(KEY_PREFIX) :]
    if "_" not in rest:
        return None
    lookup, _secret = rest.split("_", 1)
    if len(lookup) != LOOKUP_PREFIX_LEN:
        return None
    return lookup
