"""NP-154 / NP-151 unit tests."""

from __future__ import annotations

import logging

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.security.masking import (
    SensitiveDataFilter,
    mask_email,
    mask_mapping,
    mask_phone,
    mask_string,
    mask_tax_number,
)


def test_mask_helpers():
    assert mask_email("ayse@firma.com") == "a***@firma.com"
    assert mask_phone("+90 555 123 4567").endswith("4567")
    assert mask_tax_number("1234567890").endswith("7890")
    assert "***" in mask_string('password":"SecretPass123!"')
    assert "Bearer ***" in mask_string("Authorization: Bearer abc.def.ghi")
    masked = mask_mapping(
        {
            "email": "demo@nakitpilot.local",
            "password": "SecretPass123!",
            "tax_number": "1234567890",
            "phone": "05551234567",
            "token": "eyJhbGciOiJIUzI1NiJ9.payload.signature",
            "ok": "visible",
        }
    )
    assert masked["password"] == "***"
    assert masked["ok"] == "visible"
    assert "@" in masked["email"]
    assert masked["email"].startswith("d")


def test_logging_filter_redacts_message():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='login failed password=SecretPass123! email=user@example.com',
        args=(),
        exc_info=None,
    )
    SensitiveDataFilter().filter(record)
    assert "SecretPass123!" not in record.msg
    assert "user@example.com" not in record.msg


@pytest.mark.django_db
@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_RATES": {
            "auth_login": "2/min",
            "auth_refresh": "1000/min",
            "import_upload": "1000/min",
        },
    },
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
def test_login_rate_limit():
    cache.clear()
    client = APIClient()
    for _ in range(2):
        response = client.post(
            "/api/auth/login",
            {"email": "nobody@example.com", "password": "wrong"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    limited = client.post(
        "/api/auth/login",
        {"email": "nobody@example.com", "password": "wrong"},
        format="json",
    )
    assert limited.status_code == status.HTTP_429_TOO_MANY_REQUESTS
