"""NP-304 — SSO provider configuration (Enterprise)."""

from __future__ import annotations

from typing import Any

from apps.billing.subscription_service import Feature, can_use
from apps.governance.models import SSOProtocol, SSOProviderConfig


class SSOError(Exception):
    def __init__(self, message: str, code: str = "sso_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def assert_sso_entitled(organization) -> None:
    result = can_use(organization, Feature.SSO)
    if not result.allowed:
        raise SSOError(
            "SSO yalnızca Enterprise paketinde kullanılabilir.",
            code="entitlement_denied",
        )


def list_providers(organization) -> list[dict[str, Any]]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    return [
        {
            "id": p.id,
            "protocol": p.protocol,
            "name": p.name,
            "is_enabled": p.is_enabled,
            "issuer_url": p.issuer_url,
            "client_id": p.client_id,
            "metadata_url": p.metadata_url,
            "entity_id": p.entity_id,
            "acs_url": p.acs_url,
            "domains": p.domains,
        }
        for p in SSOProviderConfig.objects.filter(organization_id=org_id)
    ]


def upsert_provider(
    organization,
    *,
    protocol: str,
    name: str,
    is_enabled: bool = False,
    issuer_url: str = "",
    client_id: str = "",
    metadata_url: str = "",
    entity_id: str = "",
    acs_url: str = "",
    domains: list | None = None,
) -> SSOProviderConfig:
    assert_sso_entitled(organization)
    if protocol not in SSOProtocol.values:
        raise SSOError("Desteklenmeyen protokol.", code="invalid_protocol")
    org_id = organization.pk if hasattr(organization, "pk") else organization
    provider, _ = SSOProviderConfig.objects.update_or_create(
        organization_id=org_id,
        protocol=protocol,
        name=name,
        defaults={
            "is_enabled": is_enabled,
            "issuer_url": issuer_url,
            "client_id": client_id,
            "metadata_url": metadata_url,
            "entity_id": entity_id,
            "acs_url": acs_url,
            "domains": domains or [],
        },
    )
    return provider


def sso_login_options(email_domain: str = "") -> list[dict[str, Any]]:
    """Public discovery: enabled providers matching domain (no secrets)."""
    qs = SSOProviderConfig.objects.filter(is_enabled=True)
    results = []
    for p in qs:
        domains = p.domains or []
        if email_domain and domains and email_domain.lower() not in [d.lower() for d in domains]:
            continue
        results.append(
            {
                "organization_id": p.organization_id,
                "protocol": p.protocol,
                "name": p.name,
                "login_hint": f"/api/auth/sso/{p.protocol.lower()}/start?org={p.organization_id}",
            }
        )
    return results
