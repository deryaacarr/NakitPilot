"""NP-291 — örnek veri modu (clearly separated from real data)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers.models import Customer, CustomerSource, RiskStatus
from apps.invoices.models import Invoice, InvoiceSource, InvoiceStatus
from apps.onboarding.progress import ensure_state

SAMPLE_PREFIX = "[ÖRNEK] "


@transaction.atomic
def enable_sample_data(organization) -> dict[str, Any]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    state = ensure_state(organization)
    if state.sample_data_enabled and Customer.objects.filter(
        organization_id=org_id, is_sample=True
    ).exists():
        return sample_summary(organization)

    customers = []
    for i in range(1, 21):
        c = Customer.objects.create(
            organization_id=org_id,
            code=f"SAMPLE-{i:03d}",
            name=f"{SAMPLE_PREFIX}Müşteri {i}",
            email=f"ornek{i}@example.invalid",
            phone=f"+90555{i:07d}"[:16],
            city="İstanbul",
            sector="Örnek",
            risk_status=RiskStatus.MEDIUM if i % 3 == 0 else RiskStatus.LOW,
            risk_score=40 + (i % 50),
            source=CustomerSource.SAMPLE,
            is_sample=True,
            notes="Örnek veri — gerçek cari değildir.",
            tags=["sample_data", "ornek"],
        )
        customers.append(c)

    today = timezone.localdate()
    invoices = []
    for i in range(1, 51):
        cust = customers[(i - 1) % len(customers)]
        overdue = i % 4 == 0
        inv = Invoice.objects.create(
            organization_id=org_id,
            customer=cust,
            number=f"SAMPLE-INV-{i:04d}",
            invoice_date=today - timedelta(days=45 + i),
            due_date=today - timedelta(days=10) if overdue else today + timedelta(days=15 + i % 20),
            currency="TRY",
            subtotal_amount=Decimal("1000.00") + i,
            tax_amount=Decimal("180.00"),
            total_amount=Decimal("1180.00") + i,
            status=InvoiceStatus.OVERDUE if overdue else InvoiceStatus.OPEN,
            description="Örnek fatura",
            notes="Örnek veri — gerçek alacak değildir.",
            source=InvoiceSource.SAMPLE,
            is_sample=True,
        )
        invoices.append(inv)

    promises = 0
    tasks = 0
    try:
        from apps.collections.models import (
            CollectionTask,
            CollectionTaskPriority,
            CollectionTaskSource,
            CollectionTaskStatus,
            CollectionTaskType,
            PaymentPromise,
            PaymentPromiseStatus,
        )

        for i, cust in enumerate(customers[:8], start=1):
            PaymentPromise.objects.create(
                organization_id=org_id,
                customer=cust,
                amount=Decimal("500.00") * i,
                promised_date=today + timedelta(days=i),
                status=PaymentPromiseStatus.PENDING,
                notes="Örnek ödeme sözü",
            )
            promises += 1

        for i, inv in enumerate(invoices[:10], start=1):
            CollectionTask.objects.create(
                organization_id=org_id,
                customer=inv.customer,
                invoice=inv,
                title=f"{SAMPLE_PREFIX}Tahsilat görevi {i}",
                description="Örnek tahsilat görevi",
                task_type=CollectionTaskType.CALL,
                status=CollectionTaskStatus.OPEN,
                priority=CollectionTaskPriority.MEDIUM,
                source=CollectionTaskSource.MANUAL,
                due_date=today + timedelta(days=i),
            )
            tasks += 1
    except Exception:  # noqa: BLE001
        pass

    state.sample_data_enabled = True
    state.save(update_fields=["sample_data_enabled", "updated_at"])
    return {
        "enabled": True,
        "customers": len(customers),
        "invoices": len(invoices),
        "promises": promises,
        "tasks": tasks,
        "label": SAMPLE_PREFIX.strip(),
        "note": "Örnek veri gerçek kayıtlardan is_sample=true ve [ÖRNEK] öneki ile ayrılır.",
    }


@transaction.atomic
def disable_sample_data(organization) -> dict[str, Any]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    try:
        from apps.collections.models import CollectionTask, PaymentPromise

        PaymentPromise.objects.filter(
            organization_id=org_id, customer__is_sample=True
        ).delete()
        CollectionTask.objects.filter(
            organization_id=org_id, customer__is_sample=True
        ).delete()
    except Exception:  # noqa: BLE001
        pass
    Invoice.objects.filter(organization_id=org_id, is_sample=True).delete()
    Customer.objects.filter(organization_id=org_id, is_sample=True).delete()
    state = ensure_state(organization)
    state.sample_data_enabled = False
    state.save(update_fields=["sample_data_enabled", "updated_at"])
    return {"enabled": False, "removed": True}


def sample_summary(organization) -> dict[str, Any]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    state = ensure_state(organization)
    return {
        "enabled": state.sample_data_enabled,
        "customers": Customer.objects.filter(organization_id=org_id, is_sample=True).count(),
        "invoices": Invoice.objects.filter(organization_id=org_id, is_sample=True).count(),
        "label": SAMPLE_PREFIX.strip(),
        "note": "Örnek veri gerçek kayıtlardan is_sample=true ve [ÖRNEK] öneki ile ayrılır.",
    }
