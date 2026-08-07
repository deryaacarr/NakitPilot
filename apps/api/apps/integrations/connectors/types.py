"""Normalized DTOs returned by accounting connectors (NP-191).

Connectors must not mutate Customer / Invoice / Payment models.
Service layers consume these structures and perform persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class NormalizedCompany:
    external_id: str
    name: str
    tax_number: str = ""
    currency: str = "TRY"
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedCustomer:
    external_id: str
    name: str
    code: str = ""
    tax_number: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    sector: str = ""
    payment_term_days: int | None = None
    credit_limit: Decimal | None = None
    is_active: bool = True
    notes: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedInvoice:
    external_id: str
    external_customer_id: str
    number: str
    invoice_date: date
    due_date: date
    currency: str
    total_amount: Decimal
    subtotal_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    status: str = ""
    description: str = ""
    notes: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedPayment:
    external_id: str
    external_customer_id: str
    payment_date: date
    amount: Decimal
    currency: str = "TRY"
    method: str = ""
    reference: str = ""
    notes: str = ""
    external_invoice_ids: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FetchPage(Generic[T]):
    """Cursor-paginated batch of normalized (or raw pre-normalize) items."""

    items: list[T]
    next_cursor: str | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None
