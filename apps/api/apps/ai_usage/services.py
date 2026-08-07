"""NP-235 — metering, limits, truncation, and cache helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from apps.ai_usage.models import (
    AIFeature,
    AIPackage,
    AIUsageEvent,
    AIUsageLimitConfig,
    ZERO,
)

# Default package quotas when org has no AIUsageLimitConfig row yet.
PACKAGE_DEFAULTS: dict[str, dict[str, Any]] = {
    AIPackage.STARTER: {
        "package_monthly_tokens": 100_000,
        "daily_user_tokens": 10_000,
        "org_budget_monthly": Decimal("50.0000"),
        "max_input_chars": 8_000,
        "cache_ttl_seconds": 3_600,
    },
    AIPackage.PRO: {
        "package_monthly_tokens": 500_000,
        "daily_user_tokens": 50_000,
        "org_budget_monthly": Decimal("250.0000"),
        "max_input_chars": 16_000,
        "cache_ttl_seconds": 3_600,
    },
    AIPackage.ENTERPRISE: {
        "package_monthly_tokens": 2_000_000,
        "daily_user_tokens": 200_000,
        "org_budget_monthly": Decimal("1000.0000"),
        "max_input_chars": 32_000,
        "cache_ttl_seconds": 7_200,
    },
}

# USD-ish cost per 1k tokens by model (configurable via settings.AI_USAGE_MODEL_RATES).
DEFAULT_MODEL_RATES: dict[str, dict[str, Decimal]] = {
    "deterministic": {"input": ZERO, "output": ZERO},
    "gpt-4o-mini": {"input": Decimal("0.000150"), "output": Decimal("0.000600")},
    "gpt-4o": {"input": Decimal("0.002500"), "output": Decimal("0.010000")},
}


class AIUsageLimitExceeded(Exception):
    def __init__(self, message: str, code: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


@dataclass
class TruncationResult:
    text: str
    truncated: bool
    original_chars: int
    max_chars: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) for metering without a tokenizer."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def model_rates(model: str) -> dict[str, Decimal]:
    configured = getattr(settings, "AI_USAGE_MODEL_RATES", None) or {}
    if model in configured:
        raw = configured[model]
        return {
            "input": Decimal(str(raw.get("input", 0))),
            "output": Decimal(str(raw.get("output", 0))),
        }
    return DEFAULT_MODEL_RATES.get(
        model, {"input": Decimal("0.001"), "output": Decimal("0.002")}
    )


def estimate_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    rates = model_rates(model)
    cost = (
        Decimal(input_tokens) / Decimal(1000) * rates["input"]
        + Decimal(output_tokens) / Decimal(1000) * rates["output"]
    )
    return cost.quantize(Decimal("0.000001"))


def get_or_create_limit_config(organization) -> AIUsageLimitConfig:
    defaults = PACKAGE_DEFAULTS[AIPackage.STARTER]
    config, _ = AIUsageLimitConfig.objects.get_or_create(
        organization=organization,
        defaults={
            "package": AIPackage.STARTER,
            **defaults,
        },
    )
    return config


def apply_package_defaults(config: AIUsageLimitConfig, package: str) -> AIUsageLimitConfig:
    defaults = PACKAGE_DEFAULTS.get(package) or PACKAGE_DEFAULTS[AIPackage.STARTER]
    config.package = package
    for key, value in defaults.items():
        setattr(config, key, value)
    config.save()
    return config


def truncate_content(text: str, max_chars: int) -> TruncationResult:
    original = text or ""
    if max_chars <= 0 or len(original) <= max_chars:
        return TruncationResult(
            text=original,
            truncated=False,
            original_chars=len(original),
            max_chars=max_chars,
        )
    clipped = original[: max(0, max_chars - 1)].rstrip() + "…"
    return TruncationResult(
        text=clipped,
        truncated=True,
        original_chars=len(original),
        max_chars=max_chars,
    )


def _month_start(today: date | None = None) -> date:
    today = today or timezone.localdate()
    return today.replace(day=1)


def _usage_qs(organization, *, user=None, since: date | None = None):
    qs = AIUsageEvent.objects.filter(organization=organization)
    if user is not None:
        qs = qs.filter(user=user)
    if since is not None:
        qs = qs.filter(created_at__date__gte=since)
    return qs


def usage_totals(organization, *, user=None, since: date | None = None) -> dict[str, Any]:
    agg = _usage_qs(organization, user=user, since=since).aggregate(
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        estimated_cost=Sum("estimated_cost"),
    )
    input_tokens = int(agg["input_tokens"] or 0)
    output_tokens = int(agg["output_tokens"] or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost": Decimal(str(agg["estimated_cost"] or ZERO)),
    }


def check_limits(
    organization,
    *,
    user=None,
    extra_tokens: int = 0,
    extra_cost: Decimal = ZERO,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    Enforce package monthly tokens, daily user tokens, and org monthly budget.

    Raises AIUsageLimitExceeded when a hard limit would be breached.
    """
    today = as_of or timezone.localdate()
    config = get_or_create_limit_config(organization)
    month_totals = usage_totals(organization, since=_month_start(today))
    day_user = (
        usage_totals(organization, user=user, since=today)
        if user is not None
        else {"total_tokens": 0, "estimated_cost": ZERO}
    )

    projected_month_tokens = month_totals["total_tokens"] + extra_tokens
    projected_day_tokens = int(day_user["total_tokens"]) + extra_tokens
    projected_cost = month_totals["estimated_cost"] + Decimal(str(extra_cost))

    status = {
        "package": config.package,
        "package_monthly_tokens": config.package_monthly_tokens,
        "package_tokens_used": month_totals["total_tokens"],
        "daily_user_tokens": config.daily_user_tokens,
        "daily_user_tokens_used": int(day_user["total_tokens"]),
        "org_budget_monthly": str(config.org_budget_monthly),
        "org_budget_used": str(month_totals["estimated_cost"]),
        "max_input_chars": config.max_input_chars,
        "cache_ttl_seconds": config.cache_ttl_seconds,
        "allowed": True,
    }

    if projected_month_tokens > config.package_monthly_tokens:
        raise AIUsageLimitExceeded(
            "Paket aylık AI token limiti aşıldı.",
            "package_limit",
            details=status,
        )
    if user is not None and projected_day_tokens > config.daily_user_tokens:
        raise AIUsageLimitExceeded(
            "Günlük kullanıcı AI limiti aşıldı.",
            "daily_user_limit",
            details=status,
        )
    if projected_cost > config.org_budget_monthly:
        raise AIUsageLimitExceeded(
            "Organizasyon AI bütçesi aşıldı.",
            "org_budget",
            details=status,
        )
    return status


