"""Message template services (NP-130–133)."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.collections.models import CollectionActivity, CollectionActivityType
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.messaging.models import MessageChannel, MessageTemplate
from apps.messaging.rendering import render_message_template

CHANNEL_ACTIVITY = {
    MessageChannel.EMAIL: CollectionActivityType.EMAIL,
    MessageChannel.WHATSAPP: CollectionActivityType.WHATSAPP,
    MessageChannel.SMS: CollectionActivityType.NOTE,
}


class MessagingError(Exception):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


def preview_template(
    template: MessageTemplate,
    *,
    customer_id: int,
    invoice_id: int | None = None,
    payment_link: str = "",
) -> dict[str, Any]:
    customer = Customer.objects.filter(
        pk=customer_id, organization_id=template.organization_id
    ).first()
    if customer is None:
        raise MessagingError("Müşteri bulunamadı.", "customer_not_found")

    invoice = None
    if invoice_id is not None:
        invoice = Invoice.objects.filter(
            pk=invoice_id,
            organization_id=template.organization_id,
            customer_id=customer.id,
        ).first()
        if invoice is None:
            raise MessagingError("Fatura bulunamadı.", "invoice_not_found")

    return render_message_template(
        template,
        customer=customer,
        invoice=invoice,
        payment_link=payment_link,
    )


def generate_toned_message(
    organization,
    *,
    customer_id: int,
    tone: str,
    invoice_id: int | None = None,
    payment_link: str = "",
    actor=None,
) -> dict[str, Any]:
    """NP-233: tone assistant — DB-filled placeholders only (metered NP-235)."""
    from apps.ai_usage.models import AIFeature
    from apps.ai_usage.services import AIUsageLimitExceeded, run_metered
    from apps.messaging.assistant import MessageTone, generate_message

    if tone not in MessageTone.values:
        raise MessagingError("Geçersiz ton seçimi.", "invalid_tone")

    customer = Customer.objects.filter(
        pk=customer_id, organization_id=organization.id
    ).first()
    if customer is None:
        raise MessagingError("Müşteri bulunamadı.", "customer_not_found")

    invoice = None
    if invoice_id is not None:
        invoice = Invoice.objects.filter(
            pk=invoice_id,
            organization_id=organization.id,
            customer_id=customer.id,
        ).first()
        if invoice is None:
            raise MessagingError("Fatura bulunamadı.", "invoice_not_found")

    def _produce(_truncated_input: str) -> dict[str, Any]:
        from apps.ai_usage.prompt_security import (
            MESSAGE_ASSISTANT_SCHEMA,
            PromptSecurityError,
            secure_ai_produce,
        )

        try:
            return secure_ai_produce(
                organization=organization,
                scoped_objects=[customer, invoice],
                output_schema=MESSAGE_ASSISTANT_SCHEMA,
                producer=lambda: generate_message(
                    organization=organization,
                    customer=customer,
                    tone=tone,
                    invoice=invoice,
                    payment_link=payment_link,
                ),
            )
        except PromptSecurityError as exc:
            raise MessagingError(exc.message, exc.code) from exc

    try:
        metered = run_metered(
            organization=organization,
            user=actor,
            feature=AIFeature.MESSAGE_ASSISTANT,
            model="deterministic",
            input_text=f"tone={tone};customer={customer_id};invoice={invoice_id}",
            cache_payload={
                "tone": tone,
                "customer_id": customer_id,
                "invoice_id": invoice_id,
                "payment_link": payment_link,
            },
            producer=_produce,
        )
    except AIUsageLimitExceeded as exc:
        raise MessagingError(exc.message, exc.code) from exc
    return metered["result"]


def record_template_copy(
    template: MessageTemplate,
    *,
    customer_id: int,
    actor=None,
    invoice_id: int | None = None,
    create_activity: bool = False,
    rendered_body: str = "",
    rendered_subject: str = "",
    payment_link: str = "",
) -> dict[str, Any]:
    """NP-133: optional activity on copy — never logs as auto-sent."""
    preview = preview_template(
        template,
        customer_id=customer_id,
        invoice_id=invoice_id,
        payment_link=payment_link,
    )
    body = rendered_body or preview["body"]
    subject = rendered_subject or preview["subject"]

    activity = None
    if create_activity:
        customer = Customer.objects.get(pk=customer_id)
        activity_type = CHANNEL_ACTIVITY.get(
            template.channel, CollectionActivityType.NOTE
        )
        activity = CollectionActivity.objects.create(
            organization=template.organization,
            customer=customer,
            activity_type=activity_type,
            summary=f"Mesaj kopyalandı ({template.name})",
            notes=body[:4000],
            occurred_at=timezone.now(),
            created_by=actor,
            metadata={
                "source": "message_template_copy",
                "template_id": template.id,
                "channel": template.channel,
                "subject": subject,
                "auto_sent": False,
            },
        )

    return {
        "copied": True,
        "auto_sent": False,
        "subject": subject,
        "body": body,
        "activity_id": activity.id if activity else None,
        "message": "Mesaj kopyalandı",
    }


DEFAULT_TEMPLATES = [
    {
        "name": "Gecikmiş fatura hatırlatma",
        "channel": MessageChannel.EMAIL,
        "subject": "{{invoice_number}} numaralı fatura hatırlatması",
        "body": (
            "Merhaba {{customer_name}} yetkilisi,\n\n"
            "{{due_date}} vadeli {{invoice_amount}} tutarındaki faturanızın\n"
            "ödemesi henüz hesabımıza ulaşmamıştır.\n\n"
            "Kalan tutar: {{remaining_amount}}\n"
            "Gecikme: {{overdue_days}} gün\n\n"
            "Saygılarımızla,\n{{company_name}}"
        ),
        "is_default": True,
    },
    {
        "name": "WhatsApp kısa hatırlatma",
        "channel": MessageChannel.WHATSAPP,
        "subject": "",
        "body": (
            "Merhaba {{customer_name}}, {{due_date}} vadeli "
            "{{invoice_number}} faturanızın {{remaining_amount}} bakiyesi "
            "ödenmemiştir. {{company_name}}"
        ),
        "is_default": True,
    },
    {
        "name": "SMS hatırlatma",
        "channel": MessageChannel.SMS,
        "subject": "",
        "body": (
            "{{company_name}}: {{customer_name}}, {{invoice_number}} "
            "fatura bakiyesi {{remaining_amount}}. Vade {{due_date}}."
        ),
        "is_default": True,
    },
]


def ensure_default_templates(organization) -> int:
    """Create MVP default templates if org has none."""
    if MessageTemplate.objects.filter(organization=organization).exists():
        return 0
    created = 0
    for item in DEFAULT_TEMPLATES:
        MessageTemplate.objects.create(organization=organization, **item)
        created += 1
    return created
