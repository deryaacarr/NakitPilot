"""NP-240 — outbound email compose, approve, send, tracking, bounce."""

from __future__ import annotations

import html
import logging
from email.utils import make_msgid
from typing import Any
from urllib.parse import unquote, urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.utils import timezone

from apps.collections.models import CollectionActivity, CollectionActivityType
from apps.customers.models import Customer
from apps.integrations.crypto import (
    CredentialCryptoError,
    credential_key_hint,
    decrypt_credentials,
    encrypt_credentials,
)
from apps.invoices.models import Invoice
from apps.messaging.models import (
    EmailEventType,
    EmailProviderConfig,
    EmailProviderType,
    EmailTrackingEvent,
    MessageChannel,
    MessageTemplate,
    OutboundEmail,
    OutboundEmailStatus,
)
from apps.messaging.rendering import render_message_template
from apps.messaging.services import MessagingError

logger = logging.getLogger(__name__)

# 1x1 transparent GIF
_PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01"
    b"\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def get_provider_config(organization) -> EmailProviderConfig | None:
    return (
        EmailProviderConfig.objects.filter(organization=organization, is_active=True)
        .order_by("id")
        .first()
    )


def upsert_provider_config(
    organization,
    *,
    provider: str = EmailProviderType.SMTP,
    from_email: str,
    from_name: str = "",
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_use_tls: bool = True,
    smtp_use_ssl: bool = False,
    credentials: dict[str, Any] | None = None,
) -> EmailProviderConfig:
    config, _ = EmailProviderConfig.objects.get_or_create(
        organization=organization,
        defaults={
            "from_email": from_email,
            "provider": provider,
        },
    )
    config.provider = provider
    config.from_email = from_email
    config.from_name = from_name or ""
    config.smtp_host = smtp_host or ""
    config.smtp_port = smtp_port
    config.smtp_use_tls = smtp_use_tls
    config.smtp_use_ssl = smtp_use_ssl
    if credentials:
        config.encrypted_credentials = encrypt_credentials(credentials)
        config.key_hint = credential_key_hint(credentials)
    config.is_active = True
    config.save()
    return config


def provider_config_public(config: EmailProviderConfig) -> dict[str, Any]:
    return {
        "id": config.id,
        "organization": config.organization_id,
        "provider": config.provider,
        "from_email": config.from_email,
        "from_name": config.from_name,
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "smtp_use_tls": config.smtp_use_tls,
        "smtp_use_ssl": config.smtp_use_ssl,
        "key_hint": config.key_hint,
        "has_credentials": bool(config.encrypted_credentials),
        "is_active": config.is_active,
    }


def _record_event(
    email: OutboundEmail,
    event_type: str,
    *,
    url: str = "",
    meta: dict | None = None,
) -> EmailTrackingEvent:
    return EmailTrackingEvent.objects.create(
        organization=email.organization,
        email=email,
        event_type=event_type,
        url=url or "",
        meta=meta or {},
    )


def _tracking_base_url() -> str:
    return (getattr(settings, "PUBLIC_API_BASE_URL", None) or "http://localhost:8000").rstrip(
        "/"
    )


def inject_tracking(email: OutboundEmail, body_html: str) -> str:
    """Append open pixel and rewrite http(s) links for click tracking."""
    import re

    base = _tracking_base_url()
    token = email.tracking_token
    pixel = (
        f'<img src="{base}/api/public/email/o/{token}.gif" width="1" height="1" alt="" />'
    )

    def _rewrite(match: re.Match[str]) -> str:
        href = match.group(1)
        if "api/public/email/" in href:
            return match.group(0)
        tracked = f"{base}/api/public/email/c/{token}/?{urlencode({'u': href})}"
        return f'href="{tracked}"'

    rewritten = re.sub(r'href="(https?://[^"]+)"', _rewrite, body_html or "")
    if "</body>" in rewritten.lower():
        return re.sub(r"(?i)</body>", pixel + "</body>", rewritten, count=1)
    return rewritten + pixel


def text_to_html(text: str) -> str:
    escaped = html.escape(text or "").replace("\n", "<br>\n")
    return f"<html><body><p>{escaped}</p></body></html>"


