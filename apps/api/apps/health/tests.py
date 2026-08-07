"""NP-184 health endpoint tests."""

from unittest.mock import patch

import pytest
from django.test import Client


@pytest.mark.django_db
@patch("apps.health.views._check_redis", return_value={"ok": True})
def test_legacy_health_ready(_redis_ok):
    client = Client()
    response = client.get("/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["postgres"]["ok"] is True


def test_live_no_db():
    client = Client()
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "live"


@pytest.mark.django_db
@patch("apps.health.views._check_redis", return_value={"ok": True})
def test_ready_ok(_redis_ok, settings, tmp_path):
    settings.PRIVATE_UPLOAD_ROOT = tmp_path / "uploads"
    client = Client()
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["postgres"]["ok"] is True
    assert body["checks"]["storage"]["ok"] is True
