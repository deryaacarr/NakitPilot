"""NP-244 / NP-252 — communication frequency + disputed-invoice protection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.collections.models import DISPUTE_ACTIVE_STATUSES, Dispute
from apps.customers.metrics import invoice_has_active_dispute
from apps.customers.models import Customer
from apps.messaging.models import (
    OutboundEmail,
    OutboundEmailStatus,
    OutboundWhatsApp,
    WhatsAppMessageStatus,
)
from apps.messaging.services import MessagingError

MAX_AUTO_PER_24H = 1
MAX_MESSAGES_PER_7D = 3

_EMAIL_SENT = {
    OutboundEmailStatus.QUEUED,
    OutboundEmailStatus.SENDING,
    OutboundEmailStatus.SENT,
    OutboundEmailStatus.DELIVERED,
    OutboundEmailStatus.OPENED,
    OutboundEmailStatus.CLICKED,
}
_WA_SENT = {
    WhatsAppMessageStatus.QUEUED,
    WhatsAppMessageStatus.SENDING,
    WhatsAppMessageStatus.SENT,
    WhatsAppMessageStatus.DELIVERED,
    WhatsAppMessageStatus.READ,
}


@dataclass
class FrequencyCheckResult:
    allowed: bool
    reason: str = ""
    code: str = ""
    auto_last_24h: int = 0
    messages_last_7d: int = 0
    open_dispute: bool = False
    invoice_disputed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "code": self.code,
            "auto_last_24h": self.auto_last_24h,
            "messages_last_7d": self.messages_last_7d,
            "open_dispute": self.open_dispute,
            "invoice_disputed": self.invoice_disputed,
            "limits": {
                "max_auto_per_24h": MAX_AUTO_PER_24H,
                "max_messages_per_7d": MAX_MESSAGES_PER_7D,
            },
        }


def customer_has_open_dispute(customer: Customer) -> bool:
    return Dispute.objects.filter(
        organization_id=customer.organization_id,
        customer_id=customer.id,
        status__in=DISPUTE_ACTIVE_STATUSES,
    ).exists()


def _count_auto_24h(customer: Customer) -> int:
    since = timezone.now() - timedelta(hours=24)
    wa = OutboundWhatsApp.objects.filter(
        organization_id=customer.organization_id,
        customer_id=customer.id,
        is_automatic=True,
        status__in=_WA_SENT,
    ).filter(Q(sent_at__gte=since) | Q(sent_at__isnull=True, queued_at__gte=since)).count()
    email = OutboundEmail.objects.filter(
        organization_id=customer.organization_id,
        customer_id=customer.id,
        status__in=_EMAIL_SENT,
        sent_at__gte=since,
    ).count()
    return wa + email


def _count_messages_7d(customer: Customer) -> int:
    since = timezone.now() - timedelta(days=7)
    wa = OutboundWhatsApp.objects.filter(
        organization_id=customer.organization_id,
        customer_id=customer.id,
        status__in=_WA_SENT,
        sent_at__gte=since,
    ).count()
    email = OutboundEmail.objects.filter(
        organization_id=customer.organization_id,
        customer_id=customer.id,
        status__in=_EMAIL_SENT,
        sent_at__gte=since,
    ).count()
    return wa + email


def check_frequency(
    customer: Customer,
    *,
    is_automatic: bool = True,
    invoice_id: int | None = None,
) -> FrequencyCheckResult:
    """NP-244 frequency + NP-252 disputed invoice gate for automatic messages."""
    open_dispute = customer_has_open_dispute(customer)
    invoice_disputed = invoice_has_active_dispute(
        organization_id=customer.organization_id,
        invoice_id=invoice_id,
    )
    auto_24h = _count_auto_24h(customer)
    msg_7d = _count_messages_7d(customer)

    # NP-252: disputed invoice must not receive automatic collection messages
    if is_automatic and invoice_disputed:
        return FrequencyCheckResult(
            allowed=False,
            reason="İtirazlı fatura otomatik tahsilat mesajı alamaz.",
            code="invoice_disputed",
            auto_last_24h=auto_24h,
            messages_last_7d=msg_7d,
            open_dispute=open_dispute,
            invoice_disputed=True,
        )

    if open_dispute and is_automatic and invoice_id is None:
        # Customer-level automation without invoice still paused when any dispute open
        return FrequencyCheckResult(
            allowed=False,
            reason="Açık itiraz varken otomasyon durduruldu.",
            code="open_dispute",
            auto_last_24h=auto_24h,
            messages_last_7d=msg_7d,
            open_dispute=True,
            invoice_disputed=False,
        )

    if is_automatic and auto_24h >= MAX_AUTO_PER_24H:
        return FrequencyCheckResult(
            allowed=False,
            reason="24 saatte maksimum 1 otomatik mesaj gönderilebilir.",
            code="auto_24h_limit",
            auto_last_24h=auto_24h,
            messages_last_7d=msg_7d,
            open_dispute=open_dispute,
            invoice_disputed=invoice_disputed,
        )

    if msg_7d >= MAX_MESSAGES_PER_7D:
        return FrequencyCheckResult(
            allowed=False,
            reason="7 günde maksimum 3 mesaj gönderilebilir.",
            code="messages_7d_limit",
            auto_last_24h=auto_24h,
            messages_last_7d=msg_7d,
            open_dispute=open_dispute,
            invoice_disputed=invoice_disputed,
        )

    return FrequencyCheckResult(
        allowed=True,
        auto_last_24h=auto_24h,
        messages_last_7d=msg_7d,
        open_dispute=open_dispute,
        invoice_disputed=invoice_disputed,
    )


def assert_frequency_allowed(
    customer: Customer,
    *,
    is_automatic: bool = True,
    invoice_id: int | None = None,
) -> FrequencyCheckResult:
    result = check_frequency(
        customer, is_automatic=is_automatic, invoice_id=invoice_id
    )
    if not result.allowed:
        raise MessagingError(result.reason, result.code)
    return result
