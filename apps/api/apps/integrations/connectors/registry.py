"""Registry of AccountingConnector classes (provider → implementation)."""

from __future__ import annotations

from typing import Any, Mapping, Type

from apps.integrations.connectors.base import AccountingConnector

_REGISTRY: dict[str, Type[AccountingConnector]] = {}


def register(connector_cls: Type[AccountingConnector]) -> Type[AccountingConnector]:
    if not connector_cls.provider:
        raise ValueError("AccountingConnector.provider is required.")
    if not issubclass(connector_cls, AccountingConnector):
        raise TypeError(f"{connector_cls!r} must subclass AccountingConnector")
    _REGISTRY[connector_cls.provider] = connector_cls
    return connector_cls


def get(provider: str) -> Type[AccountingConnector]:
    try:
        return _REGISTRY[provider]
    except KeyError as exc:
        raise KeyError(f"Unknown integration provider: {provider}") from exc


def build(
    provider: str,
    *,
    credentials: dict[str, Any],
    settings: Mapping[str, Any] | None = None,
) -> AccountingConnector:
    """Instantiate a bound connector for a connection session."""
    return get(provider)(credentials=credentials, settings=settings)


def list_providers() -> list[dict[str, str]]:
    return [
        {
            "provider": cls.provider,
            "display_name": cls.display_name or cls.provider,
        }
        for cls in sorted(_REGISTRY.values(), key=lambda c: c.provider)
    ]


def known_providers() -> frozenset[str]:
    return frozenset(_REGISTRY.keys())


def clear_registry() -> None:
    """Test helper — wipe registrations."""
    _REGISTRY.clear()
