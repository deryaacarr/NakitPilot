"""NP-313 — display-level PII masking (role-based)."""

from __future__ import annotations

import re


def mask_phone_display(value: str) -> str:
    """0532 *** ** 45"""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 6:
        return "***"
    # Turkish mobiles often stored as 11 digits (0 + 10) — keep leading 0 in prefix
    if len(digits) >= 11 and digits.startswith("0"):
        d = digits[-11:]
        return f"{d[:4]} *** ** {d[-2:]}"
    if len(digits) >= 10:
        d = digits[-10:]
        return f"0{d[:3]} *** ** {d[-2:]}"
    return f"{digits[:3]} *** {digits[-2:]}"


def mask_email_display(value: str) -> str:
    """me***@firma.com"""
    if "@" not in (value or ""):
        return "***"
    local, _, domain = value.partition("@")
    if not local:
        return f"***@{domain}"
    keep = min(2, len(local))
    return f"{local[:keep]}***@{domain}"


def mask_tax_display(value: str) -> str:
    """Vergi no: ******4321"""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) <= 4:
        return "****"
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"
