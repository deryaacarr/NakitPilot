"""NP-270 — payable side; NP-271 — bank balances."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class BankAccount(TenantModel):
    """Manual bank balance tracking (NP-271). Integration can come later."""

    name = models.CharField(max_length=128)
    bank_name = models.CharField(max_length=128, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    currency = models.CharField(max_length=3, default="TRY")
    current_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
    )
    blocked_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    as_of = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "bank account"
        verbose_name_plural = "bank accounts"

    def __str__(self) -> str:
        return self.name

    @property
    def available_balance(self) -> Decimal:
        avail = self.current_balance - self.blocked_amount
        return avail


class ExpenseCategory(TenantModel):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "expense category"
        verbose_name_plural = "expense categories"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "name"),
                name="payables_category_uniq_org_name",
            )
        ]

    def __str__(self) -> str:
        return self.name


class PayableStatus(models.TextChoices):
    OPEN = "OPEN", "Açık"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Kısmi ödendi"
    PAID = "PAID", "Ödendi"
    CANCELLED = "CANCELLED", "İptal"


class Payable(TenantModel):
    """One-off supplier / vendor payable."""

    vendor_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payables",
    )
    due_date = models.DateField()
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    currency = models.CharField(max_length=3, default="TRY")
    status = models.CharField(
        max_length=32,
        choices=PayableStatus.choices,
        default=PayableStatus.OPEN,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payables",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("due_date", "id")
        verbose_name = "payable"
        verbose_name_plural = "payables"
        indexes = [
            models.Index(fields=["organization", "status", "due_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.vendor_name} · {self.amount}"

    @property
    def remaining_amount(self) -> Decimal:
        rem = self.amount - self.paid_amount
        return rem if rem > ZERO else ZERO


class RecurringExpense(TenantModel):
    """Repeating expense schedule (rent, salaries, etc.)."""

    name = models.CharField(max_length=128)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_expenses",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    currency = models.CharField(max_length=3, default="TRY")
    # day of month 1–28 (simplified)
    day_of_month = models.PositiveSmallIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "recurring expense"
        verbose_name_plural = "recurring expenses"

    def __str__(self) -> str:
        return self.name


class ExpectedExpense(TenantModel):
    """Ad-hoc expected cash outflow for forecast."""

    title = models.CharField(max_length=255)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expected_expenses",
    )
    expected_date = models.DateField()
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    currency = models.CharField(max_length=3, default="TRY")
    probability = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("1.0000"),
        validators=[MinValueValidator(ZERO)],
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("expected_date", "id")
        verbose_name = "expected expense"
        verbose_name_plural = "expected expenses"

    def __str__(self) -> str:
        return self.title

    @property
    def expected_amount(self) -> Decimal:
        return (self.amount * self.probability).quantize(Decimal("0.01"))
