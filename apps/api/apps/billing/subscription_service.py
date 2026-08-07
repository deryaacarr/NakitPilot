"""NP-281 — centralized feature entitlement checks.

Usage:
    subscription_service.can_use(organization, feature="advanced_workflows")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.billing.models import (
    PlanCode,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)

# Canonical feature keys — never scatter plan == "..." in call sites
class Feature:
    MAX_USERS = "max_users"
    MAX_CUSTOMERS = "max_customers"
    MONTHLY_INVOICE_SYNCS = "monthly_invoice_syncs"
    AI_MONTHLY_TOKENS = "ai_monthly_tokens"
    MAX_WORKFLOWS = "max_workflows"
    MAX_INTEGRATIONS = "max_integrations"
    API_ACCESS = "api_access"
    WEBHOOK_ACCESS = "webhook_access"
    REPORT_EXPORT = "report_export"
    ADVANCED_WORKFLOWS = "advanced_workflows"
    FORECAST_SCENARIOS = "forecast_scenarios"
    WHAT_IF_ANALYSIS = "what_if_analysis"


DEFAULT_ENTITLEMENTS: dict[str, dict[str, Any]] = {
    PlanCode.STARTER: {
        Feature.MAX_USERS: 3,
        Feature.MAX_CUSTOMERS: 200,
        Feature.MONTHLY_INVOICE_SYNCS: 2,
        Feature.AI_MONTHLY_TOKENS: 50_000,
        Feature.MAX_WORKFLOWS: 3,
        Feature.MAX_INTEGRATIONS: 1,
        Feature.API_ACCESS: False,
        Feature.WEBHOOK_ACCESS: False,
        Feature.REPORT_EXPORT: True,
        Feature.ADVANCED_WORKFLOWS: False,
        Feature.FORECAST_SCENARIOS: False,
        Feature.WHAT_IF_ANALYSIS: False,
    },
    PlanCode.PROFESSIONAL: {
        Feature.MAX_USERS: 10,
        Feature.MAX_CUSTOMERS: 2000,
        Feature.MONTHLY_INVOICE_SYNCS: 30,
        Feature.AI_MONTHLY_TOKENS: 250_000,
        Feature.MAX_WORKFLOWS: 20,
        Feature.MAX_INTEGRATIONS: 5,
        Feature.API_ACCESS: True,
        Feature.WEBHOOK_ACCESS: True,
        Feature.REPORT_EXPORT: True,
        Feature.ADVANCED_WORKFLOWS: True,
        Feature.FORECAST_SCENARIOS: True,
        Feature.WHAT_IF_ANALYSIS: True,
    },
    PlanCode.BUSINESS: {
        Feature.MAX_USERS: 50,
        Feature.MAX_CUSTOMERS: 20_000,
        Feature.MONTHLY_INVOICE_SYNCS: 100,
        Feature.AI_MONTHLY_TOKENS: 1_000_000,
        Feature.MAX_WORKFLOWS: 100,
        Feature.MAX_INTEGRATIONS: 20,
        Feature.API_ACCESS: True,
        Feature.WEBHOOK_ACCESS: True,
        Feature.REPORT_EXPORT: True,
        Feature.ADVANCED_WORKFLOWS: True,
        Feature.FORECAST_SCENARIOS: True,
        Feature.WHAT_IF_ANALYSIS: True,
    },
    PlanCode.ENTERPRISE: {
        Feature.MAX_USERS: 10_000,
        Feature.MAX_CUSTOMERS: 1_000_000,
        Feature.MONTHLY_INVOICE_SYNCS: 10_000,
        Feature.AI_MONTHLY_TOKENS: 10_000_000,
        Feature.MAX_WORKFLOWS: 10_000,
        Feature.MAX_INTEGRATIONS: 10_000,
        Feature.API_ACCESS: True,
        Feature.WEBHOOK_ACCESS: True,
        Feature.REPORT_EXPORT: True,
        Feature.ADVANCED_WORKFLOWS: True,
        Feature.FORECAST_SCENARIOS: True,
        Feature.WHAT_IF_ANALYSIS: True,
    },
}

PLAN_META = {
    PlanCode.STARTER: ("Starter", Decimal("990.00"), 0),
    PlanCode.PROFESSIONAL: ("Professional", Decimal("2990.00"), 1),
    PlanCode.BUSINESS: ("Business", Decimal("6990.00"), 2),
    PlanCode.ENTERPRISE: ("Enterprise", Decimal("0.00"), 3),
}


class EntitlementDenied(Exception):
    def __init__(self, message: str, code: str = "entitlement_denied", feature: str = ""):
        super().__init__(message)
        self.message = message
        self.code = code
        self.feature = feature


@dataclass
class EntitlementResult:
    allowed: bool
    feature: str
    limit: Any = None
    current: Any = None
    plan_code: str = ""
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "feature": self.feature,
            "limit": self.limit,
            "current": self.current,
            "plan_code": self.plan_code,
            "reason": self.reason,
        }


def ensure_default_plans() -> list[SubscriptionPlan]:
    created = []
    for code, (name, price, order) in PLAN_META.items():
        plan, was = SubscriptionPlan.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "price_monthly": price,
                "price_yearly": (price * 10) if price > 0 else Decimal("0"),
                "entitlements": DEFAULT_ENTITLEMENTS[code],
                "sort_order": order,
                "is_active": True,
            },
        )
        # Keep entitlements in sync with code defaults for system plans
        if plan.entitlements != DEFAULT_ENTITLEMENTS[code]:
            plan.entitlements = DEFAULT_ENTITLEMENTS[code]
            plan.save(update_fields=["entitlements", "updated_at"])
        if was:
            created.append(plan)
    return created


def get_active_subscription(organization) -> Subscription | None:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    return (
        Subscription.objects.filter(
            organization_id=org_id,
            status__in=[
                SubscriptionStatus.TRIALING,
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.PAST_DUE,
            ],
        )
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )


def ensure_subscription(organization, *, plan_code: str = PlanCode.STARTER) -> Subscription:
    ensure_default_plans()
    existing = get_active_subscription(organization)
    if existing:
        return existing
    # Prefer most recent subscription even if expired (for read-only restoration UX)
    org_id = organization.pk if hasattr(organization, "pk") else organization
    expired = (
        Subscription.objects.filter(organization_id=org_id)
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )
    if expired and expired.status in (
        SubscriptionStatus.EXPIRED,
        SubscriptionStatus.CANCELLED,
    ):
        return expired
    plan = SubscriptionPlan.objects.get(code=plan_code)
    return Subscription.objects.create(
        organization_id=org_id,
        plan=plan,
        status=SubscriptionStatus.TRIALING,
        seats=1,
        card_required=False,
        trial_ends_at=timezone.now() + timedelta(days=14),
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=14),
    )


def get_entitlements(organization) -> dict[str, Any]:
    ensure_default_plans()
    sub = get_active_subscription(organization)
    if sub is None:
        return dict(DEFAULT_ENTITLEMENTS[PlanCode.STARTER])
    ents = dict(DEFAULT_ENTITLEMENTS.get(sub.plan.code, DEFAULT_ENTITLEMENTS[PlanCode.STARTER]))
    ents.update(sub.plan.entitlements or {})
    return ents


def _usage_for_feature(organization, feature: str) -> int | None:
    """Return current usage for limit-style features, else None."""
    org_id = organization.pk if hasattr(organization, "pk") else organization
    if feature == Feature.MAX_USERS:
        from apps.organizations.models import Membership

        return Membership.objects.filter(organization_id=org_id, is_active=True).count()
    if feature == Feature.MAX_CUSTOMERS:
        from apps.customers.models import Customer

        return Customer.objects.filter(organization_id=org_id, is_active=True).count()
    if feature == Feature.MAX_WORKFLOWS:
        try:
            from apps.workflows.models import CollectionWorkflow

            return CollectionWorkflow.objects.filter(organization_id=org_id).count()
        except Exception:  # noqa: BLE001
            return 0
    if feature == Feature.MAX_INTEGRATIONS:
        try:
            from apps.integrations.models import IntegrationConnection

            return IntegrationConnection.objects.filter(organization_id=org_id).count()
        except Exception:  # noqa: BLE001
            return 0
    return None


def assert_writable(organization) -> None:
    """NP-283/284 — block mutations when trial/dunning left the org read-only."""
    from apps.billing.trial import is_read_only

    if is_read_only(organization):
        raise EntitlementDenied(
            "Abonelik salt okunur modda (deneme veya ödeme süresi doldu).",
            code="read_only",
        )


def can_use(
    organization,
    feature: str,
    *,
    quantity: int = 1,
) -> EntitlementResult:
    """
    Central entitlement gate (NP-281).

    Boolean features → allowed True/False.
    Numeric limits → allowed if current + quantity <= limit.
    """
    ents = get_entitlements(organization)
    sub = get_active_subscription(organization)
    plan_code = sub.plan.code if sub else PlanCode.STARTER
    if feature not in ents:
        return EntitlementResult(
            allowed=False,
            feature=feature,
            plan_code=plan_code,
            reason="Bilinmeyen özellik.",
        )
    limit = ents[feature]
    if isinstance(limit, bool):
        return EntitlementResult(
            allowed=bool(limit),
            feature=feature,
            limit=limit,
            plan_code=plan_code,
            reason="" if limit else "Paketinizin bu özelliğe erişimi yok.",
        )
    if isinstance(limit, (int, float, Decimal)):
        current = _usage_for_feature(organization, feature) or 0
        allowed = (current + quantity) <= int(limit)
        return EntitlementResult(
            allowed=allowed,
            feature=feature,
            limit=int(limit),
            current=current,
            plan_code=plan_code,
            reason="" if allowed else f"Limit aşıldı ({current}/{limit}).",
        )
    return EntitlementResult(
        allowed=True,
        feature=feature,
        limit=limit,
        plan_code=plan_code,
    )


def require_feature(organization, feature: str, *, quantity: int = 1) -> EntitlementResult:
    result = can_use(organization, feature, quantity=quantity)
    if not result.allowed:
        raise EntitlementDenied(result.reason or "Özellik kullanılamaz.", feature=feature)
    return result
