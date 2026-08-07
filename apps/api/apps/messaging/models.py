"""Message templates (NP-130), outbound email (NP-240), WhatsApp (NP-242–245)."""

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


# ---------------------------------------------------------------------------
# WhatsApp Business (NP-242) + response classification (NP-245)
# ---------------------------------------------------------------------------


class WhatsAppTemplateStatus(models.TextChoices):
    DRAFT = "DRAFT", "Taslak"
    PENDING = "PENDING", "Onay bekliyor"
    APPROVED = "APPROVED", "Onaylı"
    REJECTED = "REJECTED", "Reddedildi"
    PAUSED = "PAUSED", "Duraklatıldı"


class WhatsAppApprovedTemplate(TenantModel):
    """Meta/WhatsApp approved (or pending) message template (NP-242)."""

    name = models.CharField(max_length=128)
    language_code = models.CharField(max_length=16, default="tr")
    category = models.CharField(max_length=64, blank=True)
    body = models.TextField()
    header = models.CharField(max_length=255, blank=True)
    footer = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16,
        choices=WhatsAppTemplateStatus.choices,
        default=WhatsAppTemplateStatus.DRAFT,
        db_index=True,
    )
    external_template_id = models.CharField(max_length=128, blank=True)
    message_template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_approvals",
    )
    variables_schema = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "language_code", "id")
        verbose_name = "WhatsApp approved template"
        verbose_name_plural = "WhatsApp approved templates"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "name", "language_code"),
                name="messaging_wa_template_uniq_org_name_lang",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.language_code}) · {self.status}"


class WhatsAppMessageStatus(models.TextChoices):
    DRAFT = "DRAFT", "Taslak"
    QUEUED = "QUEUED", "Kuyrukta"
    SENDING = "SENDING", "Gönderiliyor"
    SENT = "SENT", "Gönderildi"
    DELIVERED = "DELIVERED", "Teslim edildi"
    READ = "READ", "Okundu"
    FAILED = "FAILED", "Başarısız"
    CANCELLED = "CANCELLED", "İptal"
    SKIPPED = "SKIPPED", "Atlandı"


class OutboundWhatsApp(TenantModel):
    """Single WhatsApp outbound message with delivery status (NP-242)."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="outbound_whatsapp",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_whatsapp",
    )
    template = models.ForeignKey(
        WhatsAppApprovedTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_messages",
    )
    to_phone = models.CharField(max_length=32)
    body = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=WhatsAppMessageStatus.choices,
        default=WhatsAppMessageStatus.DRAFT,
        db_index=True,
    )
    is_automatic = models.BooleanField(default=False, db_index=True)
    batch_id = models.UUIDField(null=True, blank=True, db_index=True)
    skip_reason = models.CharField(max_length=128, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_outbound_whatsapp",
    )
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    activity = models.ForeignKey(
        "collections.CollectionActivity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_whatsapp",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "outbound WhatsApp"
        verbose_name_plural = "outbound WhatsApp messages"
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
            models.Index(fields=["organization", "customer", "created_at"]),
            models.Index(fields=["organization", "customer", "is_automatic", "sent_at"]),
        ]

    def __str__(self) -> str:
        return f"WA {self.id} → {self.to_phone} ({self.status})"


class WhatsAppStatusEvent(TenantModel):
    """Status webhook history for an outbound WhatsApp message."""

    message = models.ForeignKey(
        OutboundWhatsApp,
        on_delete=models.CASCADE,
        related_name="events",
    )
    status = models.CharField(max_length=16, choices=WhatsAppMessageStatus.choices)
    meta = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-occurred_at",)
        verbose_name = "WhatsApp status event"
        verbose_name_plural = "WhatsApp status events"


class ResponseClassification(models.TextChoices):
    """Inbound reply labels (NP-245)."""

    PAID = "PAID", "Ödeme yaptı"
    PROMISE = "PROMISE", "Ödeme sözü verdi"
    INVOICE_DISPUTE = "INVOICE_DISPUTE", "Fatura itirazı"
    WRONG_PERSON = "WRONG_PERSON", "Yanlış kişi"
    CASH_SHORTAGE = "CASH_SHORTAGE", "Nakit sıkıntısı"
    CALLBACK_REQUEST = "CALLBACK_REQUEST", "Tekrar iletişim talebi"
    LEGAL_DISPUTE = "LEGAL_DISPUTE", "Hukuki itiraz"


class InboundWhatsApp(TenantModel):
    """Inbound WhatsApp reply matched to a customer (NP-242 / NP-245)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbound_whatsapp",
    )
    from_phone = models.CharField(max_length=32, db_index=True)
    body = models.TextField()
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    match_method = models.CharField(max_length=32, blank=True)
    suggested_classification = models.CharField(
        max_length=32,
        choices=ResponseClassification.choices,
        blank=True,
    )
    classification = models.CharField(
        max_length=32,
        choices=ResponseClassification.choices,
        blank=True,
    )
    classification_confirmed = models.BooleanField(default=False)
    classification_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_wa_classifications",
    )
    classification_confirmed_at = models.DateTimeField(null=True, blank=True)
    opt_out_detected = models.BooleanField(default=False)
    received_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at",)
        verbose_name = "inbound WhatsApp"
        verbose_name_plural = "inbound WhatsApp messages"
        indexes = [
            models.Index(fields=["organization", "from_phone", "received_at"]),
            models.Index(fields=["organization", "customer", "received_at"]),
        ]

    def __str__(self) -> str:
        return f"Inbound WA {self.id} from {self.from_phone}"


class WhatsAppOptOut(TenantModel):
    """Opt-out tracking for WhatsApp numbers (NP-242)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_opt_outs",
    )
    phone = models.CharField(max_length=32, db_index=True)
    is_active = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, blank=True)
    source_inbound = models.ForeignKey(
        InboundWhatsApp,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opt_outs",
    )
    opted_out_at = models.DateTimeField(default=timezone.now)
    opted_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-opted_out_at",)
        verbose_name = "WhatsApp opt-out"
        verbose_name_plural = "WhatsApp opt-outs"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "phone"),
                condition=models.Q(is_active=True),
                name="messaging_wa_optout_active_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"Opt-out {self.phone} ({'active' if self.is_active else 'inactive'})"


class WhatsAppProviderConfig(TenantModel):
    """Org WhatsApp Business API settings (NP-242)."""

    phone_number_id = models.CharField(max_length=64, blank=True)
    waba_id = models.CharField(max_length=64, blank=True)
    display_phone = models.CharField(max_length=32, blank=True)
    encrypted_credentials = models.TextField(blank=True)
    key_hint = models.CharField(max_length=16, blank=True)
    mock_mode = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "WhatsApp provider config"
        verbose_name_plural = "WhatsApp provider configs"
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                name="messaging_wa_provider_one_per_org",
            )
        ]

    def __str__(self) -> str:
        return f"WA provider · org {self.organization_id}"
