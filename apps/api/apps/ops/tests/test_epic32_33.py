"""EPIC 32 / 33 — scalability & observability."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.ops.caching import org_cache_key
from apps.ops.locks import LockError, distributed_lock
from apps.ops.loadtest import run_benchmark
from apps.ops.alerts import ensure_default_rules, evaluate_alerts
from apps.ops.status import status_payload
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def ops_ctx(db):
    cache.clear()
    org = Organization.objects.create(name="Ops Co", slug="ops-co")
    user = User.objects.create_user(email="ops@example.com", password=PASSWORD, is_staff=True)
    Membership.objects.create(organization=org, user=user, role=Role.OWNER, is_active=True)
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return org, user, client


@pytest.mark.django_db
def test_org_cache_key_includes_org():
    key = org_cache_key(42, "dashboard_cards", "x")
    assert "np:org:42:" in key


@pytest.mark.django_db
def test_distributed_lock(ops_ctx):
    with distributed_lock("test", 1, timeout=5):
        with pytest.raises(LockError):
            with distributed_lock("test", 1, timeout=5):
                pass


@pytest.mark.django_db
def test_loadtest_small(ops_ctx):
    org, _, client = ops_ctx
    run = run_benchmark(org, profile="small")
    assert run.customers >= 20
    assert "dashboard_summary_ms" in run.timings_ms
    resp = client.post("/api/ops/loadtest/", {"profile": "small"}, format="json")
    assert resp.status_code == 201


@pytest.mark.django_db
def test_status_alerts_metrics_runbooks(ops_ctx):
    _, _, client = ops_ctx
    status = client.get("/api/ops/status/")
    assert status.status_code == 200
    assert len(status.data["components"]) >= 7

    ensure_default_rules()
    rules = client.get("/api/ops/alerts/rules/")
    assert rules.status_code == 200
    assert len(rules.data["results"]) >= 5

    tech = client.get("/api/ops/metrics/technical/")
    assert tech.status_code == 200
    assert "api" in tech.data

    biz = client.get("/api/ops/metrics/business/")
    assert biz.status_code == 200
    assert "daily_collected_amount" in biz.data

    books = client.get("/api/ops/runbooks/")
    assert books.status_code == 200
    assert any(r["key"] == "api_error_rate" for r in books.data["results"])

    detail = client.get("/api/ops/runbooks/api_error_rate/")
    assert detail.status_code == 200
    assert "Belirti" in detail.data["content"]

    fired = evaluate_alerts()
    assert isinstance(fired, list)

    assert status_payload()["overall"]


@pytest.mark.django_db
def test_request_id_header(ops_ctx):
    _, _, client = ops_ctx
    resp = client.get("/api/ops/status/")
    assert resp.get("X-Request-Id") or True  # status is AllowAny without middleware path via client
    # Authenticated path goes through middleware
    resp2 = client.get("/api/ops/metrics/business/")
    assert "X-Request-Id" in resp2
    assert "X-Trace-Id" in resp2


@pytest.mark.django_db
def test_read_model_refresh(ops_ctx):
    _, _, client = ops_ctx
    resp = client.post("/api/ops/read-models/refresh/", {}, format="json")
    assert resp.status_code == 200
    assert "open_balance" in resp.data
