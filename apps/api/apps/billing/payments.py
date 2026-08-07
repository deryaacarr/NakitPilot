"""NP-284 — payment provider flow (mock) + dunning."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.billing.models import (
    BillingInvoice,
    BillingInvoiceStatus,
    PaymentAttempt,
    PaymentAttemptStatus,
    PlanCode,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from apps.billing.subscription_service import ensure_default_plans, ensure_subscription

PROVIDER = "mockpay"
WEBHOOK_SECRET = getattr(settings, "BILLING_WEBHOOK_SECRET", "nakitpilot-billing-dev-secret")

# Dunning: attempt 0 (immediate) → +3d → +7d → grace → read-only
DUNNING_RETRY_DAYS = (0, 3, 7)
GRACE_DAYS = 3


class PaymentError(Exception):
    def __init__(self, message: str, code: str = "payment_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _invoice_number(org_id: int) -> str:
    return f"NP-{org_id}-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def sign_payload(body: str) -> str:
    return hmac.new(
        WEBHOOK_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(body: str, signature: str) -> bool:
    expected = sign_payload(body)
    return hmac.compare_digest(expected, signature or "")


@transaction.atomic
def start_checkout(
    organization,
    *,
    plan_code: str,
    payment_token: str = "",
) -> dict[str, Any]:
    """
    Paket seç → ödeme oturumu oluştur (fatura + pending attempt).
    Webhook doğrulaması sonrası abonelik aktifleşir.
    """
    ensure_default_plans()
    code = (plan_code or "").strip().upper()
    if code not in PlanCode.values:
        raise PaymentError("Geçersiz paket.", code="invalid_plan")
    plan = SubscriptionPlan.objects.get(code=code)
    sub = ensure_subscription(organization)
    org_id = organization.pk if hasattr(organization, "pk") else organization

    amount = plan.price_monthly
    inv = BillingInvoice.objects.create(
        organization_id=org_id,
        subscription=sub,
        number=_invoice_number(org_id),
        status=BillingInvoiceStatus.OPEN,
        subtotal=amount,
        tax=Decimal("0.00"),
        total=amount,
        currency="TRY",
        period_start=timezone.localdate(),
        period_end=(timezone.now() + timedelta(days=30)).date(),
        due_date=timezone.localdate(),
        line_items=[
            {
                "description": f"{plan.name} aylık abonelik",
                "quantity": 1,
                "unit_price": str(amount),
                "plan_code": plan.code,
            }
        ],
    )
    ref = f"chk_{uuid.uuid4().hex}"
    attempt = PaymentAttempt.objects.create(
        organization_id=org_id,
        billing_invoice=inv,
        amount=amount,
        status=PaymentAttemptStatus.PENDING,
        provider=PROVIDER,
        provider_reference=ref,
    )
    # Dev convenience: token "fail" forces failure path without webhook
    if payment_token == "fail":
        return handle_payment_failure(attempt)

    return {
        "checkout_id": ref,
        "invoice_id": inv.id,
        "invoice_number": inv.number,
        "amount": str(amount),
        "currency": "TRY",
        "plan_code": plan.code,
        "provider": PROVIDER,
        "status": "pending",
        "client_secret": sign_payload(ref),
    }


@transaction.atomic
def activate_from_payment(attempt: PaymentAttempt, *, plan_code: str | None = None) -> Subscription:
    inv = attempt.billing_invoice
    sub = inv.subscription
    if plan_code:
        ensure_default_plans()
        sub.plan = SubscriptionPlan.objects.get(code=plan_code)
    now = timezone.now()
    attempt.status = PaymentAttemptStatus.SUCCEEDED
    attempt.save(update_fields=["status"])
    inv.status = BillingInvoiceStatus.PAID
    inv.paid_at = now
    inv.save(update_fields=["status", "paid_at"])

    sub.status = SubscriptionStatus.ACTIVE
    sub.read_only = False
    sub.dunning_step = 0
    sub.next_retry_at = None
    sub.grace_ends_at = None
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)
    sub.trial_ends_at = None
    sub.payment_provider = PROVIDER
    sub.save(
        update_fields=[
            "plan",
            "status",
            "read_only",
            "dunning_step",
            "next_retry_at",
            "grace_ends_at",
            "current_period_start",
            "current_period_end",
            "trial_ends_at",
            "payment_provider",
            "updated_at",
        ]
    )
    return sub


def handle_payment_failure(attempt: PaymentAttempt) -> dict[str, Any]:
    """NP-284 dunning: 1st try → +3d → +7d → grace → read-only."""
    attempt.status = PaymentAttemptStatus.FAILED
    attempt.error_message = attempt.error_message or "Ödeme başarısız"
    attempt.save(update_fields=["status", "error_message"])

    sub = attempt.billing_invoice.subscription
    sub.status = SubscriptionStatus.PAST_DUE
    # dunning_step: 1 = first failure, 2 = after +3d retry, 3 = after +7d → grace
    sub.dunning_step = min(int(sub.dunning_step or 0) + 1, 3)
    if sub.dunning_step == 1:
        sub.next_retry_at = timezone.now() + timedelta(days=3)
        sub.grace_ends_at = None
        sub.read_only = False
    elif sub.dunning_step == 2:
        sub.next_retry_at = timezone.now() + timedelta(days=7)
        sub.grace_ends_at = None
        sub.read_only = False
    else:
        sub.next_retry_at = None
        if not sub.grace_ends_at:
            sub.grace_ends_at = timezone.now() + timedelta(days=GRACE_DAYS)
        sub.read_only = timezone.now() >= sub.grace_ends_at
    sub.save(
        update_fields=[
            "status",
            "dunning_step",
            "next_retry_at",
            "grace_ends_at",
            "read_only",
            "updated_at",
        ]
    )
    return {
        "status": "failed",
        "dunning_step": sub.dunning_step,
        "next_retry_at": sub.next_retry_at.isoformat() if sub.next_retry_at else None,
        "grace_ends_at": sub.grace_ends_at.isoformat() if sub.grace_ends_at else None,
        "read_only": sub.read_only,
        "invoice_id": attempt.billing_invoice_id,
    }


@transaction.atomic
def process_webhook(
    *,
    event: str,
    checkout_id: str,
    plan_code: str = "",
    raw_body: str = "",
    signature: str = "",
) -> dict[str, Any]:
    if raw_body and signature and not verify_signature(raw_body, signature):
        raise PaymentError("Webhook imzası geçersiz.", code="invalid_signature")

    attempt = (
        PaymentAttempt.objects.select_related("billing_invoice", "billing_invoice__subscription")
        .filter(provider_reference=checkout_id, provider=PROVIDER)
        .first()
    )
    if attempt is None:
        raise PaymentError("Ödeme oturumu bulunamadı.", code="not_found")

    if event in ("payment.succeeded", "checkout.completed"):
        code = (plan_code or "").strip().upper()
        if not code:
            items = attempt.billing_invoice.line_items or []
            for item in items:
                if item.get("plan_code"):
                    code = str(item["plan_code"]).upper()
                    break
        if not code:
            code = attempt.billing_invoice.subscription.plan.code
        sub = activate_from_payment(attempt, plan_code=code)
        return {
            "status": "activated",
            "subscription_id": sub.id,
            "plan_code": sub.plan.code,
            "invoice_id": attempt.billing_invoice_id,
            "invoice_number": attempt.billing_invoice.number,
        }

    if event in ("payment.failed", "checkout.failed"):
        return handle_payment_failure(attempt)

    raise PaymentError(f"Desteklenmeyen olay: {event}", code="unknown_event")


def process_due_retries() -> int:
    """Cron helper: retry PAST_DUE subscriptions whose next_retry_at has passed."""
    now = timezone.now()
    count = 0
    qs = Subscription.objects.filter(
        status=SubscriptionStatus.PAST_DUE,
        next_retry_at__lte=now,
        read_only=False,
    ).select_related("plan")
    for sub in qs:
        org = sub.organization
        result = start_checkout(org, plan_code=sub.plan.code, payment_token="")
        # Auto-fail in mock unless a real webhook arrives — mark for webhook
        # Create a synthetic failure if still pending after scheduling
        ref = result.get("checkout_id")
        if ref:
            attempt = PaymentAttempt.objects.filter(provider_reference=ref).first()
            if attempt and attempt.status == PaymentAttemptStatus.PENDING:
                # Leave pending for webhook; bump next_retry if still at same step
                pass
        count += 1
    # Also enforce grace → read-only
    for sub in Subscription.objects.filter(
        status=SubscriptionStatus.PAST_DUE,
        grace_ends_at__lte=now,
        read_only=False,
    ):
        sub.read_only = True
        sub.save(update_fields=["read_only", "updated_at"])
        count += 1
    return count


def update_payment_method(
    organization,
    *,
    brand: str,
    last4: str,
    provider_customer_id: str = "",
) -> Subscription:
    sub = ensure_subscription(organization)
    sub.payment_method_brand = (brand or "")[:32]
    sub.payment_method_last4 = (last4 or "")[:4]
    sub.payment_provider = PROVIDER
    if provider_customer_id:
        sub.payment_provider_customer_id = provider_customer_id[:128]
    sub.save(
        update_fields=[
            "payment_method_brand",
            "payment_method_last4",
            "payment_provider",
            "payment_provider_customer_id",
            "updated_at",
        ]
    )
    return sub


def schedule_downgrade(organization, plan_code: str) -> Subscription:
    ensure_default_plans()
    code = plan_code.strip().upper()
    plan = SubscriptionPlan.objects.get(code=code)
    sub = ensure_subscription(organization)
    if plan.sort_order >= sub.plan.sort_order and plan.price_monthly >= sub.plan.price_monthly:
        raise PaymentError("Düşürme için daha düşük bir paket seçin.", code="not_downgrade")
    sub.scheduled_plan = plan
    sub.scheduled_plan_at = sub.current_period_end or (timezone.now() + timedelta(days=30))
    sub.save(update_fields=["scheduled_plan", "scheduled_plan_at", "updated_at"])
    return sub


def cancel_subscription(organization, *, at_period_end: bool = True) -> Subscription:
    sub = ensure_subscription(organization)
    if at_period_end:
        sub.cancel_at_period_end = True
        sub.save(update_fields=["cancel_at_period_end", "updated_at"])
    else:
        sub.status = SubscriptionStatus.CANCELLED
        sub.cancelled_at = timezone.now()
        sub.cancel_at_period_end = False
        sub.read_only = True
        sub.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancel_at_period_end",
                "read_only",
                "updated_at",
            ]
        )
    return sub


def invoice_download_payload(invoice: BillingInvoice) -> dict[str, Any]:
    return {
        "id": invoice.id,
        "number": invoice.number,
        "status": invoice.status,
        "total": str(invoice.total),
        "currency": invoice.currency,
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "line_items": invoice.line_items,
        "pdf_available": bool(invoice.pdf_path),
    }
