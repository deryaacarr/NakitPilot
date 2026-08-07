"""Message templates (NP-130) and outbound email (NP-240)."""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.organizations.tenancy import TenantModel


class MessageChannel(models.TextChoices):
    EMAIL = "EMAIL", "E-posta"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    SMS = "SMS", "SMS"


class MessageTemplate(TenantModel):
    """Organization-scoped communication template."""

    name = models.CharField(max_length=128)
    channel = models.CharField(max_length=16, choices=MessageChannel.choices)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("channel", "name", "id")
        verbose_name = "message template"
        verbose_name_plural = "message templates"
        indexes = [
            models.Index(fields=["organization", "channel", "is_default"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.channel})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_default:
                (
                    MessageTemplate.objects.filter(
                        organization_id=self.organization_id,
                        channel=self.channel,
                        is_default=True,
                    )
                    .exclude(pk=self.pk)
                    .update(is_default=False)
                )


class EmailProviderType(models.TextChoices):
    SMTP = "SMTP", "SMTP"
    API = "API", "Sağlayıcı API"
    CONSOLE = "CONSOLE", "Konsol (geliştirme)"


class EmailProviderConfig(TenantModel):
    """Org email transport settings (NP-240). Secrets stored encrypted."""

    provider = models.CharField(
        max_length=16,
        choices=EmailProviderType.choices,
        default=EmailProviderType.SMTP,
    )
    from_email = models.EmailField()
    from_name = models.CharField(max_length=128, blank=True)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    encrypted_credentials = models.TextField(blank=True)
    key_hint = models.CharField(max_length=16, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "email provider config"
        verbose_name_plural = "email provider configs"
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                name="messaging_email_provider_one_per_org",
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization_id} · {self.provider}"


class OutboundEmailStatus(models.TextChoices):
    DRAFT = "DRAFT", "Taslak"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Onay bekliyor"
    APPROVED = "APPROVED", "Onaylandı"
    QUEUED = "QUEUED", "Kuyrukta"
    SENDING = "SENDING", "Gönderiliyor"
    SENT = "SENT", "Gönderildi"
    DELIVERED = "DELIVERED", "Teslim edildi"
    OPENED = "OPENED", "Açıldı"
    CLICKED = "CLICKED", "Tıklandı"
    BOUNCED = "BOUNCED", "Bounce"
    FAILED = "FAILED", "Başarısız"
    CANCELLED = "CANCELLED", "İptal"


class OutboundEmail(TenantModel):
    """Customer email with approval + delivery tracking (NP-240)."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tracking_token = models.CharField(max_length=64, unique=True, db_index=True)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="outbound_emails",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_emails",
    )
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_emails",
    )
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body_text = models.TextField()
    body_html = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=OutboundEmailStatus.choices,
        default=OutboundEmailStatus.PENDING_APPROVAL,
        db_index=True,
    )
    provider = models.CharField(max_length=16, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_outbound_emails",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_outbound_emails",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    open_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    bounce_type = models.CharField(max_length=64, blank=True)
    bounce_detail = models.TextField(blank=True)
    activity = models.ForeignKey(
        "collections.CollectionActivity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_emails",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "outbound email"
        verbose_name_plural = "outbound emails"
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
            models.Index(fields=["organization", "customer", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Email {self.id} → {self.to_email} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.tracking_token:
            self.tracking_token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)


class EmailEventType(models.TextChoices):
    QUEUED = "QUEUED", "Kuyruğa alındı"
    SENT = "SENT", "Gönderildi"
    DELIVERED = "DELIVERED", "Teslim"
    OPEN = "OPEN", "Açılma"
    CLICK = "CLICK", "Tıklama"
    BOUNCE = "BOUNCE", "Bounce"
    FAILED = "FAILED", "Hata"
    APPROVED = "APPROVED", "Onay"


class EmailTrackingEvent(TenantModel):
    """Open / click / bounce / delivery events for an outbound email."""

    email = models.ForeignKey(
        OutboundEmail,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=16, choices=EmailEventType.choices)
    url = models.TextField(blank=True)
    meta = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-occurred_at",)
        verbose_name = "email tracking event"
        verbose_name_plural = "email tracking events"
        indexes = [
            models.Index(fields=["organization", "event_type", "occurred_at"]),
        ]
