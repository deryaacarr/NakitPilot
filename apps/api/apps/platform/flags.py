"""NP-362 — feature flag evaluation."""

from __future__ import annotations

import hashlib
from typing import Any

from django.conf import settings

from apps.platform.models import FeatureFlag, FeatureFlagKey

KNOWN_FLAGS = [c.value for c in FeatureFlagKey]


def _stable_bucket(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def current_environment() -> str:
    return (
        getattr(settings, "NAKITPILOT_ENV", None)
        or getattr(settings, "ENVIRONMENT", None)
        or "development"
    ).lower()


def is_feature_enabled(
    key: str,
    *,
    organization=None,
    user=None,
    plan_code: str | None = None,
    environment: str | None = None,
) -> bool:
    try:
        flag = FeatureFlag.objects.get(key=key)
    except FeatureFlag.DoesNotExist:
        return False
    if not flag.enabled:
        return False

    env = (environment or current_environment()).lower()
    envs = [str(e).lower() for e in (flag.environments or [])]
    if envs and env not in envs:
        return False

    if plan_code is None and organization is not None:
        try:
            from apps.billing.models import Subscription, SubscriptionStatus

            sub = (
                Subscription.objects.filter(
                    organization=organization,
                    status__in=[
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING,
                        SubscriptionStatus.PAST_DUE,
                    ],
                )
                .select_related("plan")
                .first()
            )
            if sub and sub.plan_id:
                plan_code = sub.plan.code
        except Exception:
            plan_code = None

    plans = [str(p).upper() for p in (flag.plan_codes or [])]
    if plans and (plan_code or "").upper() not in plans:
        return False

    org_ids = [int(x) for x in (flag.organization_ids or []) if str(x).isdigit() or isinstance(x, int)]
    if org_ids:
        if organization is None or organization.pk not in org_ids:
            return False

    pct = int(flag.rollout_percentage or 0)
    if pct <= 0:
        return False
    if pct < 100:
        seed_parts = [key]
        if organization is not None:
            seed_parts.append(f"org:{organization.pk}")
        if user is not None:
            seed_parts.append(f"user:{user.pk}")
        if _stable_bucket("|".join(seed_parts)) >= pct:
            return False
    return True


def evaluate_flags(
    *,
    organization=None,
    user=None,
    keys: list[str] | None = None,
) -> dict[str, bool]:
    keys = keys or KNOWN_FLAGS
    return {
        key: is_feature_enabled(key, organization=organization, user=user)
        for key in keys
    }


def flag_payload(flag: FeatureFlag) -> dict[str, Any]:
    return {
        "id": flag.id,
        "key": flag.key,
        "description": flag.description,
        "enabled": flag.enabled,
        "environments": flag.environments or [],
        "plan_codes": flag.plan_codes or [],
        "organization_ids": flag.organization_ids or [],
        "rollout_percentage": flag.rollout_percentage,
        "updated_at": flag.updated_at.isoformat() if flag.updated_at else None,
    }
