"""NP-283 — 14-day free trial, no card, read-only after expiry + progress."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.billing.models import Subscription, SubscriptionStatus
from apps.billing.subscription_service import ensure_subscription, get_active_subscription


def apply_trial_expiry(organization) -> Subscription:
    """If trial ended without conversion → read-only mode."""
    sub = ensure_subscription(organization)
    if sub.status != SubscriptionStatus.TRIALING:
        return sub
    if sub.trial_ends_at and timezone.now() >= sub.trial_ends_at:
        sub.status = SubscriptionStatus.EXPIRED
        sub.read_only = True
        sub.save(update_fields=["status", "read_only", "updated_at"])
    return sub


def is_read_only(organization) -> bool:
    sub = get_active_subscription(organization)
    if sub is None:
        sub = apply_trial_expiry(organization)
    else:
        apply_trial_expiry(organization)
        sub.refresh_from_db()
    if sub.read_only:
        return True
    if sub.status == SubscriptionStatus.EXPIRED:
        return True
    if (
        sub.status == SubscriptionStatus.PAST_DUE
        and sub.grace_ends_at
        and timezone.now() >= sub.grace_ends_at
    ):
        if not sub.read_only:
            sub.read_only = True
            sub.save(update_fields=["read_only", "updated_at"])
        return True
    return bool(sub.read_only)


def trial_progress(organization) -> dict[str, Any]:
    """
    Trial onboarding checklist shown during the free period:
    - KolayBi bağlandı
    - N müşteri aktarıldı
    - N gecikmiş fatura bulundu
    - İlk workflow oluşturuldu
    """
    org_id = organization.pk if hasattr(organization, "pk") else organization
    sub = ensure_subscription(organization)
    apply_trial_expiry(organization)
    sub.refresh_from_db()

    kolaybi = False
    try:
        from apps.integrations.models import IntegrationConnection

        kolaybi = IntegrationConnection.objects.filter(
            organization_id=org_id
        ).exists()
    except Exception:  # noqa: BLE001
        kolaybi = False

    from apps.customers.models import Customer
    from apps.invoices.models import Invoice, InvoiceStatus

    customers = Customer.objects.filter(
        organization_id=org_id, is_sample=False, is_active=True
    ).count()
    overdue = Invoice.objects.filter(
        organization_id=org_id,
        is_sample=False,
        status=InvoiceStatus.OVERDUE,
    ).count()

    workflow = False
    try:
        from apps.workflows.models import CollectionWorkflow

        workflow = CollectionWorkflow.objects.filter(organization_id=org_id).exists()
    except Exception:  # noqa: BLE001
        workflow = False

    steps = [
        {
            "key": "kolaybi_connected",
            "label": "KolayBi bağlandı",
            "done": kolaybi,
            "detail": "Bağlı" if kolaybi else "Henüz bağlanmadı",
        },
        {
            "key": "customers_imported",
            "label": f"{customers} müşteri aktarıldı" if customers else "Müşteri aktarımı",
            "done": customers > 0,
            "detail": f"{customers} müşteri",
            "count": customers,
        },
        {
            "key": "overdue_found",
            "label": (
                f"{overdue} gecikmiş fatura bulundu"
                if overdue
                else "Gecikmiş fatura taraması"
            ),
            "done": overdue > 0,
            "detail": f"{overdue} gecikmiş fatura",
            "count": overdue,
        },
        {
            "key": "first_workflow",
            "label": "İlk workflow oluşturuldu",
            "done": workflow,
            "detail": "Oluşturuldu" if workflow else "Bekleniyor",
        },
    ]
    done_count = sum(1 for s in steps if s["done"])
    days_left = None
    if sub.trial_ends_at:
        delta = sub.trial_ends_at - timezone.now()
        days_left = max(0, delta.days)

    return {
        "status": sub.status,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "days_left": days_left,
        "card_required": sub.card_required,
        "read_only": sub.read_only or sub.status == SubscriptionStatus.EXPIRED,
        "steps": steps,
        "completed_steps": done_count,
        "total_steps": len(steps),
        "progress_pct": round(100 * done_count / len(steps)) if steps else 0,
    }
