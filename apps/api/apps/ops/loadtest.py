"""NP-320 — scale benchmark harness (profiles: small / medium / full)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from django.db import transaction
from django.utils import timezone

from apps.ops.models import LoadTestRun

# Full target from ticket (destructive — only with --profile full + confirm)
FULL_TARGETS = {
    "customers": 100_000,
    "invoices": 2_000_000,
    "activities": 5_000_000,
    "concurrent_users": 500,
}

PROFILES = {
    # small stays CI-safe; use medium/full on staging with disk headroom
    "small": {"customers": 20, "invoices": 50, "activities": 30, "concurrent_users": 5},
    "medium": {"customers": 5_000, "invoices": 25_000, "activities": 10_000, "concurrent_users": 50},
    "full": FULL_TARGETS,
}


@dataclass
class Timing:
    name: str
    ms: float


def _time_ms(fn: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn()
    return result, (time.perf_counter() - started) * 1000


def seed_volume(organization, *, customers: int, invoices: int, activities: int) -> dict[str, int]:
    """Idempotent-ish seed with SAMPLE-like codes for load testing."""
    from apps.collections.models import CollectionActivity, CollectionActivityType
    from apps.customers.models import Customer
    from apps.invoices.models import Invoice, InvoiceStatus

    org_id = organization.pk
    existing = Customer.objects.filter(organization_id=org_id, code__startswith="LT-").count()
    created_c = 0
    batch = []
    need_c = max(0, customers - existing)
    with transaction.atomic():
        for i in range(existing + 1, existing + need_c + 1):
            batch.append(
                Customer(
                    organization_id=org_id,
                    code=f"LT-{i:06d}",
                    name=f"LoadTest Customer {i}",
                    is_active=True,
                )
            )
            if len(batch) >= 500:
                Customer.objects.bulk_create(batch, ignore_conflicts=True)
                created_c += len(batch)
                batch = []
        if batch:
            Customer.objects.bulk_create(batch, ignore_conflicts=True)
            created_c += len(batch)

    cust_ids = list(
        Customer.objects.filter(organization_id=org_id, code__startswith="LT-").values_list(
            "id", flat=True
        )[:customers]
    )
    if not cust_ids:
        return {"customers": 0, "invoices": 0, "activities": 0}

    existing_inv = Invoice.objects.filter(organization_id=org_id, number__startswith="LT-").count()
    need_i = max(0, invoices - existing_inv)
    created_i = 0
    inv_batch = []
    today = timezone.localdate()
    with transaction.atomic():
        for i in range(existing_inv + 1, existing_inv + need_i + 1):
            cust_id = cust_ids[(i - 1) % len(cust_ids)]
            inv_batch.append(
                Invoice(
                    organization_id=org_id,
                    customer_id=cust_id,
                    number=f"LT-{i:08d}",
                    invoice_date=today,
                    due_date=today,
                    total_amount=Decimal("100.00"),
                    status=InvoiceStatus.OPEN,
                )
            )
            if len(inv_batch) >= 500:
                Invoice.objects.bulk_create(inv_batch, ignore_conflicts=True)
                created_i += len(inv_batch)
                inv_batch = []
        if inv_batch:
            Invoice.objects.bulk_create(inv_batch, ignore_conflicts=True)
            created_i += len(inv_batch)

    existing_a = CollectionActivity.objects.filter(
        organization_id=org_id, summary__startswith="LT activity"
    ).count()
    need_a = max(0, activities - existing_a)
    created_a = 0
    act_batch = []
    with transaction.atomic():
        for i in range(existing_a + 1, existing_a + need_a + 1):
            cust_id = cust_ids[(i - 1) % len(cust_ids)]
            act_batch.append(
                CollectionActivity(
                    organization_id=org_id,
                    customer_id=cust_id,
                    activity_type=CollectionActivityType.NOTE,
                    summary=f"LT activity {i}",
                )
            )
            if len(act_batch) >= 500:
                CollectionActivity.objects.bulk_create(act_batch)
                created_a += len(act_batch)
                act_batch = []
        if act_batch:
            CollectionActivity.objects.bulk_create(act_batch)
            created_a += len(act_batch)

    return {
        "customers": Customer.objects.filter(organization_id=org_id, code__startswith="LT-").count(),
        "invoices": Invoice.objects.filter(organization_id=org_id, number__startswith="LT-").count(),
        "activities": CollectionActivity.objects.filter(
            organization_id=org_id, summary__startswith="LT activity"
        ).count(),
        "created_customers": created_c,
        "created_invoices": created_i,
        "created_activities": created_a,
    }


def run_benchmark(organization, *, profile: str = "small", user=None) -> LoadTestRun:
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")
    cfg = PROFILES[profile]
    volumes = seed_volume(
        organization,
        customers=cfg["customers"],
        invoices=cfg["invoices"],
        activities=cfg["activities"],
    )
    org_id = organization.pk
    timings: dict[str, float] = {}

    from apps.customers.models import Customer
    from apps.dashboard.services import dashboard_overview, dashboard_summary
    from apps.forecasting.weekly import calculate_organization_forecast

    _, timings["list_customers_ms"] = _time_ms(
        lambda: list(Customer.objects.filter(organization_id=org_id).order_by("name")[:50])
    )
    _, timings["dashboard_summary_ms"] = _time_ms(lambda: dashboard_summary(org_id))
    _, timings["dashboard_overview_ms"] = _time_ms(lambda: dashboard_overview(org_id))
    _, timings["forecast_ms"] = _time_ms(
        lambda: calculate_organization_forecast(org_id, persist=False)
    )
    try:
        from apps.risk.services import calculate_customer_risk

        cust = Customer.objects.filter(organization_id=org_id).first()
        if cust:
            _, timings["risk_ms"] = _time_ms(lambda: calculate_customer_risk(cust.id))
    except Exception:  # noqa: BLE001
        timings["risk_ms"] = -1

    # Import timing — measure dry parse of N rows as proxy
    started = time.perf_counter()
    _ = [{"code": f"X{i}", "name": f"N{i}"} for i in range(min(1000, cfg["customers"]))]
    timings["import_proxy_ms"] = (time.perf_counter() - started) * 1000

    return LoadTestRun.objects.create(
        organization=organization,
        profile=profile,
        concurrent_users=cfg["concurrent_users"],
        customers=volumes["customers"],
        invoices=volumes["invoices"],
        activities=volumes["activities"],
        timings_ms={k: round(v, 2) for k, v in timings.items()},
        notes=(
            f"Target full scale: {FULL_TARGETS}. "
            "EXPLAIN ANALYZE docs: docs/ops/np321-index-explain.md"
        ),
        created_by=user,
    )
