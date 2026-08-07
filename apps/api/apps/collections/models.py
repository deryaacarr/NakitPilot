"""Collection tasks, activities, and payment promises (EPIC 7–8)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class PaymentPromiseStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    FULFILLED = "FULFILLED", "Fulfilled"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED", "Partially fulfilled"
    BROKEN = "BROKEN", "Broken"
    CANCELLED = "CANCELLED", "Cancelled"


class PaymentPromise(TenantModel):
    """Customer commitment to pay on a date."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="payment_promises",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_promises",
    )
    promised_date = models.DateField()
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    currency = models.CharField(max_length=3, default="TRY")
    status = models.CharField(
        max_length=32,
        choices=PaymentPromiseStatus.choices,
        default=PaymentPromiseStatus.PENDING,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payment_promises",
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("promised_date", "id")
        verbose_name = "payment promise"
        verbose_name_plural = "payment promises"

    def __str__(self) -> str:
        return f"Promise {self.amount} on {self.promised_date}"


class CollectionTaskType(models.TextChoices):
    CALL = "CALL", "Call"
    EMAIL = "EMAIL", "Email"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    FOLLOW_UP = "FOLLOW_UP", "Follow-up"
    MEETING = "MEETING", "Meeting"
    OTHER = "OTHER", "Other"


class CollectionTaskStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class CollectionTaskPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class CollectionTaskSource(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    OVERDUE_INVOICE = "OVERDUE_INVOICE", "Overdue invoice"
    BROKEN_PROMISE = "BROKEN_PROMISE", "Broken promise"
    FOLLOW_UP = "FOLLOW_UP", "Follow-up"


class CallOutcome(models.TextChoices):
    """NP-083 complete outcomes (Turkish labels)."""

    REACHED = "REACHED", "Ulaşıldı"
    NOT_REACHED = "NOT_REACHED", "Ulaşılamadı"
    PAYMENT_MADE = "PAYMENT_MADE", "Ödeme yapıldı"
    PROMISE_GIVEN = "PROMISE_GIVEN", "Ödeme sözü verdi"
    DISPUTED = "DISPUTED", "İtiraz etti"
    WRONG_PERSON = "WRONG_PERSON", "Yanlış kişi"
    CALLBACK = "CALLBACK", "Tekrar aranacak"


class CollectionTask(TenantModel):
    """Tahsilat görevi (NP-080)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="collection_tasks",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collection_tasks",
    )
    related_promise = models.ForeignKey(
        PaymentPromise,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collection_tasks",
    )
    task_type = models.CharField(
        max_length=32,
        choices=CollectionTaskType.choices,
        default=CollectionTaskType.CALL,
    )
    status = models.CharField(
        max_length=32,
        choices=CollectionTaskStatus.choices,
        default=CollectionTaskStatus.OPEN,
    )
    priority = models.CharField(
        max_length=16,
        choices=CollectionTaskPriority.choices,
        default=CollectionTaskPriority.LOW,
    )
    priority_score = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_collection_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_collection_tasks",
    )
    source = models.CharField(
        max_length=32,
        choices=CollectionTaskSource.choices,
        default=CollectionTaskSource.MANUAL,
    )
    outcome = models.CharField(
        max_length=32,
        choices=CallOutcome.choices,
        blank=True,
    )
    outcome_notes = models.TextField(blank=True)
    callback_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("due_date", "-priority_score", "id")
        verbose_name = "collection task"
        verbose_name_plural = "collection tasks"
        indexes = [
            models.Index(fields=("organization", "status", "due_date")),
            models.Index(fields=("organization", "assigned_to", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"

    @property
    def is_open(self) -> bool:
        return self.status in {
            CollectionTaskStatus.OPEN,
            CollectionTaskStatus.IN_PROGRESS,
        }


class CollectionActivityType(models.TextChoices):
    CALL = "CALL", "Telefon görüşmesi"
    EMAIL = "EMAIL", "E-posta"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    TASK_COMPLETED = "TASK_COMPLETED", "Görev tamamlandı"
    PROMISE = "PROMISE", "Ödeme sözü"
    PAYMENT = "PAYMENT", "Ödeme"
    NOTE = "NOTE", "Not"
    OTHER = "OTHER", "Diğer"


class CollectionActivity(TenantModel):
    """Timeline / görüşme kaydı (NP-086)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="collection_activities",
    )
    task = models.ForeignKey(
        CollectionTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    activity_type = models.CharField(
        max_length=32,
        choices=CollectionActivityType.choices,
        default=CollectionActivityType.NOTE,
    )
    summary = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collection_activities",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        verbose_name = "collection activity"
        verbose_name_plural = "collection activities"

    def __str__(self) -> str:
        return f"{self.activity_type}: {self.summary}"


# ---------------------------------------------------------------------------
# Disputes (NP-250 / EPIC 25)
# ---------------------------------------------------------------------------


class DisputeCategory(models.TextChoices):
    INVOICE_ERROR = "INVOICE_ERROR", "Fatura hatası"
    MISSING_DELIVERY = "MISSING_DELIVERY", "Eksik teslimat"
    SERVICE_DISPUTE = "SERVICE_DISPUTE", "Hizmet uyuşmazlığı"
    PRICE_DISPUTE = "PRICE_DISPUTE", "Fiyat itirazı"
    TAX_ERROR = "TAX_ERROR", "Vergi bilgisi hatası"
    UNAUTHORIZED_INVOICE = "UNAUTHORIZED_INVOICE", "Yetkisiz fatura"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE", "Mükerrer fatura"
    OTHER = "OTHER", "Diğer"


class DisputeStatus(models.TextChoices):
    """NP-251 dispute workflow statuses."""

    OPEN = "OPEN", "Açık"
    UNDER_REVIEW = "UNDER_REVIEW", "İncelemede"
    WAITING_CUSTOMER = "WAITING_CUSTOMER", "Müşteri bekleniyor"
    WAITING_INTERNAL = "WAITING_INTERNAL", "İç birim bekleniyor"
    RESOLVED = "RESOLVED", "Çözüldü"
    REJECTED = "REJECTED", "Reddedildi"
    CANCELLED = "CANCELLED", "İptal"


# Active (non-terminal) statuses — disputed amounts / automation gates
DISPUTE_ACTIVE_STATUSES = frozenset(
    {
        DisputeStatus.OPEN,
        DisputeStatus.UNDER_REVIEW,
        DisputeStatus.WAITING_CUSTOMER,
        DisputeStatus.WAITING_INTERNAL,
    }
)
DISPUTE_TERMINAL_STATUSES = frozenset(
    {
        DisputeStatus.RESOLVED,
        DisputeStatus.REJECTED,
        DisputeStatus.CANCELLED,
    }
)


class DisputeAttachmentKind(models.TextChoices):
    """NP-253 evidence types."""

    PDF = "PDF", "PDF"
    IMAGE = "IMAGE", "Görsel"
    DELIVERY_DOC = "DELIVERY_DOC", "Teslimat belgesi"
    EMAIL = "EMAIL", "E-posta"
    CONTRACT = "CONTRACT", "Sözleşme"


class Dispute(TenantModel):
    """Invoice/customer dispute case (NP-250 / NP-251)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="disputes",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes",
    )
    category = models.CharField(max_length=32, choices=DisputeCategory.choices)
    status = models.CharField(
        max_length=32,
        choices=DisputeStatus.choices,
        default=DisputeStatus.OPEN,
        db_index=True,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(ZERO)],
    )
    opened_at = models.DateTimeField(default=timezone.now)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_disputes",
    )
    description = models.TextField(blank=True)
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_disputes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-opened_at", "-id")
        verbose_name = "dispute"
        verbose_name_plural = "disputes"
        indexes = [
            models.Index(fields=["organization", "status", "opened_at"]),
            models.Index(fields=["organization", "customer", "status"]),
            models.Index(fields=["organization", "invoice", "status"]),
        ]

    def __str__(self) -> str:
        return f"Dispute {self.id} · {self.category} ({self.status})"

    @property
    def is_open(self) -> bool:
        return self.status in DISPUTE_ACTIVE_STATUSES


class DisputeStatusEvent(TenantModel):
    """Audit trail for NP-251 workflow transitions."""

    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name="status_events",
    )
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, choices=DisputeStatus.choices)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispute_status_events",
    )
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-occurred_at", "-id")
        verbose_name = "dispute status event"
        verbose_name_plural = "dispute status events"


class DisputeAttachment(TenantModel):
    """Evidence files attached to a dispute (NP-253)."""

    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    kind = models.CharField(
        max_length=32,
        choices=DisputeAttachmentKind.choices,
        default=DisputeAttachmentKind.PDF,
    )
    original_filename = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=512)
    content_type = models.CharField(max_length=128, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispute_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "dispute attachment"
        verbose_name_plural = "dispute attachments"

    def __str__(self) -> str:
        return f"{self.kind}: {self.original_filename}"
