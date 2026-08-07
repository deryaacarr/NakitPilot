"""NP-282 — usage metering (record + summary)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from django.db.models import F, Sum
from django.utils import timezone

from apps.billing.models import UsageMetric, UsageRecord
from apps.billing.subscription_service import ensure_subscription, get_entitlements


def _month_bounds(when: date | None = None) -> tuple[date, date]:
    d = when or timezone.localdate()
    last = monthrange(d.year, d.month)[1]
    return date(d.year, d.month, 1), date(d.year, d.month, last)


def record_usage(
    organization,
    metric: str,
    quantity: int = 1,
    *,
    replace: bool = False,
) -> UsageRecord:
    """Increment (or replace) a metered quantity for the current billing month."""
    if quantity < 0:
        raise ValueError("quantity must be >= 0")
    org_id = organization.pk if hasattr(organization, "pk") else organization
    sub = ensure_subscription(organization)
    start, end = _month_bounds()
    record, created = UsageRecord.objects.get_or_create(
        organization_id=org_id,
        subscription=sub,
        metric=metric,
        period_start=start,
        period_end=end,
        defaults={"quantity": quantity if replace else quantity},
    )
    if not created:
        if replace:
            record.quantity = quantity
        else:
            UsageRecord.objects.filter(pk=record.pk).update(quantity=F("quantity") + quantity)
            record.refresh_from_db()
        record.save(update_fields=["updated_at"])
    return record


def get_metric_total(organization, metric: str, *, when: date | None = None) -> int:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    start, end = _month_bounds(when)
    total = (
        UsageRecord.objects.filter(
            organization_id=org_id,
            metric=metric,
            period_start=start,
            period_end=end,
        ).aggregate(s=Sum("quantity"))["s"]
        or 0
    )
    return int(total)


def sync_live_gauges(organization) -> dict[str, int]:
    """Refresh gauges that are derived from live tables (customers, storage)."""
    org_id = organization.pk if hasattr(organization, "pk") else organization
    from apps.customers.models import Customer

    active = Customer.objects.filter(
        organization_id=org_id, is_active=True, is_sample=False
    ).count()
    record_usage(organization, UsageMetric.ACTIVE_CUSTOMERS, active, replace=True)

    storage = get_metric_total(organization, UsageMetric.FILE_STORAGE_BYTES)
    return {
        UsageMetric.ACTIVE_CUSTOMERS: active,
        UsageMetric.FILE_STORAGE_BYTES: storage,
    }


def meter_integration_sync(organization, *, invoices_processed: int = 0) -> None:
    """NP-282 — count a sync run (+ optional monthly invoice processing)."""
    try:
        record_usage(organization, UsageMetric.INTEGRATION_SYNCS, 1)
        if invoices_processed > 0:
            record_usage(organization, UsageMetric.MONTHLY_INVOICES, invoices_processed)
    except Exception:  # noqa: BLE001
        pass


def usage_summary(organization) -> dict[str, Any]:
    """NP-282 usage dashboard payload with plan limits where applicable."""
    sync_live_gauges(organization)
    ents = get_entitlements(organization)
    start, end = _month_bounds()
    metrics = {m.value: get_metric_total(organization, m.value) for m in UsageMetric}
    limits = {
        UsageMetric.ACTIVE_CUSTOMERS: ents.get("max_customers"),
        UsageMetric.MONTHLY_INVOICES: ents.get("monthly_invoice_syncs"),
        UsageMetric.AI_TOKENS: ents.get("ai_monthly_tokens"),
        UsageMetric.INTEGRATION_SYNCS: ents.get("max_integrations"),
    }
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "metrics": metrics,
        "limits": {k: limits.get(k) for k in metrics},
        "labels": {m.value: m.label for m in UsageMetric},
    }