def record_usage(
    *,
    organization,
    user=None,
    feature: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model: str = "deterministic",
    estimated_cost: Decimal | None = None,
    cache_hit: bool = False,
    truncated: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AIUsageEvent:
    if feature not in AIFeature.values:
        feature = AIFeature.GENERIC
    cost = estimated_cost
    if cost is None:
        cost = estimate_cost(
            model=model, input_tokens=input_tokens, output_tokens=output_tokens
        )
    return AIUsageEvent.objects.create(
        organization=organization,
        user=user,
        feature=feature,
        input_tokens=max(0, int(input_tokens)),
        output_tokens=max(0, int(output_tokens)),
        estimated_cost=cost,
        model=model or "deterministic",
        cache_hit=cache_hit,
        truncated=truncated,
        metadata=metadata or {},
    )


def cache_key_for(
    *,
    organization_id: int,
    feature: str,
    payload: Any,
) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"ai_usage:{organization_id}:{feature}:{digest}"


def get_cached(key: str) -> Any | None:
    return cache.get(key)


def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    cache.set(key, value, timeout=ttl_seconds)


def run_metered(
    *,
    organization,
    user=None,
    feature: str,
    model: str = "deterministic",
    input_text: str = "",
    cache_payload: Any | None = None,
    producer: Callable[[str], Any],
) -> dict[str, Any]:
    """
    Truncate → cache → limit check → produce → record usage.

    ``producer`` receives the (possibly truncated) input text and returns
    any JSON-serializable result. For dict results, output tokens are
    estimated from ``json.dumps(result)``.
    """
    config = get_or_create_limit_config(organization)
    truncation = truncate_content(input_text, config.max_input_chars)
    prepared = truncation.text

    key = None
    if cache_payload is not None and config.cache_ttl_seconds > 0:
        key = cache_key_for(
            organization_id=organization.id,
            feature=feature,
            payload={"input": prepared, "extra": cache_payload},
        )
        cached = get_cached(key)
        if cached is not None:
            record_usage(
                organization=organization,
                user=user,
                feature=feature,
                input_tokens=0,
                output_tokens=0,
                model=model,
                estimated_cost=ZERO,
                cache_hit=True,
                truncated=truncation.truncated,
                metadata={"cache_key": key},
            )
            return {
                "result": cached,
                "cache_hit": True,
                "truncated": truncation.truncated,
                "usage_recorded": True,
            }

    in_tokens = estimate_tokens(prepared)
    # Optimistic output budget for limit check (updated after produce).
    check_limits(
        organization,
        user=user,
        extra_tokens=in_tokens,
        extra_cost=estimate_cost(model=model, input_tokens=in_tokens, output_tokens=0),
    )

    result = producer(prepared)
    out_blob = result if isinstance(result, str) else json.dumps(result, default=str)
    out_tokens = estimate_tokens(out_blob)
    cost = estimate_cost(
        model=model, input_tokens=in_tokens, output_tokens=out_tokens
    )
    # Re-check with full cost (may raise if budget tight).
    check_limits(
        organization,
        user=user,
        extra_tokens=in_tokens + out_tokens,
        extra_cost=cost,
    )
    event = record_usage(
        organization=organization,
        user=user,
        feature=feature,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        model=model,
        estimated_cost=cost,
        cache_hit=False,
        truncated=truncation.truncated,
        metadata={"cache_key": key} if key else {},
    )
    if key is not None:
        set_cached(key, result, config.cache_ttl_seconds)
    return {
        "result": result,
        "cache_hit": False,
        "truncated": truncation.truncated,
        "usage_event_id": event.id,
        "usage_recorded": True,
    }


def usage_summary(organization, *, user=None) -> dict[str, Any]:
    today = timezone.localdate()
    config = get_or_create_limit_config(organization)
    month = usage_totals(organization, since=_month_start(today))
    day = usage_totals(organization, user=user, since=today) if user else None
    return {
        "organization_id": organization.id,
        "user_id": getattr(user, "id", None),
        "package": config.package,
        "limits": {
            "package_monthly_tokens": config.package_monthly_tokens,
            "daily_user_tokens": config.daily_user_tokens,
            "org_budget_monthly": str(config.org_budget_monthly),
            "max_input_chars": config.max_input_chars,
            "cache_ttl_seconds": config.cache_ttl_seconds,
        },
        "usage": {
            "month": {
                "input_tokens": month["input_tokens"],
                "output_tokens": month["output_tokens"],
                "total_tokens": month["total_tokens"],
                "estimated_cost": str(month["estimated_cost"]),
            },
            "today_user": (
                {
                    "input_tokens": day["input_tokens"],
                    "output_tokens": day["output_tokens"],
                    "total_tokens": day["total_tokens"],
                    "estimated_cost": str(day["estimated_cost"]),
                }
                if day
                else None
            ),
        },
        "controls": [
            "package_usage",
            "daily_user_limit",
            "organization_budget",
            "long_content_truncation",
            "cache",
        ],
    }
