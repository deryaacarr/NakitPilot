"""NP-360 — super-admin overview (no customer PII by default)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from apps.organizations.models import Membership, Organization

User = get_user_model()
ZERO = Decimal("0.00")


def build_platform_overview(*, include_customer_data: bool = False) -> dict[str, Any]:
    """
    Aggregate platform metrics.

    Customer debtor data (names, phones, invoice lines) is intentionally omitted
    unless include_customer_data=True (explicit elevated request — still no PII
    dump of all customers; only counts).
    """
    now = timezone.now()

    orgs = list(
        Organization.objects.annotate(
            user_count=Count("memberships", distinct=True),
        )
        .order_by("-created_at")[:100]
        .values("id", "name", "slug", "user_count", "created_at", "is_active")
    )

    # Normalize org rows without customer fields
    organizations = [
        {
            "id": o["id"],
            "name": o["name"],
            "slug": o.get("slug") or "",
            "user_count": o.get("user_count") or 0,
            "created_at": o["created_at"].isoformat() if o.get("created_at") else None,
        }
        for o in orgs
    ]

    total_users = User.objects.filter(is_active=True).count()
    total_memberships = Membership.objects.filter(is_active=True).count()

    plans: list[dict[str, Any]] = []
    subscriptions: list[dict[str, Any]] = []
    try:
        from apps.billing.models import Subscription, SubscriptionPlan

        plans = list(
            SubscriptionPlan.objects.annotate(sub_count=Count("subscriptions")).values(
                "id", "code", "name", "sub_count"
            )
        )
        subscriptions = list(
            Subscription.objects.select_related("plan", "organization")
            .order_by("-updated_at")[:50]
            .values(
                "id",
                "status",
                "organization_id",
                "organization__name",
                "plan__code",
                "trial_ends_at",
                "current_period_end",
            )
        )
        subscriptions = [
            {
                "id": s["id"],
                "status": s["status"],
                "organization_id": s["organization_id"],
                "organization_name": s["organization__name"],
                "plan_code": s["plan__code"],
                "trial_ends_at": s["trial_ends_at"].isoformat()
                if s.get("trial_ends_at")
                else None,
                "current_period_end": s["current_period_end"].isoformat()
                if s.get("current_period_end")
                else None,
            }
            for s in subscriptions
        ]
    except Exception:
        pass

    integrations: list[dict[str, Any]] = []
    try:
        from apps.integrations.models import IntegrationConnection

        integrations = list(
            IntegrationConnection.objects.values("status").annotate(count=Count("id"))
        )
        recent_errors = list(
            IntegrationConnection.objects.exclude(last_error="")
            .order_by("-updated_at")[:20]
            .values("id", "organization_id", "provider", "status", "last_error", "updated_at")
        )
        last_errors = [
            {
                "source": "integration",
                "id": e["id"],
                "organization_id": e["organization_id"],
                "provider": e.get("provider") or "",
                "status": e["status"],
                "message": (e["last_error"] or "")[:240],
                "at": e["updated_at"].isoformat() if e.get("updated_at") else None,
            }
            for e in recent_errors
        ]
    except Exception:
        integrations = []
        last_errors = []

    try:
        from apps.ops.models import AlertEvent

        for ev in AlertEvent.objects.select_related("rule").order_by("-created_at")[:15]:
            last_errors.append(
                {
                    "source": "ops_alert",
                    "id": ev.id,
                    "organization_id": ev.organization_id,
                    "provider": getattr(ev.rule, "name", None) or f"rule:{ev.rule_id}",
                    "status": "active" if ev.is_active else "resolved",
                    "message": (ev.message or "")[:240],
                    "at": ev.created_at.isoformat() if ev.created_at else None,
                }
            )
    except Exception:
        pass

    support_tickets: list[dict[str, Any]] = []
    try:
        from apps.platform.models import SupportTicket

        support_tickets = list(
            SupportTicket.objects.select_related("organization")
            .order_by("-created_at")[:30]
            .values(
                "id",
                "subject",
                "status",
                "organization_id",
                "organization__name",
                "created_at",
            )
        )
        support_tickets = [
            {
                "id": t["id"],
                "subject": t["subject"],
                "status": t["status"],
                "organization_id": t["organization_id"],
                "organization_name": t["organization__name"],
                "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
            }
            for t in support_tickets
        ]
    except Exception:
        pass

    ai_cost = {"estimated_cost_total": "0.00", "events": 0}
    try:
        from apps.ai_usage.models import AIUsageEvent

        agg = AIUsageEvent.objects.aggregate(
            cost=Sum("estimated_cost"),
            events=Count("id"),
        )
        ai_cost = {
            "estimated_cost_total": str(agg["cost"] or ZERO),
            "events": agg["events"] or 0,
        }
    except Exception:
        pass

    storage = {"file_storage_bytes": 0, "note": "usage gauge / import sizes"}
    try:
        from apps.billing.models import UsageMetric, UsageRecord

        total = (
            UsageRecord.objects.filter(metric=UsageMetric.FILE_STORAGE_BYTES).aggregate(
                total=Sum("quantity")
            )["total"]
            or 0
        )
        storage["file_storage_bytes"] = int(total)
    except Exception:
        try:
            from apps.imports.models import ImportJob

            total = ImportJob.objects.aggregate(total=Sum("file_size"))["total"] or 0
            storage["file_storage_bytes"] = int(total)
            storage["note"] = "sum of import job file_size"
        except Exception:
            pass

    payload: dict[str, Any] = {
        "as_of": now.isoformat(),
        "privacy": {
            "customer_data_included": False,
            "note": (
                "Super admin paneli varsayılan olarak müşteri (borçlu) verisi göstermez."
            ),
        },
        "totals": {
            "organizations": Organization.objects.count(),
            "active_users": total_users,
            "active_memberships": total_memberships,
        },
        "organizations": organizations,
        "plans": plans,
        "subscriptions": subscriptions,
        "integrations": {"by_status": integrations},
        "last_errors": last_errors[:30],
        "support_tickets": support_tickets,
        "ai_cost": ai_cost,
        "storage": storage,
    }

    if include_customer_data:
        # Still only aggregate counts — never dump customer PII rows.
        try:
            from apps.customers.models import Customer
            from apps.invoices.models import Invoice

            payload["privacy"]["customer_data_included"] = True
            payload["customer_aggregates"] = {
                "customer_count": Customer.objects.count(),
                "invoice_count": Invoice.objects.count(),
            }
        except Exception:
            payload["customer_aggregates"] = {}

    return payload
