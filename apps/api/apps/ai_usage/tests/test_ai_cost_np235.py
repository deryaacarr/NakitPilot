"""NP-235 AI cost control tests."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.ai_usage.models import AIFeature, AIUsageEvent
from apps.ai_usage.services import (
    AIUsageLimitExceeded,
    check_limits,
    estimate_cost,
    get_or_create_limit_config,
    record_usage,
    run_metered,
    truncate_content,
    usage_summary,
)
from apps.organizations.models import Organization

User = get_user_model()


@pytest.fixture
def ai_ctx(db):
    org = Organization.objects.create(name="AI Co", slug="ai-co-np235")
    user = User.objects.create_user(email="ai@example.com", password="x")
    config = get_or_create_limit_config(org)
    return org, user, config


@pytest.mark.django_db
def test_record_usage_metric_fields(ai_ctx):
    org, user, _ = ai_ctx
    event = record_usage(
        organization=org,
        user=user,
        feature=AIFeature.MESSAGE_ASSISTANT,
        input_tokens=100,
        output_tokens=50,
        model="gpt-4o-mini",
    )
    assert event.organization_id == org.id
    assert event.user_id == user.id
    assert event.feature == AIFeature.MESSAGE_ASSISTANT
    assert event.input_tokens == 100
    assert event.output_tokens == 50
    assert event.estimated_cost > 0
    assert event.model == "gpt-4o-mini"
    assert event.created_at is not None


@pytest.mark.django_db
def test_truncate_long_content(ai_ctx):
    result = truncate_content("a" * 100, max_chars=20)
    assert result.truncated is True
    assert len(result.text) <= 20
    assert result.original_chars == 100


@pytest.mark.django_db
def test_package_monthly_limit(ai_ctx):
    org, user, config = ai_ctx
    config.package_monthly_tokens = 100
    config.save(update_fields=["package_monthly_tokens"])
    record_usage(
        organization=org,
        user=user,
        feature=AIFeature.GENERIC,
        input_tokens=80,
        output_tokens=20,
        model="deterministic",
        estimated_cost=Decimal("0"),
    )
    with pytest.raises(AIUsageLimitExceeded) as exc:
        check_limits(org, user=user, extra_tokens=1)
    assert exc.value.code == "package_limit"


@pytest.mark.django_db
def test_daily_user_limit(ai_ctx):
    org, user, config = ai_ctx
    config.daily_user_tokens = 50
    config.package_monthly_tokens = 1_000_000
    config.save(update_fields=["daily_user_tokens", "package_monthly_tokens"])
    record_usage(
        organization=org,
        user=user,
        feature=AIFeature.GENERIC,
        input_tokens=40,
        output_tokens=10,
        model="deterministic",
        estimated_cost=Decimal("0"),
    )
    with pytest.raises(AIUsageLimitExceeded) as exc:
        check_limits(org, user=user, extra_tokens=1)
    assert exc.value.code == "daily_user_limit"


@pytest.mark.django_db
def test_org_budget_limit(ai_ctx):
    org, user, config = ai_ctx
    config.org_budget_monthly = Decimal("1.0000")
    config.package_monthly_tokens = 1_000_000
    config.daily_user_tokens = 1_000_000
    config.save(
        update_fields=[
            "org_budget_monthly",
            "package_monthly_tokens",
            "daily_user_tokens",
        ]
    )
    record_usage(
        organization=org,
        user=user,
        feature=AIFeature.GENERIC,
        input_tokens=1,
        output_tokens=1,
        model="gpt-4o",
        estimated_cost=Decimal("0.9000"),
    )
    with pytest.raises(AIUsageLimitExceeded) as exc:
        check_limits(org, user=user, extra_cost=Decimal("0.2000"))
    assert exc.value.code == "org_budget"


@pytest.mark.django_db
def test_cache_hit_records_zero_cost(ai_ctx):
    org, user, config = ai_ctx
    config.cache_ttl_seconds = 60
    config.save(update_fields=["cache_ttl_seconds"])
    calls = {"n": 0}

    def producer(_text: str):
        calls["n"] += 1
        return {"ok": True, "value": 42}

    first = run_metered(
        organization=org,
        user=user,
        feature=AIFeature.PAYMENT_PLAN,
        input_text="hello",
        cache_payload={"k": 1},
        producer=producer,
    )
    second = run_metered(
        organization=org,
        user=user,
        feature=AIFeature.PAYMENT_PLAN,
        input_text="hello",
        cache_payload={"k": 1},
        producer=producer,
    )
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert calls["n"] == 1
    assert AIUsageEvent.objects.filter(organization=org, cache_hit=True).count() == 1


@pytest.mark.django_db
def test_usage_summary_lists_controls(ai_ctx):
    org, user, _ = ai_ctx
    summary = usage_summary(org, user=user)
    assert summary["organization_id"] == org.id
    assert summary["user_id"] == user.id
    for key in (
        "package_usage",
        "daily_user_limit",
        "organization_budget",
        "long_content_truncation",
        "cache",
    ):
        assert key in summary["controls"]


@pytest.mark.django_db
def test_estimate_cost_deterministic_zero():
    assert estimate_cost(model="deterministic", input_tokens=1000, output_tokens=1000) == 0
