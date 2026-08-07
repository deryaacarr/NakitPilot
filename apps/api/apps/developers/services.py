"""Developer portal aggregates (NP-206)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.api_keys.models import ApiRequestLog
from apps.webhooks.models import WebhookDelivery, WebhookDeliveryStatus


def usage_series(*, organization, days: int = 14) -> dict:
    days = max(1, min(int(days), 90))
    since = timezone.now() - timedelta(days=days)
    rows = (
        ApiRequestLog.objects.filter(organization=organization, created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"), errors=Count("id", filter=Q(status_code__gte=400)))
        .order_by("day")
    )
    by_day = {
        r["day"].isoformat(): {"total": r["total"], "errors": r["errors"]}
        for r in rows
        if r["day"]
    }
    series = []
    for i in range(days - 1, -1, -1):
        d = (timezone.localdate() - timedelta(days=i)).isoformat()
        bucket = by_day.get(d, {"total": 0, "errors": 0})
        series.append({"date": d, "total": bucket["total"], "errors": bucket["errors"]})

    totals = ApiRequestLog.objects.filter(
        organization=organization, created_at__gte=since
    ).aggregate(
        total=Count("id"),
        errors=Count("id", filter=Q(status_code__gte=400)),
        success=Count("id", filter=Q(status_code__lt=400)),
    )
    return {
        "days": days,
        "series": series,
        "totals": {
            "total": totals["total"] or 0,
            "success": totals["success"] or 0,
            "errors": totals["errors"] or 0,
        },
    }


def recent_errors(*, organization, limit: int = 25) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    api_errors = list(
        ApiRequestLog.objects.filter(organization=organization, status_code__gte=400)
        .select_related("api_key")
        .order_by("-created_at")[:limit]
    )
    webhook_errors = list(
        WebhookDelivery.objects.filter(
            organization=organization,
            status__in=[WebhookDeliveryStatus.FAILED, WebhookDeliveryStatus.EXHAUSTED],
        )
        .select_related("endpoint")
        .order_by("-updated_at")[:limit]
    )

    items: list[dict] = []
    for row in api_errors:
        items.append(
            {
                "source": "api",
                "id": row.id,
                "at": row.created_at,
                "title": f"{row.method} {row.path}",
                "detail": row.error_detail or f"HTTP {row.status_code}",
                "status_code": row.status_code,
                "api_key_prefix": row.api_key.display_prefix if row.api_key_id else "",
            }
        )
    for row in webhook_errors:
        items.append(
            {
                "source": "webhook",
                "id": row.id,
                "at": row.updated_at,
                "title": f"{row.event_type} → {row.endpoint.name}",
                "detail": row.last_error or row.status,
                "status_code": None,
                "delivery_public_id": str(row.public_id),
            }
        )
    items.sort(key=lambda x: x["at"], reverse=True)
    return items[:limit]
