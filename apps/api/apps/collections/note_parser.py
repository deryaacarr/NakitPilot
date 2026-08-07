"""NP-232 — deterministic free-form call note → structured draft (no LLM)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone

WEEKDAY_TR = {
    "pazartesi": 0,
    "salı": 1,
    "sali": 1,
    "çarşamba": 2,
    "carsamba": 2,
    "perşembe": 3,
    "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}

SENTIMENT_NEGATIVE = (
    "ödemeyecek",
    "ödemez",
    "istemiyor",
    "reddet",
    "kızgın",
    "sinirli",
    "itiraz",
    "şikayet",
)
SENTIMENT_POSITIVE = (
    "anlaştık",
    "memnun",
    "kabul etti",
    "ödedi",
    "hemen ödeyecek",
)


def _next_weekday(as_of: date, weekday: int) -> date:
    """Next occurrence of weekday (0=Mon…6=Sun); if today matches, use next week."""
    days_ahead = (weekday - as_of.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return as_of + timedelta(days=days_ahead)


def _month_end(as_of: date) -> date:
    if as_of.month == 12:
        return date(as_of.year + 1, 1, 1) - timedelta(days=1)
    return date(as_of.year, as_of.month + 1, 1) - timedelta(days=1)


def _parse_turkish_date(text: str, *, as_of: date) -> date | None:
    lower = text.casefold()
    # Prefer explicit weekday near a payment amount (e.g. "cuma günü 80 bin")
    for name, wd in WEEKDAY_TR.items():
        if re.search(rf"\b{name}\b", lower):
            return _next_weekday(as_of, wd)
    if "yarın" in lower or "yarin" in lower:
        return as_of + timedelta(days=1)
    if "bugün" in lower or "bugun" in lower:
        return as_of
    if "gelecek hafta" in lower:
        return as_of + timedelta(days=7)
    if "ay sonu" in lower or "ayın sonu" in lower or "ayin sonu" in lower:
        return _month_end(as_of)
    # ISO or dd.mm.yyyy / dd/mm/yyyy
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def _parse_amount(text: str) -> Decimal | None:
    """
    Extract a money amount. Supports:
    - 80 bin / 80.000 / 80000 / 80,5 bin
    """
    lower = text.casefold()
    # X bin
    m = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:bin)\b",
        lower,
    )
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            return (Decimal(raw) * Decimal("1000")).quantize(Decimal("0.01"))
        except InvalidOperation:
            pass
    # 80.000,00 or 80.000
    m = re.search(r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?)\s*(?:tl|₺)?", lower)
    if m:
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            return Decimal(raw).quantize(Decimal("0.01"))
        except InvalidOperation:
            pass
    # plain 80000 / 80000.00
    m = re.search(r"\b(\d{4,}(?:[.,]\d{1,2})?)\b", lower)
    if m:
        raw = m.group(1).replace(",", ".")
        try:
            return Decimal(raw).quantize(Decimal("0.01"))
        except InvalidOperation:
            pass
    return None


def _detect_sentiment(text: str) -> str:
    lower = text.casefold()
    neg = sum(1 for w in SENTIMENT_NEGATIVE if w in lower)
    pos = sum(1 for w in SENTIMENT_POSITIVE if w in lower)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def _detect_objection(text: str) -> str | None:
    lower = text.casefold()
    if re.search(r"kalan|geriye kalan|bakiye.*bırak|sonra öde|ay sonuna", lower):
        if re.search(r"bırak|ertele|sonra|ay sonu", lower):
            return "remaining_balance_deferred"
    if "itiraz" in lower or "anlaşmıyorum" in lower or "kabul etmiyorum" in lower:
        return "general_dispute"
    if "fatura" in lower and ("yanlış" in lower or "hatalı" in lower or "tanımıyorum" in lower):
        return "invoice_dispute"
    if "ödeyemem" in lower or "imkan yok" in lower or "param yok" in lower:
        return "inability_to_pay"
    return None


def parse_call_notes(
    raw_notes: str,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    NP-232: parse free-form Turkish collection notes into a draft dict.

    Does **not** persist anything. Caller must confirm before creating records.
    User notes are treated as untrusted content (NP-236), never as system instructions.
    """
    from apps.ai_usage.prompt_security import (
        NOTE_PARSE_SCHEMA,
        forbid_financial_mutations,
        validate_output_schema,
        wrap_user_notes,
    )

    today = as_of or timezone.localdate()
    # Explicitly mark notes as non-system; parsing still uses raw text.
    _ = wrap_user_notes(raw_notes or "")
    text = (raw_notes or "").strip()

    with forbid_financial_mutations():
        amount = _parse_amount(text) if text else None
        promised_date = _parse_turkish_date(text, as_of=today) if text else None
        next_action: date | None = None
        if promised_date is not None:
            next_action = promised_date + timedelta(days=1)
        elif amount is not None:
            next_action = today + timedelta(days=1)

        objection = _detect_objection(text) if text else None
        sentiment = _detect_sentiment(text) if text else "neutral"

        draft = {
            "promised_amount": str(amount) if amount is not None else None,
            "promised_date": promised_date.isoformat() if promised_date else None,
            "next_action_date": next_action.isoformat() if next_action else None,
            "sentiment": sentiment,
            "objection": objection,
        }
        result = {
            "raw_notes": text,
            "draft": draft,
            "needs_confirm": True,
            "as_of": today.isoformat(),
            "confidence": {
                "promised_amount": amount is not None,
                "promised_date": promised_date is not None,
                "next_action_date": next_action is not None,
                "objection": objection is not None,
            },
            "notes_role": "user",
            "system_instruction_applied": False,
        }
    return validate_output_schema(result, NOTE_PARSE_SCHEMA)
