"""NP-183 / NP-185 tests."""

import os
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from config.sentry import before_send

User = get_user_model()


def test_sentry_before_send_scrubs_secrets():
    event = {
        "request": {
            "headers": {"Authorization": "Bearer super-secret-token", "Content-Type": "application/json"},
            "data": {"password": "hunter2", "email": "user@example.com", "amount": "10.00"},
            "cookies": {"sessionid": "abc"},
        },
        "user": {"id": "9", "email": "user@example.com"},
        "message": "Bearer eyJhbGciOiJIUzI1NiJ9.aaa.bbb failed for user@example.com",
    }
    scrubbed = before_send(event, {})
    assert scrubbed is not None
    assert scrubbed["request"]["headers"]["Authorization"] == "***"
    assert scrubbed["request"]["data"]["password"] == "***"
    assert scrubbed["request"]["cookies"] == "***"
    assert "email" not in scrubbed["user"]
    assert scrubbed["user"]["id"] == "9"
    assert "hunter2" not in str(scrubbed)
    assert "Bearer ***" in scrubbed["message"] or "***jwt***" in scrubbed["message"]


@pytest.mark.django_db
def test_create_initial_admin_from_env(capsys):
    with patch.dict(
        os.environ,
        {
            "INITIAL_ADMIN_EMAIL": "admin@nakitpilot.local",
            "INITIAL_ADMIN_PASSWORD": "VerySecurePass1!",
        },
        clear=False,
    ):
        call_command("create_initial_admin", "--noinput")
    user = User.objects.get(email="admin@nakitpilot.local")
    assert user.is_superuser is True
    assert user.check_password("VerySecurePass1!")
    out = capsys.readouterr().out
    assert "VerySecurePass1!" not in out


@pytest.mark.django_db
def test_create_initial_admin_requires_env_with_noinput():
    with patch.dict(os.environ, {"INITIAL_ADMIN_PASSWORD": ""}, clear=False):
        os.environ.pop("INITIAL_ADMIN_PASSWORD", None)
        with pytest.raises(CommandError):
            call_command("create_initial_admin", "--noinput", "--email", "x@y.com")
