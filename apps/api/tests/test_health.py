from unittest.mock import patch

import pytest
from django.test import Client


@pytest.mark.django_db
@patch("apps.health.views._check_redis", return_value={"ok": True})
def test_healthcheck_ok(_redis_ok):
    client = Client()
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["postgres"]["ok"] is True
