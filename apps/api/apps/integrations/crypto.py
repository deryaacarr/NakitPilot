"""Fernet helpers for integration credential encryption (NP-190)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CredentialCryptoError(Exception):
    """Raised when credentials cannot be encrypted or decrypted."""


def _resolve_fernet_key() -> bytes:
    raw = (os.getenv("INTEGRATIONS_FERNET_KEY") or getattr(settings, "INTEGRATIONS_FERNET_KEY", "") or "").strip()
    if raw:
        key = raw.encode("utf-8") if isinstance(raw, str) else raw
        # Accept raw Fernet key or derive from arbitrary secret string.
        try:
            Fernet(key)
            return key
        except (ValueError, TypeError):
            digest = hashlib.sha256(key).digest()
            return base64.urlsafe_b64encode(digest)

    secret = getattr(settings, "SECRET_KEY", "") or ""
    if not secret:
        raise CredentialCryptoError("SECRET_KEY is required to derive INTEGRATIONS_FERNET_KEY.")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    return Fernet(_resolve_fernet_key())


def encrypt_credentials(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise CredentialCryptoError("Credentials payload must be a dict.")
    token = get_fernet().encrypt(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return token.decode("utf-8")


def decrypt_credentials(ciphertext: str) -> dict[str, Any]:
    if not ciphertext:
        raise CredentialCryptoError("Empty credential ciphertext.")
    try:
        raw = get_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise CredentialCryptoError("Invalid credential ciphertext.") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise CredentialCryptoError("Decrypted credentials must be a dict.")
    return data


def credential_key_hint(payload: dict[str, Any]) -> str:
    """Non-secret hint for UI (last 4 chars of a primary key field)."""
    for field in ("api_key", "access_token", "client_id", "username"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            cleaned = value.strip()
            return cleaned[-4:] if len(cleaned) >= 4 else cleaned
    return ""
