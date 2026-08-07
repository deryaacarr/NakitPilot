"""Webhook endpoint secret helpers (NP-203)."""

from __future__ import annotations

import secrets

from apps.integrations.crypto import CredentialCryptoError, decrypt_credentials, encrypt_credentials


class WebhookSecretError(Exception):
    pass


def generate_webhook_secret() -> str:
    """Return a signing secret shown once at endpoint creation (`whsec_…`)."""
    return f"whsec_{secrets.token_urlsafe(32)}"


def encrypt_webhook_secret(secret: str) -> str:
    try:
        return encrypt_credentials({"secret": secret})
    except CredentialCryptoError as exc:
        raise WebhookSecretError(str(exc)) from exc


def decrypt_webhook_secret(ciphertext: str) -> str:
    try:
        payload = decrypt_credentials(ciphertext)
    except CredentialCryptoError as exc:
        raise WebhookSecretError(str(exc)) from exc
    secret = payload.get("secret")
    if not isinstance(secret, str) or not secret:
        raise WebhookSecretError("Webhook secret missing from ciphertext.")
    return secret


def secret_hint(secret: str) -> str:
    cleaned = (secret or "").strip()
    if len(cleaned) <= 8:
        return cleaned
    return cleaned[-4:]
