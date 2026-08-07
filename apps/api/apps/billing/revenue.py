"""NP-286 — admin revenue metrics (MRR, ARR, churn, …)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.billing.models import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PlanCode,
    Subscription,
    SubscriptionStatus,
)


def revenue_metrics() -> dict[str, Any]:
    now = timezone.now()
    month_ago = now - timedelta(days=30)

    active = Subscription.objects.filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]
    ).select_related("plan")
    trialing = Subscription.objects.filter(status=SubscriptionStatus.TRIALING).count()

    mrr = Decimal("0.00")
    plan_dist: dict[str, int] = {c: 0 for c in PlanCode.values}
    for sub in active:
        mrr += sub.plan.price_monthly or Decimal("0")
        plan_dist[sub.plan.code] = plan_dist.get(sub.plan.code, 0) + 1

    active_count = active.count()
    arr = mrr * 12

    # Conversion: trials that became ACTIVE in last 90d vs trials started
    window = now - timedelta(days=90)
    trials_started = Subscription.objects.filter(created_at__gte=window).count()
    converted = Subscription.objects.filter(
        status=SubscriptionStatus.ACTIVE,
        created_at__gte=window,
        trial_ends_at__isnull=True,
    ).count()
    # Also count ACTIVE that had a trial
    converted_alt = Subscription.objects.filter(
        status=SubscriptionStatus.ACTIVE,
        updated_at__gte=window,
    ).exclude(trial_ends_at__isnull=False, status=SubscriptionStatus.TRIALING).count()
    conversion_rate = (
        round(100.0 * converted / trials_started, 2) if trials_started else 0.0
    )

    cancelled_30 = Subscription.objects.filter(
        status=SubscriptionStatus.CANCELLED,
        cancelled_at__gte=month_ago,
    ).count()
    base = active_count + cancelled_30
    churn = round(100.0 * cancelled_30 / base, 2) if base else 0.0

    arpu = (mrr / active_count) if active_count else Decimal("0.00")

    failed_payments = PaymentAttempt.objects.filter(
        status=PaymentAttemptStatus.FAILED,
        attempted_at__gte=month_ago,
    ).count()

    return {
        "mrr": str(mrr.quantize(Decimal("0.01"))),
        "arr": str(arr.quantize(Decimal("0.01"))),
        "active_subscriptions": active_count,
        "trial_users": trialing,
        "conversion_rate": conversion_rate,
        "churn": churn,
        "arpu": str(Decimal(arpu).quantize(Decimal("0.01"))),
        "failed_payments": failed_payments,
        "plan_distribution": plan_dist,
        "as_of": now.isoformat(),
        "_meta": {"converted_sample": converted_alt},
    }
