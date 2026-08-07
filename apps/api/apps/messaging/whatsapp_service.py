"""NP-242 / NP-245 — WhatsApp Business send, bulk, status, inbound, opt-out."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone

from apps.collections.models import CollectionActivity, CollectionActivityType
from apps.customers.models import Customer, CustomerContact
from apps.integrations.crypto import (
    credential_key_hint,
    decrypt_credentials,
    encrypt_credentials,
)
from apps.invoices.models import Invoice
from apps.messaging.frequency import assert_frequency_allowed
from apps.messaging.models import (
    InboundWhatsApp,
    OutboundWhatsApp,
    ResponseClassification,
    WhatsAppApprovedTemplate,
    WhatsAppMessageStatus,
    WhatsAppOptOut,
    WhatsAppProviderConfig,
    WhatsAppStatusEvent,
    WhatsAppTemplateStatus,
)
from apps.messaging.preferences import assert_channel_allowed
from apps.messaging.rendering import render_message_template
from apps.messaging.services import MessagingError

logger = logging.getLogger(__name__)

# Bulk send hard caps (NP-242)
MAX_BULK_RECIPIENTS = 50
OPT_OUT_KEYWORDS = (
    "dur",
    "stop",
    "iptal",
    "vazgeç",
    "vazgec",
    "çıkar",
    "cikar",
    "abone olma",
    "unsubscribe",
    "opt out",
    "opt-out",
)

_CLASSIFY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    (ResponseClassification.PAID, ("ödeme yapt", "odeme yapt", "ödedim", "odedim", "havale yapt")),
    (ResponseClassification.PROMISE, ("söz ver", "soz ver", "ödeyeceğim", "odeyecegim", "yarın öde")),
    (ResponseClassification.INVOICE_DISPUTE, ("fatura hatal", "itiraz", "yanlış fatura", "yanlis fatura")),
    (ResponseClassification.WRONG_PERSON, ("yanlış kişi", "yanlis kisi", "ben değilim", "ben degilim")),
    (ResponseClassification.CASH_SHORTAGE, ("nakit sıkınt", "nakit sikint", "param yok", "ödeyemiyorum")),
    (ResponseClassification.CALLBACK_REQUEST, ("tekrar ara", "sonra ara", "geri dön", "geri don")),
    (ResponseClassification.LEGAL_DISPUTE, ("hukuk", "avukat", "mahkeme", "icra")),
]


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D+", "", (raw or "").strip())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = "90" + digits[1:]
    return digits


def get_provider_config(organization) -> WhatsAppProviderConfig | None:
    return (
        WhatsAppProviderConfig.objects.filter(organization=organization, is_active=True)
        .order_by("id")
        .first()
    )


def upsert_provider_config(
    organization,
    *,
    phone_number_id: str = "",
    waba_id: str = "",
    display_phone: str = "",
    mock_mode: bool = True,
    credentials: dict[str, Any] | None = None,
) -> WhatsAppProviderConfig:
    config, _ = WhatsAppProviderConfig.objects.get_or_create(
        organization=organization,
        defaults={"mock_mode": mock_mode},
    )
    config.phone_number_id = phone_number_id or ""
    config.waba_id = waba_id or ""
    config.display_phone = display_phone or ""
    config.mock_mode = bool(mock_mode)
    if credentials:
        config.encrypted_credentials = encrypt_credentials(credentials)
        config.key_hint = credential_key_hint(credentials)
    config.is_active = True
    config.save()
    return config


def provider_config_public(config: WhatsAppProviderConfig) -> dict[str, Any]:
    return {
        "id": config.id,
        "organization": config.organization_id,
        "phone_number_id": config.phone_number_id,
        "waba_id": config.waba_id,
        "display_phone": config.display_phone,
        "mock_mode": config.mock_mode,
        "key_hint": config.key_hint,
        "has_credentials": bool(config.encrypted_credentials),
        "is_active": config.is_active,
    }


def serialize_wa_template(tpl: WhatsAppApprovedTemplate) -> dict[str, Any]:
    return {
        "id": tpl.id,
        "organization": tpl.organization_id,
        "name": tpl.name,
        "language_code": tpl.language_code,
        "category": tpl.category,
        "body": tpl.body,
        "header": tpl.header,
        "footer": tpl.footer,
        "status": tpl.status,
        "external_template_id": tpl.external_template_id,
        "message_template_id": tpl.message_template_id,
        "variables_schema": tpl.variables_schema,
        "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
        "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
    }


def serialize_outbound_wa(msg: OutboundWhatsApp) -> dict[str, Any]:
    return {
        "id": msg.id,
        "public_id": str(msg.public_id),
        "organization": msg.organization_id,
        "customer_id": msg.customer_id,
        "invoice_id": msg.invoice_id,
        "template_id": msg.template_id,
        "to_phone": msg.to_phone,
        "body": msg.body,
        "status": msg.status,
        "is_automatic": msg.is_automatic,
        "batch_id": str(msg.batch_id) if msg.batch_id else None,
        "skip_reason": msg.skip_reason,
        "provider_message_id": msg.provider_message_id,
        "error_message": msg.error_message,
        "queued_at": msg.queued_at.isoformat() if msg.queued_at else None,
        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def serialize_inbound_wa(msg: InboundWhatsApp) -> dict[str, Any]:
    return {
        "id": msg.id,
        "organization": msg.organization_id,
        "customer_id": msg.customer_id,
        "from_phone": msg.from_phone,
        "body": msg.body,
        "provider_message_id": msg.provider_message_id,
        "matched_at": msg.matched_at.isoformat() if msg.matched_at else None,
        "match_method": msg.match_method,
        "suggested_classification": msg.suggested_classification,
        "classification": msg.classification,
        "classification_confirmed": msg.classification_confirmed,
        "classification_confirmed_at": (
            msg.classification_confirmed_at.isoformat()
            if msg.classification_confirmed_at
            else None
        ),
        "opt_out_detected": msg.opt_out_detected,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
    }


def is_opted_out(organization_id: int, phone: str) -> bool:
    phone_n = normalize_phone(phone)
    return WhatsAppOptOut.objects.filter(
        organization_id=organization_id,
        phone=phone_n,
        is_active=True,
    ).exists()


def resolve_customer_phone(customer: Customer, to_phone: str = "") -> str:
    if to_phone:
        return normalize_phone(to_phone)
    if customer.phone:
        return normalize_phone(customer.phone)
    contact = (
        CustomerContact.objects.filter(customer=customer)
        .exclude(phone="")
        .order_by("-is_primary", "id")
        .first()
    )
    if contact and contact.phone:
        return normalize_phone(contact.phone)
    raise MessagingError("WhatsApp numarası bulunamadı.", "phone_missing")


def _render_body(
    organization,
    *,
    template: WhatsAppApprovedTemplate | None,
    customer: Customer,
    invoice: Invoice | None,
    body_override: str = "",
) -> str:
    if body_override.strip():
        return body_override.strip()
    if template is None:
        raise MessagingError("Şablon veya mesaj metni zorunlu.", "template_required")
    # Prefer linked MessageTemplate rendering variables when available.
    if template.message_template_id:
        rendered = render_message_template(
            template.message_template,
            customer=customer,
            invoice=invoice,
        )
        return (rendered.get("body") or template.body).strip()
    body = template.body
    replacements = {
        "{{customer_name}}": customer.name,
        "{{invoice_number}}": invoice.number if invoice else "",
        "{{remaining_amount}}": str(invoice.remaining_amount()) if invoice else "",
    }
    for key, val in replacements.items():
        body = body.replace(key, val)
    return body.strip()


def _record_status(msg: OutboundWhatsApp, status: str, *, meta: dict | None = None) -> None:
    WhatsAppStatusEvent.objects.create(
        organization_id=msg.organization_id,
        message=msg,
        status=status,
        meta=meta or {},
    )


def _provider_send(msg: OutboundWhatsApp, config: WhatsAppProviderConfig | None) -> str:
    """Return provider message id. Mock by default."""
    if config is None or config.mock_mode:
        return f"mock-wa-{msg.public_id.hex[:16]}"
    # Live Meta Cloud API path — credentials present but HTTP send left for infra.
    try:
        creds = decrypt_credentials(config.encrypted_credentials) if config.encrypted_credentials else {}
    except Exception as exc:  # noqa: BLE001
        raise MessagingError(f"WhatsApp kimlik bilgisi okunamadı: {exc}", "wa_credentials") from exc
    if not creds.get("access_token") and not creds.get("api_key"):
        raise MessagingError("WhatsApp access token eksik.", "wa_token_missing")
    # Without network dependency in MVP, fall back to mock id tagged live-ready.
    logger.info(
        "WhatsApp live send stub org=%s phone_number_id=%s to=%s",
        msg.organization_id,
        config.phone_number_id,
        msg.to_phone,
    )
    return f"live-pending-{msg.public_id.hex[:16]}"


@transaction.atomic
def create_and_send_whatsapp(
    *,
    organization,
    customer_id: int,
    template_id: int | None = None,
    invoice_id: int | None = None,
    to_phone: str = "",
    body: str = "",
    actor=None,
    is_automatic: bool = False,
    batch_id: uuid.UUID | None = None,
    queue_send: bool = True,
) -> OutboundWhatsApp:
    customer = Customer.objects.filter(pk=customer_id, organization=organization).first()
    if customer is None:
        raise MessagingError("Müşteri bulunamadı.", "customer_not_found")

    template = None
    if template_id:
        template = (
            WhatsAppApprovedTemplate.objects.for_organization(organization)
            .filter(pk=template_id)
            .first()
        )
        if template is None:
            raise MessagingError("WhatsApp şablonu bulunamadı.", "template_not_found")
        if template.status != WhatsAppTemplateStatus.APPROVED:
            raise MessagingError(
                "Yalnızca onaylı şablonlarla gönderim yapılabilir.",
                "template_not_approved",
            )

    invoice = None
    if invoice_id:
        invoice = Invoice.objects.filter(pk=invoice_id, organization=organization).first()
        if invoice is None:
            raise MessagingError("Fatura bulunamadı.", "invoice_not_found")

    phone = resolve_customer_phone(customer, to_phone)
    if is_opted_out(organization.id, phone):
        raise MessagingError("Bu numara WhatsApp opt-out listesinde.", "opted_out")

    assert_channel_allowed(customer, "WHATSAPP", respect_hours=is_automatic)
    assert_frequency_allowed(
        customer, is_automatic=is_automatic, invoice_id=invoice_id
    )

    rendered = _render_body(
        organization,
        template=template,
        customer=customer,
        invoice=invoice,
        body_override=body,
    )
    msg = OutboundWhatsApp.objects.create(
        organization=organization,
        customer=customer,
        invoice=invoice,
        template=template,
        to_phone=phone,
        body=rendered,
        status=WhatsAppMessageStatus.DRAFT,
        is_automatic=is_automatic,
        batch_id=batch_id,
        created_by=actor,
    )
    if queue_send:
        send_whatsapp_now(msg.id)
        msg.refresh_from_db()
    return msg


def send_whatsapp_now(message_id: int) -> OutboundWhatsApp:
    msg = OutboundWhatsApp.objects.select_related("customer", "organization").filter(pk=message_id).first()
    if msg is None:
        raise MessagingError("Mesaj bulunamadı.", "not_found")
    if msg.status in {
        WhatsAppMessageStatus.SENT,
        WhatsAppMessageStatus.DELIVERED,
        WhatsAppMessageStatus.READ,
    }:
        return msg

    config = get_provider_config(msg.organization)
    msg.status = WhatsAppMessageStatus.SENDING
    msg.queued_at = msg.queued_at or timezone.now()
    msg.save(update_fields=["status", "queued_at", "updated_at"])
    _record_status(msg, WhatsAppMessageStatus.SENDING)

    try:
        provider_id = _provider_send(msg, config)
        now = timezone.now()
        msg.provider_message_id = provider_id
        msg.status = WhatsAppMessageStatus.SENT
        msg.sent_at = now
        msg.error_message = ""
        msg.save(
            update_fields=[
                "provider_message_id",
                "status",
                "sent_at",
                "error_message",
                "updated_at",
            ]
        )
        _record_status(msg, WhatsAppMessageStatus.SENT, meta={"provider_message_id": provider_id})
        try:
            from apps.billing.models import UsageMetric
            from apps.billing.usage import record_usage

            record_usage(msg.organization_id, UsageMetric.WHATSAPP_SENT, 1)
        except Exception:  # noqa: BLE001
            pass
        if msg.activity_id is None:
            activity = CollectionActivity.objects.create(
                organization_id=msg.organization_id,
                customer_id=msg.customer_id,
                activity_type=CollectionActivityType.WHATSAPP,
                summary=f"WhatsApp gönderildi → {msg.to_phone}",
                notes=msg.body[:2000],
                occurred_at=now,
                created_by=msg.created_by,
                metadata={
                    "outbound_whatsapp_id": msg.id,
                    "auto_sent": msg.is_automatic,
                    "status": msg.status,
                },
            )
            msg.activity = activity
            msg.save(update_fields=["activity", "updated_at"])
            Customer.objects.filter(pk=msg.customer_id).update(last_contact_at=now)
    except MessagingError as exc:
        msg.status = WhatsAppMessageStatus.FAILED
        msg.error_message = exc.message
        msg.save(update_fields=["status", "error_message", "updated_at"])
        _record_status(msg, WhatsAppMessageStatus.FAILED, meta={"error": exc.message})
        raise
    except Exception as exc:  # noqa: BLE001
        msg.status = WhatsAppMessageStatus.FAILED
        msg.error_message = str(exc)
        msg.save(update_fields=["status", "error_message", "updated_at"])
        _record_status(msg, WhatsAppMessageStatus.FAILED, meta={"error": str(exc)})
        raise MessagingError(str(exc), "send_failed") from exc
    return msg


def bulk_send_whatsapp(
    *,
    organization,
    customer_ids: Iterable[int],
    template_id: int,
    invoice_id: int | None = None,
    actor=None,
    is_automatic: bool = True,
) -> dict[str, Any]:
    ids = list(dict.fromkeys(int(x) for x in customer_ids))
    if not ids:
        raise MessagingError("En az bir müşteri gerekli.", "empty_recipients")
    if len(ids) > MAX_BULK_RECIPIENTS:
        raise MessagingError(
            f"Toplu gönderim en fazla {MAX_BULK_RECIPIENTS} alıcı olabilir.",
            "bulk_limit",
        )

    template = (
        WhatsAppApprovedTemplate.objects.for_organization(organization)
        .filter(pk=template_id, status=WhatsAppTemplateStatus.APPROVED)
        .first()
    )
    if template is None:
        raise MessagingError("Onaylı WhatsApp şablonu bulunamadı.", "template_not_approved")

    batch_id = uuid.uuid4()
    sent: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for cid in ids:
        try:
            msg = create_and_send_whatsapp(
                organization=organization,
                customer_id=cid,
                template_id=template.id,
                invoice_id=invoice_id,
                actor=actor,
                is_automatic=is_automatic,
                batch_id=batch_id,
                queue_send=True,
            )
            sent.append(serialize_outbound_wa(msg))
        except MessagingError as exc:
            skipped.append({"customer_id": cid, "code": exc.code, "detail": exc.message})
            # Persist skipped row for audit
            customer = Customer.objects.filter(pk=cid, organization=organization).first()
            if customer:
                try:
                    phone = resolve_customer_phone(customer)
                except MessagingError:
                    phone = ""
                OutboundWhatsApp.objects.create(
                    organization=organization,
                    customer=customer,
                    template=template,
                    to_phone=phone or "unknown",
                    body="",
                    status=WhatsAppMessageStatus.SKIPPED,
                    is_automatic=is_automatic,
                    batch_id=batch_id,
                    skip_reason=exc.code,
                    error_message=exc.message,
                    created_by=actor,
                )

    return {
        "batch_id": str(batch_id),
        "sent_count": len(sent),
        "skipped_count": len(skipped),
        "sent": sent,
        "skipped": skipped,
    }


def update_message_status(
    *,
    organization_id: int | None = None,
    provider_message_id: str = "",
    message_id: int | None = None,
    status: str,
    meta: dict | None = None,
) -> OutboundWhatsApp | None:
    status = (status or "").strip().upper()
    if status not in WhatsAppMessageStatus.values:
        raise MessagingError("Geçersiz durum.", "invalid_status")
    qs = OutboundWhatsApp.objects.all()
    if organization_id:
        qs = qs.filter(organization_id=organization_id)
    if message_id:
        msg = qs.filter(pk=message_id).first()
    else:
        msg = qs.filter(provider_message_id=provider_message_id).first()
    if msg is None:
        return None

    now = timezone.now()
    msg.status = status
    fields = ["status", "updated_at"]
    if status == WhatsAppMessageStatus.DELIVERED:
        msg.delivered_at = now
        fields.append("delivered_at")
    elif status == WhatsAppMessageStatus.READ:
        msg.read_at = now
        fields.append("read_at")
        if not msg.delivered_at:
            msg.delivered_at = now
            fields.append("delivered_at")
    elif status == WhatsAppMessageStatus.FAILED:
        msg.error_message = (meta or {}).get("error", msg.error_message)
        fields.append("error_message")
    msg.save(update_fields=fields)
    _record_status(msg, status, meta=meta)
    return msg


def match_customer_by_phone(organization, phone: str) -> tuple[Customer | None, str]:
    phone_n = normalize_phone(phone)
    if not phone_n:
        return None, ""
    customer = (
        Customer.objects.for_organization(organization)
        .exclude(phone="")
        .filter(phone__icontains=phone_n[-10:])
        .order_by("id")
        .first()
    )
    if customer:
        return customer, "customer.phone"
    contact = (
        CustomerContact.objects.for_organization(organization)
        .exclude(phone="")
        .filter(phone__icontains=phone_n[-10:])
        .select_related("customer")
        .order_by("-is_primary", "id")
        .first()
    )
    if contact:
        return contact.customer, "contact.phone"
    # Recent outbound to this number
    outbound = (
        OutboundWhatsApp.objects.for_organization(organization)
        .filter(to_phone=phone_n)
        .order_by("-created_at")
        .select_related("customer")
        .first()
    )
    if outbound:
        return outbound.customer, "outbound_history"
    return None, ""


def suggest_classification(body: str) -> str:
    text = (body or "").strip().lower()
    for label, hints in _CLASSIFY_HINTS:
        if any(h in text for h in hints):
            return label
    return ""


def detect_opt_out(body: str) -> bool:
    text = (body or "").strip().lower()
    return any(k in text for k in OPT_OUT_KEYWORDS)


@transaction.atomic
def ingest_inbound_whatsapp(
    *,
    organization,
    from_phone: str,
    body: str,
    provider_message_id: str = "",
    received_at=None,
) -> InboundWhatsApp:
    phone = normalize_phone(from_phone)
    customer, method = match_customer_by_phone(organization, phone)
    opt_out = detect_opt_out(body)
    suggested = suggest_classification(body)
    inbound = InboundWhatsApp.objects.create(
        organization=organization,
        customer=customer,
        from_phone=phone,
        body=(body or "").strip(),
        provider_message_id=provider_message_id or "",
        matched_at=timezone.now() if customer else None,
        match_method=method,
        suggested_classification=suggested,
        opt_out_detected=opt_out,
        received_at=received_at or timezone.now(),
    )
    if opt_out:
        record_opt_out(
            organization=organization,
            phone=phone,
            customer=customer,
            source_inbound=inbound,
            reason="inbound_keyword",
        )
    if customer:
        CollectionActivity.objects.create(
            organization=organization,
            customer=customer,
            activity_type=CollectionActivityType.WHATSAPP,
            summary="WhatsApp yanıtı alındı",
            notes=inbound.body[:2000],
            occurred_at=inbound.received_at,
            metadata={
                "inbound_whatsapp_id": inbound.id,
                "suggested_classification": suggested,
                "opt_out_detected": opt_out,
            },
        )
    return inbound


def record_opt_out(
    *,
    organization,
    phone: str,
    customer: Customer | None = None,
    source_inbound: InboundWhatsApp | None = None,
    reason: str = "",
) -> WhatsAppOptOut:
    phone_n = normalize_phone(phone)
    existing = WhatsAppOptOut.objects.filter(
        organization=organization, phone=phone_n, is_active=True
    ).first()
    if existing:
        return existing
    return WhatsAppOptOut.objects.create(
        organization=organization,
        customer=customer,
        phone=phone_n,
        is_active=True,
        reason=reason or "",
        source_inbound=source_inbound,
        opted_out_at=timezone.now(),
    )


def clear_opt_out(organization, phone: str) -> bool:
    phone_n = normalize_phone(phone)
    updated = WhatsAppOptOut.objects.filter(
        organization=organization, phone=phone_n, is_active=True
    ).update(is_active=False, opted_in_at=timezone.now())
    return updated > 0


@transaction.atomic
def confirm_classification(
    inbound: InboundWhatsApp,
    *,
    classification: str,
    actor=None,
) -> InboundWhatsApp:
    label = (classification or "").strip().upper()
    if label not in ResponseClassification.values:
        raise MessagingError(
            f"Geçersiz sınıflandırma. Seçenekler: {', '.join(ResponseClassification.values)}",
            "invalid_classification",
        )
    # NP-245: first stage requires explicit user confirmation.
    inbound.classification = label
    inbound.classification_confirmed = True
    inbound.classification_confirmed_by = actor
    inbound.classification_confirmed_at = timezone.now()
    inbound.save(
        update_fields=[
            "classification",
            "classification_confirmed",
            "classification_confirmed_by",
            "classification_confirmed_at",
        ]
    )
    return inbound
