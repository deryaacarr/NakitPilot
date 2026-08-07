"""KolayBi AccountingConnector (NP-191/192)."""

from __future__ import annotations

from typing import Any

from apps.integrations.connectors.base import AccountingConnector
from apps.integrations.connectors.kolaybi_client import KolayBiClient, KolayBiClientError
from apps.integrations.connectors.registry import register
from apps.integrations.connectors.types import (
    FetchPage,
    NormalizedCompany,
    NormalizedCustomer,
    NormalizedInvoice,
    NormalizedPayment,
)


@register
class KolayBiConnector(AccountingConnector):
    provider = "kolaybi"
    display_name = "KolayBi"

    @classmethod
    def validate_credentials(cls, payload: dict[str, Any]) -> None:
        super().validate_credentials(payload)
        api_key = (payload.get("api_key") or "").strip()
        channel = (payload.get("channel_id") or payload.get("channel") or "").strip()
        if not api_key:
            raise ValueError("api_key is required for KolayBi.")
        if not channel:
            raise ValueError("channel_id is required for KolayBi.")

    def _client(self) -> KolayBiClient:
        return KolayBiClient(self.credentials)

    def test_connection(self) -> dict[str, Any]:
        try:
            result = self._client().test_connection()
        except KolayBiClientError as exc:
            return {"ok": False, "provider": self.provider, "message": str(exc)}
        return {"ok": True, "provider": self.provider, **result}

    def fetch_companies(self) -> FetchPage[NormalizedCompany]:
        try:
            companies = self._client().list_companies()
        except KolayBiClientError as exc:
            raise RuntimeError(str(exc)) from exc
        items = [
            NormalizedCompany(
                external_id=c.id,
                name=c.name,
                tax_number=c.tax_number,
            )
            for c in companies
        ]
        return FetchPage(items=items)

    def fetch_customers(
        self,
        cursor: str | None = None,
        *,
        updated_since=None,
    ) -> FetchPage[NormalizedCustomer]:
        company_id = str(self.settings.get("external_company_id") or "").strip()
        try:
            page = self._client().list_customers(
                cursor=cursor,
                company_id=company_id or None,
                updated_since=updated_since,
            )
        except KolayBiClientError as exc:
            raise RuntimeError(str(exc)) from exc
        items = [self.normalize_customer(raw) for raw in page.items]
        return FetchPage(items=items, next_cursor=page.next_cursor)

    def fetch_invoices(
        self,
        cursor: str | None = None,
        *,
        updated_since=None,
    ) -> FetchPage[NormalizedInvoice]:
        company_id = str(self.settings.get("external_company_id") or "").strip()
        try:
            page = self._client().list_invoices(
                cursor=cursor,
                company_id=company_id or None,
                updated_since=updated_since,
            )
        except KolayBiClientError as exc:
            raise RuntimeError(str(exc)) from exc
        items = [self.normalize_invoice(raw) for raw in page.items]
        return FetchPage(items=items, next_cursor=page.next_cursor)

    def fetch_payments(
        self,
        cursor: str | None = None,
        *,
        updated_since=None,
    ) -> FetchPage[NormalizedPayment]:
        company_id = str(self.settings.get("external_company_id") or "").strip()
        try:
            page = self._client().list_payments(
                cursor=cursor,
                company_id=company_id or None,
                updated_since=updated_since,
            )
        except KolayBiClientError as exc:
            raise RuntimeError(str(exc)) from exc
        items = [self.normalize_payment(raw) for raw in page.items]
        return FetchPage(items=items, next_cursor=page.next_cursor)

    def normalize_customer(self, raw_data: dict[str, Any]) -> NormalizedCustomer:
        from apps.integrations.conversion import parse_optional_money

        external_id = str(raw_data.get("id") or raw_data.get("external_id") or "").strip()
        name = str(raw_data.get("name") or raw_data.get("title") or "").strip()
        if not external_id or not name:
            raise ValueError("KolayBi customer requires id and name.")
        credit = raw_data.get("credit_limit")
        return NormalizedCustomer(
            external_id=external_id,
            name=name,
            code=str(raw_data.get("code") or "").strip(),
            tax_number=str(raw_data.get("tax_number") or raw_data.get("vkn") or "").strip(),
            email=str(raw_data.get("email") or "").strip().lower(),
            phone=str(raw_data.get("phone") or "").strip(),
            city=str(raw_data.get("city") or "").strip(),
            sector=str(raw_data.get("sector") or "").strip(),
            payment_term_days=_optional_int(raw_data.get("payment_term_days")),
            credit_limit=parse_optional_money(credit) if credit not in (None, "") else None,
            is_active=bool(raw_data.get("is_active", True)),
            notes="",
            metadata={"updated_at": raw_data.get("updated_at")},
        )

    def normalize_invoice(self, raw_data: dict[str, Any]) -> NormalizedInvoice:
        from apps.integrations.conversion import parse_date, parse_money, parse_optional_money

        external_id = str(raw_data.get("id") or raw_data.get("external_id") or "").strip()
        customer_id = str(
            raw_data.get("customer_id") or raw_data.get("external_customer_id") or ""
        ).strip()
        number = str(raw_data.get("number") or raw_data.get("invoice_number") or "").strip()
        if not external_id or not customer_id or not number:
            raise ValueError("KolayBi invoice requires id, customer_id, and number.")
        status = str(raw_data.get("status") or "").strip()
        is_cancelled = bool(raw_data.get("is_cancelled")) or status.lower() in {
            "cancelled",
            "canceled",
            "deleted",
            "void",
        }
        return NormalizedInvoice(
            external_id=external_id,
            external_customer_id=customer_id,
            number=number,
            invoice_date=parse_date(
                raw_data.get("invoice_date") or raw_data.get("date"),
                field_name="invoice_date",
            ),
            due_date=parse_date(raw_data.get("due_date"), field_name="due_date"),
            currency=str(raw_data.get("currency") or "TRY").upper()[:3],
            total_amount=parse_money(
                raw_data.get("total_amount") or raw_data.get("total"),
                field_name="total_amount",
            ),
            subtotal_amount=parse_optional_money(raw_data.get("subtotal_amount")),
            tax_amount=parse_optional_money(raw_data.get("tax_amount")),
            status=status,
            description=str(raw_data.get("description") or "").strip(),
            notes="",
            metadata={"is_cancelled": is_cancelled, "updated_at": raw_data.get("updated_at")},
        )

    def normalize_payment(self, raw_data: dict[str, Any]) -> NormalizedPayment:
        from apps.integrations.conversion import parse_date, parse_money

        external_id = str(raw_data.get("id") or raw_data.get("external_id") or "").strip()
        customer_id = str(
            raw_data.get("customer_id") or raw_data.get("external_customer_id") or ""
        ).strip()
        if not external_id or not customer_id:
            raise ValueError("KolayBi payment requires id and customer_id.")
        invoice_ids = raw_data.get("invoice_ids") or raw_data.get("external_invoice_ids") or []
        if isinstance(invoice_ids, str):
            invoice_ids = [invoice_ids]
        is_cancelled = bool(raw_data.get("is_cancelled")) or str(
            raw_data.get("status") or ""
        ).lower() in {"cancelled", "canceled", "deleted", "void"}
        return NormalizedPayment(
            external_id=external_id,
            external_customer_id=customer_id,
            payment_date=parse_date(
                raw_data.get("payment_date") or raw_data.get("date"),
                field_name="payment_date",
            ),
            amount=parse_money(raw_data.get("amount"), field_name="amount"),
            currency=str(raw_data.get("currency") or "TRY").upper()[:3],
            method=str(raw_data.get("method") or "").strip(),
            reference=str(raw_data.get("reference") or "").strip(),
            notes="",
            external_invoice_ids=tuple(str(x) for x in invoice_ids),
            metadata={"is_cancelled": is_cancelled, "updated_at": raw_data.get("updated_at")},
        )


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
