"""Payment and allocation models (NP-070–074, NP-195)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
    CREDIT_CARD = "CREDIT_CARD", "Credit card"
    CHECK = "CHECK", "Check"
    OTHER = "OTHER", "Other"


class PaymentSource(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    KOLAYBI = "KOLAYBI", "KolayBi"


class Payment(TenantModel):
    """Customer payment receipt (NP-070). Soft-cancel only (NP-074)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_date = models.DateField()
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    currency = models.CharField(max_length=3, default="TRY")
    method = models.CharField(
        max_length=32,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
    )
    reference = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    unallocated_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text="Ödeme tutarı − aktif allocation toplamı (NP-072).",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_payments",
    )
    cancellation_reason = models.TextField(blank=True)
    source = models.CharField(
        max_length=32,
        choices=PaymentSource.choices,
        default=PaymentSource.MANUAL,
        db_index=True,
    )
    external_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-payment_date", "-id")
        verbose_name = "payment"
        verbose_name_plural = "payments"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="payment_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(unallocated_amount__gte=0),
                name="payment_unallocated_non_negative",
            ),
            models.UniqueConstraint(
                fields=("organization", "source", "external_id"),
                name="unique_external_payment",
                condition=~models.Q(external_id=""),
            ),
        ]

    def __str__(self) -> str:
        return f"Payment {self.id} {self.amount} {self.currency}"

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None

    def allocated_total(self) -> Decimal:
        total = self.allocations.aggregate(total=Sum("amount"))["total"]
        return total if total is not None else ZERO

    def refresh_unallocated(self, *, save: bool = True) -> Decimal:
        allocated = self.allocated_total()
        leftover = self.amount - allocated
        if leftover < ZERO:
            leftover = ZERO
        self.unallocated_amount = leftover
        if save:
            self.save(update_fields=["unallocated_amount", "updated_at"])
        return leftover

    def cancel(self, *, user=None, reason: str = "") -> None:
        if self.is_cancelled:
            return
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.cancellation_reason = (reason or "").strip()
        self.save(
            update_fields=[
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
                "updated_at",
            ]
        )


class PaymentAllocation(TenantModel):
    """Maps a payment amount slice onto an invoice (NP-071)."""

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "payment allocation"
        verbose_name_plural = "payment allocations"
        constraints = [
            models.UniqueConstraint(
                fields=("payment", "invoice"),
                name="uniq_allocation_payment_invoice",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="allocation_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Alloc {self.amount} → invoice {self.invoice_id}"
