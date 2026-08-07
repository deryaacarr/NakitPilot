"""Strict money/date conversion helpers for integration sync (NP-194)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

MONEY_QUANT = Decimal("0.01")


def parse_money(value: Any, *, field_name: str = "amount") -> Decimal:
    if value is None or value == "":
        raise ValueError(f"{field_name} gerekli.")
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"{field_name} geçersiz para değeri: {value!r}") from exc
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def parse_optional_money(value: Any, *, default: Decimal = Decimal("0.00")) -> Decimal:
    if value is None or value == "":
        return default.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    return parse_money(value)


def parse_date(value: Any, *, field_name: str = "date") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        raise ValueError(f"{field_name} gerekli.")
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"{field_name} geçersiz tarih: {value!r}") from exc
