"""NP-154 — mask sensitive values before they hit logs."""

from __future__ import annotations

import logging
import re
from typing import Any

# Keys (case-insensitive) whose values must never appear fully in logs.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "old_password",
        "new_password",
        "current_password",
        "token",
        "access",
        "refresh",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "apikey",
        "secret",
        "jwt",
        "tax_number",
        "vergi_no",
        "vkn",
        "phone",
        "telefon",
        "email",
        "e_mail",
        "file_content",
        "content",
        "file",
        "upload",
        "raw",
        "body_bytes",
    }
)

_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+=/]+")
_TAX_RE = re.compile(r"\b(\d{10,11})\b")
_PASSWORD_KV_RE = re.compile(
    r'(?i)("?(?:password|passwd|pwd|token|refresh|access)"?\s*[:=]\s*)("?)([^"\s,}\]]+)("?)'
)


def mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, _, domain = value.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def mask_tax_number(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 4:
        return "****"
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"


def mask_token(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def mask_string(value: str) -> str:
    """Best-effort redaction of free-form log text."""
    text = _BEARER_RE.sub("Bearer ***", value)
    text = _JWT_RE.sub(lambda m: mask_token(m.group(0)), text)
    text = _PASSWORD_KV_RE.sub(r"\1\2***\4", text)

    def _email(m: re.Match[str]) -> str:
        return mask_email(m.group(0))

    text = _EMAIL_RE.sub(_email, text)

    def _phone(m: re.Match[str]) -> str:
        return mask_phone(m.group(1))

    text = _PHONE_RE.sub(_phone, text)
    return text


def mask_value(key: str | None, value: Any) -> Any:
    if value is None:
        return None
    key_l = (key or "").lower()
    if key_l in SENSITIVE_KEYS or any(part in key_l for part in SENSITIVE_KEYS):
        if key_l in {"email", "e_mail"} and isinstance(value, str):
            return mask_email(value)
        if key_l in {"phone", "telefon"} and isinstance(value, str):
            return mask_phone(value)
        if key_l in {"tax_number", "vergi_no", "vkn"} and isinstance(value, str):
            return mask_tax_number(value)
        if isinstance(value, (bytes, bytearray)):
            return f"<binary {len(value)} bytes>"
        if isinstance(value, str) and len(value) > 32:
            return mask_token(value)
        return "***"
    if isinstance(value, dict):
        return mask_mapping(value)
    if isinstance(value, (list, tuple)):
        return [mask_value(None, item) for item in value]
    if isinstance(value, str):
        return mask_string(value)
    return value


def mask_mapping(data: dict[str, Any]) -> dict[str, Any]:
    return {k: mask_value(str(k), v) for k, v in data.items()}


class SensitiveDataFilter(logging.Filter):
    """Django LOGGING filter — NP-154."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_mapping(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(mask_value(None, a) for a in record.args)
        for attr in ("request", "data", "body"):
            if hasattr(record, attr):
                val = getattr(record, attr)
                if isinstance(val, dict):
                    setattr(record, attr, mask_mapping(val))
                elif isinstance(val, str):
                    setattr(record, attr, mask_string(val))
        return True