def create_email_draft(
    *,
    organization,
    customer_id: int,
    actor=None,
    template_id: int | None = None,
    invoice_id: int | None = None,
    to_email: str = "",
    subject: str = "",
    body: str = "",
    require_approval: bool = True,
    is_automatic: bool = False,
) -> OutboundEmail:
    from apps.messaging.frequency import assert_frequency_allowed

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

    # NP-252: block automatic collection messages for disputed invoices
    if is_automatic or not require_approval:
        assert_frequency_allowed(
            customer,
            is_automatic=True,
            invoice_id=invoice_id,
        )

    template = None
    if template_id is not None:
        template = MessageTemplate.objects.filter(
            pk=template_id,
            organization_id=organization.id,
            channel=MessageChannel.EMAIL,
        ).first()
        if template is None:
            raise MessagingError("E-posta şablonu bulunamadı.", "template_not_found")
        preview = render_message_template(
            template, customer=customer, invoice=invoice
        )
        subject = subject or preview.get("subject") or template.subject
        body = body or preview.get("body") or template.body

    recipient = (to_email or customer.email or "").strip()
    if not recipient:
        raise MessagingError("Alıcı e-posta adresi gerekli.", "missing_to_email")
    if not (subject or "").strip() or not (body or "").strip():
        raise MessagingError("Konu ve gövde zorunlu.", "missing_content")

    status = (
        OutboundEmailStatus.PENDING_APPROVAL
        if require_approval
        else OutboundEmailStatus.APPROVED
    )
    email = OutboundEmail(
        organization=organization,
        customer=customer,
        invoice=invoice,
        template=template,
        to_email=recipient,
        subject=subject.strip(),
        body_text=body.strip(),
        body_html=text_to_html(body.strip()),
        status=status,
        created_by=actor,
    )
    if status == OutboundEmailStatus.APPROVED:
        email.approved_by = actor
        email.approved_at = timezone.now()
    email.save()
    return email


def preview_outbound_email(email: OutboundEmail) -> dict[str, Any]:
    html_body = inject_tracking(email, email.body_html or text_to_html(email.body_text))
    return {
        "id": email.id,
        "public_id": str(email.public_id),
        "to_email": email.to_email,
        "subject": email.subject,
        "body_text": email.body_text,
        "body_html": html_body,
        "status": email.status,
        "customer_id": email.customer_id,
        "template_id": email.template_id,
        "requires_approval": email.status
        in {
            OutboundEmailStatus.DRAFT,
            OutboundEmailStatus.PENDING_APPROVAL,
        },
        "tracking_enabled": True,
    }


@transaction.atomic
def approve_outbound_email(
    email: OutboundEmail,
    *,
    actor,
    confirmed: bool,
    queue_send: bool = True,
) -> OutboundEmail:
    if not confirmed:
        raise MessagingError(
            "Onay olmadan e-posta gönderilemez.",
            "confirmation_required",
        )
    if email.status not in {
        OutboundEmailStatus.DRAFT,
        OutboundEmailStatus.PENDING_APPROVAL,
        OutboundEmailStatus.APPROVED,
        OutboundEmailStatus.FAILED,
    }:
        raise MessagingError(
            f"Bu durumda onaylanamaz: {email.status}",
            "invalid_status",
        )
    email.status = OutboundEmailStatus.APPROVED
    email.approved_by = actor
    email.approved_at = timezone.now()
    email.save(
        update_fields=["status", "approved_by", "approved_at", "updated_at"]
    )
    _record_event(email, EmailEventType.APPROVED, meta={"user_id": getattr(actor, "id", None)})
    if queue_send:
        queue_outbound_email(email)
    return email


def queue_outbound_email(email: OutboundEmail) -> OutboundEmail:
    if email.status not in {
        OutboundEmailStatus.APPROVED,
        OutboundEmailStatus.FAILED,
    }:
        raise MessagingError(
            "Yalnızca onaylı e-postalar kuyruğa alınır.",
            "not_approved",
        )
    email.status = OutboundEmailStatus.QUEUED
    email.queued_at = timezone.now()
    email.error_message = ""
    email.save(update_fields=["status", "queued_at", "error_message", "updated_at"])
    _record_event(email, EmailEventType.QUEUED)
    from django.conf import settings as dj_settings

    from apps.messaging.tasks import send_outbound_email_task

    if getattr(dj_settings, "CELERY_TASK_ALWAYS_EAGER", False):
        send_outbound_email_now(email.id)
    else:
        send_outbound_email_task.delay(email.id)
    return email


