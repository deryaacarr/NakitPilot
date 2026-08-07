"""Provider-agnostic accounting connector interface (NP-191).

Implementations (KolayBi, Logo, Mikro, Paraşüt, …) adapt external APIs into
normalized DTOs. They must not write to Django domain models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Mapping

from apps.integrations.connectors.types import (
    FetchPage,
    NormalizedCompany,
    NormalizedCustomer,
    NormalizedInvoice,
    NormalizedPayment,
)


class AccountingConnector(ABC):
    """Contract for external accounting / ERP providers."""

    provider: ClassVar[str] = ""
    display_name: ClassVar[str] = ""

    def __init__(
        self,
        *,
        credentials: dict[str, Any],
        settings: Mapping[str, Any] | None = None,
    ) -> None:
        self.validate_credentials(credentials)
        self.credentials = credentials
        self.settings = dict(settings or {})

    @classmethod
    def validate_credentials(cls, payload: dict[str, Any]) -> None:
        """Raise ValueError if credentials are incomplete. Override per provider."""
        if not isinstance(payload, dict) or not payload:
            raise ValueError("Credentials payload is required.")

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """Probe the remote API; return a small status dict (no secrets)."""

    @abstractmethod
    def fetch_companies(self) -> FetchPage[NormalizedCompany]:
        """List companies available under the current credentials."""

    @abstractmethod
    def fetch_customers(
        self,
        cursor: str | None = None,
        *,
        updated_since=None,
    ) -> FetchPage[NormalizedCustomer]:
        """Fetch a page of customers, already normalized."""

    @abstractmethod
    def fetch_invoices(
        self,
        cursor: str | None = None,
        *,
        updated_since=None,
    ) -> FetchPage[NormalizedInvoice]:
        """Fetch a page of invoices, already normalized."""

    @abstractmethod
    def fetch_payments(
        self,
        cursor: str | None = None,
        *,
        updated_since=None,
    ) -> FetchPage[NormalizedPayment]:
        """Fetch a page of payments, already normalized."""

    @abstractmethod
    def normalize_customer(self, raw_data: dict[str, Any]) -> NormalizedCustomer:
        """Map a single provider payload to NormalizedCustomer."""

    @abstractmethod
    def normalize_invoice(self, raw_data: dict[str, Any]) -> NormalizedInvoice:
        """Map a single provider payload to NormalizedInvoice."""

    @abstractmethod
    def normalize_payment(self, raw_data: dict[str, Any]) -> NormalizedPayment:
        """Map a single provider payload to NormalizedPayment."""


# Backwards-compatible alias for NP-190 call sites / imports.
BaseConnector = AccountingConnector
