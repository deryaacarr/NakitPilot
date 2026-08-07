"""NP-191 — AccountingConnector interface is provider-agnostic and model-safe."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from apps.customers.models import Customer
from apps.integrations.connectors.base import AccountingConnector
from apps.integrations.connectors.kolaybi import KolayBiConnector
from apps.integrations.connectors.registry import (
    build,
    get,
    known_providers,
    list_providers,
    register,
)
from apps.integrations.connectors.types import (
    FetchPage,
    NormalizedCompany,
    NormalizedCustomer,
    NormalizedInvoice,
    NormalizedPayment,
)
from apps.organizations.models import Organization


@register
class FakeLogoConnector(AccountingConnector):
    """Stand-in for a future Logo connector — proves registry extensibility."""

    provider = "logo"
    display_name = "Logo"

    @classmethod
    def validate_credentials(cls, payload: dict[str, Any]) -> None:
        super().validate_credentials(payload)
        if not (payload.get("client_id") and payload.get("client_secret")):
            raise ValueError("client_id and client_secret are required for Logo.")

    def test_connection(self) -> dict[str, Any]:
        return {"ok": True, "provider": self.provider}

    def fetch_companies(self) -> FetchPage[NormalizedCompany]:
        return FetchPage(
            items=[NormalizedCompany(external_id="logo-co-1", name="Logo Demo A.Ş.")]
        )

    def fetch_customers(self, cursor: str | None = None, *, updated_since=None) -> FetchPage[NormalizedCustomer]:
        return FetchPage(items=[])

    def fetch_invoices(self, cursor: str | None = None, *, updated_since=None) -> FetchPage[NormalizedInvoice]:
        return FetchPage(items=[])

    def fetch_payments(self, cursor: str | None = None, *, updated_since=None) -> FetchPage[NormalizedPayment]:
        return FetchPage(items=[])

    def normalize_customer(self, raw_data: dict[str, Any]) -> NormalizedCustomer:
        return NormalizedCustomer(
            external_id=str(raw_data["CODE"]),
            name=str(raw_data["DEFINITION"]),
        )

    def normalize_invoice(self, raw_data: dict[str, Any]) -> NormalizedInvoice:
        raise NotImplementedError

    def normalize_payment(self, raw_data: dict[str, Any]) -> NormalizedPayment:
        raise NotImplementedError


REQUIRED_METHODS = (
    "test_connection",
    "fetch_companies",
    "fetch_customers",
    "fetch_invoices",
    "fetch_payments",
    "normalize_customer",
    "normalize_invoice",
    "normalize_payment",
)


def test_accounting_connector_declares_required_abstract_methods():
    for name in REQUIRED_METHODS:
        assert name in AccountingConnector.__abstractmethods__


def test_kolaybi_is_independent_subclass():
    assert issubclass(KolayBiConnector, AccountingConnector)
    assert KolayBiConnector.provider == "kolaybi"
    # Interface module must not import KolayBi (checked via base.py contents elsewhere);
    # subclassing alone proves KolayBi plugs into the shared ABC.


def test_registry_accepts_additional_providers_like_logo():
    assert "kolaybi" in known_providers()
    assert "logo" in known_providers()
    providers = {p["provider"] for p in list_providers()}
    assert providers >= {"kolaybi", "logo"}
    assert get("logo") is FakeLogoConnector


def test_build_returns_bound_instance_without_django_models():
    connector = build("logo", credentials={"client_id": "a", "client_secret": "b"})
    assert isinstance(connector, AccountingConnector)
    assert connector.test_connection()["ok"] is True
    page = connector.fetch_companies()
    assert isinstance(page, FetchPage)
    assert page.items[0].name == "Logo Demo A.Ş."
    customer = connector.normalize_customer({"CODE": "C1", "DEFINITION": "Acme"})
    assert isinstance(customer, NormalizedCustomer)
    assert customer.external_id == "C1"


def test_kolaybi_normalize_returns_dto_not_model():
    connector = KolayBiConnector(credentials={"api_key": "kb-test-key-xxxx", "channel_id": "ch-1"})
    customer = connector.normalize_customer(
        {"id": "99", "name": "Demo Cari", "tax_number": "1234567890", "email": "A@B.com"}
    )
    invoice = connector.normalize_invoice(
        {
            "id": "inv-1",
            "customer_id": "99",
            "number": "F-2026-1",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-15",
            "total_amount": "1500.50",
            "currency": "try",
        }
    )
    payment = connector.normalize_payment(
        {
            "id": "pay-1",
            "customer_id": "99",
            "payment_date": "2026-02-01",
            "amount": "500",
            "invoice_ids": ["inv-1"],
        }
    )
    assert isinstance(customer, NormalizedCustomer)
    assert customer.email == "a@b.com"
    assert isinstance(invoice, NormalizedInvoice)
    assert invoice.total_amount == Decimal("1500.50")
    assert invoice.currency == "TRY"
    assert isinstance(payment, NormalizedPayment)
    assert payment.external_invoice_ids == ("inv-1",)
    assert not isinstance(customer, Customer)


@pytest.mark.django_db
def test_connector_does_not_create_domain_models(db):
    org = Organization.objects.create(name="Integ Org", slug="integ-np191")
    before = Customer.objects.filter(organization=org).count()

    connector = KolayBiConnector(credentials={"api_key": "kb-test-key-xxxx", "channel_id": "ch-1"})
    normalized = connector.normalize_customer({"id": "ext-1", "name": "Should Not Persist"})
    # Caller / service would persist; connector must not.
    assert isinstance(normalized, NormalizedCustomer)
    assert Customer.objects.filter(organization=org).count() == before
    assert not Customer.objects.filter(name="Should Not Persist").exists()


def test_incomplete_kolaybi_credentials_rejected():
    with pytest.raises(ValueError, match="api_key"):
        KolayBiConnector(credentials={"token": "nope"})
    with pytest.raises(ValueError, match="channel_id"):
        KolayBiConnector(credentials={"api_key": "only-key"})