def _build_connection(config: EmailProviderConfig | None):
    """SMTP or console/locmem connection."""
    backend = getattr(settings, "EMAIL_BACKEND", None)
    if backend and "locmem" in backend:
        return get_connection(backend=backend)

    if config is None or config.provider == EmailProviderType.CONSOLE:
        return get_connection(
            backend=getattr(
                settings,
                "EMAIL_BACKEND",
                "django.core.mail.backends.console.EmailBackend",
            )
        )

    if config.provider == EmailProviderType.API:
        # Provider API placeholder — fall back to SMTP fields if present,
        # otherwise console. Real SendGrid/SES adapters can plug in here.
        if not config.smtp_host:
            return get_connection(
                backend="django.core.mail.backends.console.EmailBackend"
            )

    creds: dict[str, Any] = {}
    if config.encrypted_credentials:
        try:
            creds = decrypt_credentials(config.encrypted_credentials)
        except CredentialCryptoError:
            logger.warning("email credential decrypt failed org=%s", config.organization_id)

    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=config.smtp_host or getattr(settings, "EMAIL_HOST", "localhost"),
        port=config.smtp_port or getattr(settings, "EMAIL_PORT", 587),
        username=creds.get("username") or creds.get("api_key") or "",
        password=creds.get("password") or creds.get("api_secret") or "",
        use_tls=config.smtp_use_tls,
        use_ssl=config.smtp_use_ssl,
        fail_silently=False,
    )


def send_outbound_email_now(email_id: int) -> OutboundEmail:
    email = OutboundEmail.objects.select_related(
        "organization", "customer", "template"
    ).get(pk=email_id)
    if email.status not in {
        OutboundEmailStatus.QUEUED,
        OutboundEmailStatus.APPROVED,
        OutboundEmailStatus.SENDING,
    }:
        return email

    email.status = OutboundEmailStatus.SENDING
    email.save(update_fields=["status", "updated_at"])

    config = get_provider_config(email.organization)
    from_email = (
        (config.from_email if config else None)
        or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@nakitpilot.local")
    )
    from_name = (config.from_name if config else "") or ""
    from_header = f"{from_name} <{from_email}>" if from_name else from_email

    html_body = inject_tracking(email, email.body_html or text_to_html(email.body_text))
    message_id = make_msgid(domain="nakitpilot.local")

    try:
        connection = _build_connection(config)
        msg = EmailMultiAlternatives(
            subject=email.subject,
            body=email.body_text,
            from_email=from_header,
            to=[email.to_email],
            connection=connection,
            headers={"Message-ID": message_id},
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)

        email.status = OutboundEmailStatus.SENT
        email.sent_at = timezone.now()
        email.provider = (config.provider if config else EmailProviderType.CONSOLE)
        email.provider_message_id = message_id
        email.error_message = ""
        email.save(
            update_fields=[
                "status",
                "sent_at",
                "provider",
                "provider_message_id",
                "error_message",
                "updated_at",
            ]
        )
        _record_event(email, EmailEventType.SENT, meta={"message_id": message_id})

        if email.activity_id is None:
            activity = CollectionActivity.objects.create(
                organization=email.organization,
                customer=email.customer,
                activity_type=CollectionActivityType.EMAIL,
                summary=f"E-posta gönderildi: {email.subject}",
                notes=email.body_text[:2000],
                created_by=email.approved_by or email.created_by,
                metadata={
                    "outbound_email_id": email.id,
                    "public_id": str(email.public_id),
                    "status": email.status,
                    "auto_sent": False,
                    "user_approved": True,
                },
            )
            email.activity = activity
            email.save(update_fields=["activity", "updated_at"])
    except Exception as exc:  # noqa: BLE001 — surface to status
        logger.exception("outbound email send failed id=%s", email.id)
        email.status = OutboundEmailStatus.FAILED
        email.error_message = str(exc)[:2000]
        email.save(update_fields=["status", "error_message", "updated_at"])
        _record_event(
            email, EmailEventType.FAILED, meta={"error": email.error_message}
        )
    return email


