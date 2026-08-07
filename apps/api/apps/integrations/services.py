"""Credential storage helpers — plaintext never leaves the service layer to API."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.integrations.crypto import (
    credential_key_hint,
    decrypt_credentials,
    encrypt_credentials,
)
from apps.integrations.models import IntegrationConnection, IntegrationCredential


@transaction.atomic
def set_connection_credentials(
    connection: IntegrationConnection,
    payload: dict[str, Any],
) -> IntegrationCredential:
    ciphertext = encrypt_credentials(payload)
    hint = credential_key_hint(payload)
    now = timezone.now()
    credential, _created = IntegrationCredential.objects.update_or_create(
        connection=connection,
        defaults={
            "organization": connection.organization,
            "encrypted_payload": ciphertext,
            "key_hint": hint,
            "rotated_at": now,
        },
    )
    return credential


def get_connection_credentials(connection: IntegrationConnection) -> dict[str, Any]:
    credential = getattr(connection, "credential", None)
    if credential is None:
        try:
            credential = connection.credential
        except IntegrationCredential.DoesNotExist as exc:
            raise IntegrationCredential.DoesNotExist(
                "No credentials stored for this connection."
            ) from exc
    return decrypt_credentials(credential.encrypted_payload)


def connection_has_credentials(connection: IntegrationConnection) -> bool:
    return IntegrationCredential.objects.filter(connection_id=connection.pk).exists()
