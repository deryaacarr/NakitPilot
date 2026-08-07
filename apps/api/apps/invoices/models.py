from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    OPEN = "OPEN", "Open"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"
    OVERDUE = "OVERDUE", "Overdue"
    CANCELLED = "CANCELLED", "Cancelled"


class InvoiceSource(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    KOLAYBI = "KOLAYBI", "KolayBi"
    SAMPLE = "SAMPLE", "Örnek veri"


class Invoice(TenantModel):
    """Customer invoice / alacak faturası (NP-050)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    number = models.CharField(max_length=64)
    invoice_date = models.DateField()
    due_date = models.DateField()
    currency = models.CharField(max_length=3, default="TRY")
    subtotal_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    status = models.CharField(
        max_length=32,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
    )
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_invoices",
    )
    payment_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Faturanın tamamen ödendiği tarih (actual_delay için).",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(
        max_length=32,
        choices=InvoiceSource.choices,
        default=InvoiceSource.MANUAL,
        db_index=True,
    )
    external_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    # NP-291 — sample/demo invoices
    is_sample = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-invoice_date", "-id")
        verbose_name = "invoice"
        verbose_name_plural = "invoices"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="uniq_invoice_number_per_organization",
            ),
            models.UniqueConstraint(
                fields=("organization", "source", "external_id"),
                name="unique_external_invoice",
                condition=~models.Q(external_id=""),
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="invoice_total_amount_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.number} ({self.customer_id})"

    def allocated_amount(self) -> Decimal:
        """Sum of allocations from non-cancelled payments (NP-070/074)."""
        allocations = getattr(self, "allocations", None)
        if allocations is None:
            return ZERO
        total = allocations.filter(payment__cancelled_at__isnull=True).aggregate(
            total=Sum("amount")
        )["total"]
        return total if total is not None else ZERO

    def remaining_amount(self) -> Decimal:
        """Derived: total_amount − allocations (never stored)."""
        remaining = self.total_amount - self.allocated_amount()
        return remaining if remaining > ZERO else ZERO

    def cancel(self) -> None:
        if self.status == InvoiceStatus.CANCELLED:
            return
        self.status = InvoiceStatus.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at", "updated_at"])

    def refresh_payment_status(self, *, as_of=None, save: bool = True) -> str | None:
        """NP-051: kalan tutar + vade kurallarına göre durumu yenile."""
        from apps.invoices.services import recalculate_invoice_status

        return recalculate_invoice_status(self, as_of=as_of, save=save)