def mark_delivered(email: OutboundEmail) -> OutboundEmail:
    email.delivered_at = email.delivered_at or timezone.now()
    if email.status in {
        OutboundEmailStatus.SENT,
        OutboundEmailStatus.QUEUED,
        OutboundEmailStatus.SENDING,
    }:
        email.status = OutboundEmailStatus.DELIVERED
    email.save(update_fields=["delivered_at", "status", "updated_at"])
    _record_event(email, EmailEventType.DELIVERED)
    return email


def record_open(token: str, *, meta: dict | None = None) -> OutboundEmail | None:
    email = OutboundEmail.objects.filter(tracking_token=token).first()
    if email is None:
        return None
    email.open_count += 1
    email.opened_at = email.opened_at or timezone.now()
    if email.status in {
        OutboundEmailStatus.SENT,
        OutboundEmailStatus.DELIVERED,
    }:
        email.status = OutboundEmailStatus.OPENED
    email.save(update_fields=["open_count", "opened_at", "status", "updated_at"])
    _record_event(email, EmailEventType.OPEN, meta=meta or {})
    return email


def record_click(token: str, raw_url: str, *, meta: dict | None = None) -> tuple[OutboundEmail | None, str]:
    email = OutboundEmail.objects.filter(tracking_token=token).first()
    target = unquote(raw_url or "")
    if not target.startswith(("http://", "https://")):
        target = ""
    if email is None:
        return None, target
    email.click_count += 1
    email.clicked_at = email.clicked_at or timezone.now()
    if email.status != OutboundEmailStatus.BOUNCED:
        email.status = OutboundEmailStatus.CLICKED
    email.save(update_fields=["click_count", "clicked_at", "status", "updated_at"])
    _record_event(email, EmailEventType.CLICK, url=target, meta=meta or {})
    return email, target


def record_bounce(
    *,
    token: str = "",
    provider_message_id: str = "",
    bounce_type: str = "hard",
    detail: str = "",
) -> OutboundEmail | None:
    email = None
    if token:
        email = OutboundEmail.objects.filter(tracking_token=token).first()
    if email is None and provider_message_id:
        email = OutboundEmail.objects.filter(
            provider_message_id=provider_message_id
        ).first()
    if email is None:
        return None
    email.status = OutboundEmailStatus.BOUNCED
    email.bounced_at = timezone.now()
    email.bounce_type = (bounce_type or "hard")[:64]
    email.bounce_detail = (detail or "")[:2000]
    email.save(
        update_fields=[
            "status",
            "bounced_at",
            "bounce_type",
            "bounce_detail",
            "updated_at",
        ]
    )
    _record_event(
        email,
        EmailEventType.BOUNCE,
        meta={"bounce_type": email.bounce_type, "detail": email.bounce_detail},
    )
    return email


def serialize_outbound_email(email: OutboundEmail) -> dict[str, Any]:
    return {
        "id": email.id,
        "public_id": str(email.public_id),
        "customer_id": email.customer_id,
        "invoice_id": email.invoice_id,
        "template_id": email.template_id,
        "to_email": email.to_email,
        "subject": email.subject,
        "body_text": email.body_text,
        "status": email.status,
        "provider": email.provider,
        "provider_message_id": email.provider_message_id,
        "error_message": email.error_message,
        "approved_at": email.approved_at.isoformat() if email.approved_at else None,
        "queued_at": email.queued_at.isoformat() if email.queued_at else None,
        "sent_at": email.sent_at.isoformat() if email.sent_at else None,
        "delivered_at": email.delivered_at.isoformat() if email.delivered_at else None,
        "opened_at": email.opened_at.isoformat() if email.opened_at else None,
        "clicked_at": email.clicked_at.isoformat() if email.clicked_at else None,
        "bounced_at": email.bounced_at.isoformat() if email.bounced_at else None,
        "open_count": email.open_count,
        "click_count": email.click_count,
        "bounce_type": email.bounce_type,
        "created_at": email.created_at.isoformat(),
    }


def tracking_pixel_bytes() -> bytes:
    return _PIXEL_GIF
