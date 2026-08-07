"""NP-322 — dashboard read models (pre-aggregated)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class OrganizationDailyMetrics(TenantModel):
    day = models.DateField(db_index=True)
    open_invoice_count = models.PositiveIntegerField(default=0)
    overdue_invoice_count = models.PositiveIntegerField(default=0)
    open_balance = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    overdue_balance = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    collected_amount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    tasks_created = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "day"),
                name="uniq_org_daily_metrics_day",
            )
        ]
        indexes = [models.Index(fields=["organization", "day"])]


class CustomerBalanceSnapshot(TenantModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="balance_snapshots",
    )
    open_balance = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    overdue_balance = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    invoice_count = models.PositiveIntegerField(default=0)
    snapshot_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "snapshot_at"]),
            models.Index(fields=["organization", "customer"]),
        ]


class AgingBucketSnapshot(TenantModel):
    day = models.DateField(db_index=True)
    bucket_code = models.CharField(max_length=32)
    invoice_count = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "day", "bucket_code"),
                name="uniq_aging_bucket_day",
            )
        ]


class CollectionPerformanceSnapshot(TenantModel):
    day = models.DateField(db_index=True)
    promises_kept = models.PositiveIntegerField(default=0)
    promises_broken = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)
    collected_amount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "day"),
                name="uniq_collection_perf_day",
            )
        ]


def refresh_organization_daily_metrics(organization_id: int, day: date | None = None) -> OrganizationDailyMetrics:
    from apps.collections.models import CollectionTask, CollectionTaskStatus
    from apps.dashboard.services import aging_report, dashboard_summary
    from apps.invoices.models import Invoice, InvoiceStatus
    from apps.payments.models import Payment

    day = day or timezone.localdate()
    summary = dashboard_summary(organization_id)
    cards = summary.get("cards") or {}
    open_balance = Decimal(str(cards.get("open_receivables") or 0))
    overdue_balance = Decimal(str(cards.get("overdue_receivables") or 0))
    open_count = Invoice.objects.filter(
        organization_id=organization_id,
        status__in=[InvoiceStatus.OPEN, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID],
    ).count()
    overdue_count = Invoice.objects.filter(
        organization_id=organization_id, status=InvoiceStatus.OVERDUE
    ).count()

    from datetime import datetime, time

    from django.utils.timezone import make_aware

    day_start = make_aware(datetime.combine(day, time.min))
    day_end = day_start + timedelta(days=1)
    collected = (
        Payment.objects.filter(
            organization_id=organization_id,
            cancelled_at__isnull=True,
            paid_at__gte=day_start,
            paid_at__lt=day_end,
        ).aggregate(s=Sum("amount"))["s"]
        or ZERO
    )
    tasks_created = CollectionTask.objects.filter(
        organization_id=organization_id, created_at__gte=day_start, created_at__lt=day_end
    ).count()
    tasks_completed = CollectionTask.objects.filter(
        organization_id=organization_id,
        status=CollectionTaskStatus.COMPLETED,
        completed_at__gte=day_start,
        completed_at__lt=day_end,
    ).count()

    obj, _ = OrganizationDailyMetrics.objects.update_or_create(
        organization_id=organization_id,
        day=day,
        defaults={
            "open_invoice_count": open_count,
            "overdue_invoice_count": overdue_count,
            "open_balance": open_balance,
            "overdue_balance": overdue_balance,
            "collected_amount": collected,
            "tasks_created": tasks_created,
            "tasks_completed": tasks_completed,
        },
    )

    # Aging buckets
    try:
        aging = aging_report(organization_id)
        buckets = aging.get("groups") or aging.get("buckets") or aging.get("results") or []
        for b in buckets:
            code = b.get("code") or b.get("bucket") or "unknown"
            AgingBucketSnapshot.objects.update_or_create(
                organization_id=organization_id,
                day=day,
                bucket_code=str(code)[:32],
                defaults={
                    "invoice_count": int(b.get("invoice_count") or b.get("count") or 0),
                    "amount": Decimal(str(b.get("open_amount") or b.get("amount") or 0)),
                },
            )
    except Exception:  # noqa: BLE001
        pass

    return obj


def read_model_overview(organization_id: int) -> dict[str, Any] | None:
    """Return cached read-model payload if fresh (< 15 min), else None."""
    day = timezone.localdate()
    metrics = OrganizationDailyMetrics.objects.filter(
        organization_id=organization_id, day=day
    ).first()
    if metrics is None:
        return None
    if timezone.now() - metrics.updated_at > timedelta(minutes=15):
        return None
    aging = list(
        AgingBucketSnapshot.objects.filter(organization_id=organization_id, day=day).values(
            "bucket_code", "invoice_count", "amount"
        )
    )
    return {
        "source": "read_model",
        "day": day.isoformat(),
        "open_invoice_count": metrics.open_invoice_count,
        "overdue_invoice_count": metrics.overdue_invoice_count,
        "open_balance": str(metrics.open_balance),
        "overdue_balance": str(metrics.overdue_balance),
        "collected_amount": str(metrics.collected_amount),
        "tasks_created": metrics.tasks_created,
        "tasks_completed": metrics.tasks_completed,
        "aging": [
            {
                "code": a["bucket_code"],
                "count": a["invoice_count"],
                "amount": str(a["amount"]),
            }
            for a in aging
        ],
        "updated_at": metrics.updated_at.isoformat(),
    }
