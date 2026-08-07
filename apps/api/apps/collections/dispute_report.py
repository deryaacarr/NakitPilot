"""NP-254 — dispute resolution metrics report."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.collections.models import (
    DISPUTE_ACTIVE_STATUSES,
    Dispute,
    DisputeCategory,
    DisputeStatus,
)
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization

ZERO = Decimal("0.00")


def dispute_resolution_metrics(organization) -> dict[str, Any]:
    qs = Dispute.objects.for_organization(organization)
    resolved_qs = qs.filter(
        status__in=[DisputeStatus.RESOLVED, DisputeStatus.REJECTED],
        resolved_at__isnull=False,
    )

    # Average resolution duration (hours)
    annotated = resolved_qs.annotate(
        duration=ExpressionWrapper(
            F("resolved_at") - F("opened_at"),
            output_field=DurationField(),
        )
    )
    avg_duration = annotated.aggregate(avg=Avg("duration"))["avg"]
    avg_hours = None
    if avg_duration is not None:
        avg_hours = round(avg_duration.total_seconds() / 3600, 2)

    by_category: list[dict[str, Any]] = []
    for cat in DisputeCategory:
        cat_qs = annotated.filter(category=cat.value)
        cat_avg = cat_qs.aggregate(avg=Avg("duration"))["avg"]
        cat_hours = (
            round(cat_avg.total_seconds() / 3600, 2) if cat_avg is not None else None
        )
        disputed_amt = (
            qs.filter(category=cat.value, status__in=DISPUTE_ACTIVE_STATUSES).aggregate(
                t=Coalesce(Sum("amount"), ZERO)
            )["t"]
            or ZERO
        )
        resolved_amt = (
            resolved_qs.filter(category=cat.value).aggregate(
                t=Coalesce(Sum("amount"), ZERO)
            )["t"]
            or ZERO
        )
        by_category.append(
            {
                "category": cat.value,
                "category_label": cat.label,
                "avg_resolution_hours": cat_hours,
                "active_amount": str(disputed_amt),
                "resolved_amount": str(resolved_amt),
                "resolved_count": cat_qs.count(),
            }
        )

    active_total = (
        qs.filter(status__in=DISPUTE_ACTIVE_STATUSES).aggregate(
            t=Coalesce(Sum("amount"), ZERO)
        )["t"]
        or ZERO
    )
    resolved_total = (
        resolved_qs.aggregate(t=Coalesce(Sum("amount"), ZERO))["t"] or ZERO
    )

    top_customers = list(
        qs.values("customer_id", "customer__name")
        .annotate(dispute_count=Count("id"), total_amount=Coalesce(Sum("amount"), ZERO))
        .order_by("-dispute_count", "-total_amount")[:10]
    )
    top = [
        {
            "customer_id": row["customer_id"],
            "customer_name": row["customer__name"],
            "dispute_count": row["dispute_count"],
            "total_amount": str(row["total_amount"] or ZERO),
        }
        for row in top_customers
    ]

    return {
        "avg_resolution_hours": avg_hours,
        "by_category": by_category,
        "disputed_total_amount": str(active_total),
        "resolved_total_amount": str(resolved_total),
        "active_count": qs.filter(status__in=DISPUTE_ACTIVE_STATUSES).count(),
        "resolved_count": resolved_qs.count(),
        "top_disputed_customers": top,
    }


def dispute_resolution_report_rows(organization, filters: dict | None = None) -> list[dict]:
    """Flat rows for Excel export (NP-254)."""
    metrics = dispute_resolution_metrics(organization)
    rows = [
        {
            "metric": "Ortalama çözüm süresi (saat)",
            "value": metrics["avg_resolution_hours"],
            "category": "",
            "customer": "",
        },
        {
            "metric": "İtirazlı toplam tutar",
            "value": metrics["disputed_total_amount"],
            "category": "",
            "customer": "",
        },
        {
            "metric": "Çözülen tutar",
            "value": metrics["resolved_total_amount"],
            "category": "",
            "customer": "",
        },
    ]
    for cat in metrics["by_category"]:
        rows.append(
            {
                "metric": "Kategori ortalama süre (saat)",
                "value": cat["avg_resolution_hours"],
                "category": cat["category_label"],
                "customer": "",
            }
        )
    for cust in metrics["top_disputed_customers"]:
        rows.append(
            {
                "metric": "En fazla itiraz",
                "value": cust["dispute_count"],
                "category": "",
                "customer": cust["customer_name"],
            }
        )
    return rows


class DisputeResolutionReportView(APIView):
    """GET /api/disputes/resolution-report/"""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        return Response(dispute_resolution_metrics(organization))
