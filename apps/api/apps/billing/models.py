"""EPIC 28 — SaaS subscription & billing (NP-280)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class PlanCode(models.TextChoices):
    STARTER = "STARTER", "Starter"
    PROFESSIONAL = "PROFESSIONAL", "Professional"
    BUSINESS = "BUSINESS", "Business"
    ENTERPRISE = "ENTERPRISE", "Enterprise"


class SubscriptionPlan(models.Model):
    """Product package definition (not tenant-scoped)."""

    code = models.CharField(max_length=32, choices=PlanCode.choices, unique=True)
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)]
    )
    price_yearly = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)]
    )
    # Feature entitlements JSON — single source of truth for NP-281
    entitlements = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "code")
        verbose_name = "subscription plan"
        verbose_name_plural = "subscription plans"

    def __str__(self) -> str:
        return self.name


class SubscriptionStatus(models.TextChoices):
    TRIALING = "TRIALING", "Deneme"
    ACTIVE = "ACTIVE", "Aktif"
    PAST_DUE = "PAST_DUE", "Gecikmiş"
    CANCELLED = "CANCELLED", "İptal"
    EXPIRED = "EXPIRED", "Süresi doldu"


class Subscription(TenantModel):
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=16,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIALING,
        db_index=True,
    )
    seats = models.PositiveIntegerField(default=1)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    # NP-283 — trial does not require a card
    card_required = models.BooleanField(default=False)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    # NP-283 / NP-284 — after trial expiry or dunning exhaustion
    read_only = models.BooleanField(default=False)
    grace_ends_at = models.DateTimeField(null=True, blank=True)
    dunning_step = models.PositiveSmallIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    # NP-285 — scheduled downgrade
    scheduled_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_subscriptions",
    )
    scheduled_plan_at = models.DateTimeField(null=True, blank=True)
    # NP-285 — payment method (tokenized; no full PAN stored)
    payment_provider = models.CharField(max_length=32, blank=True, default="")
    payment_provider_customer_id = models.CharField(max_length=128, blank=True, default="")
    payment_method_brand = models.CharField(max_length=32, blank=True, default="")
    payment_method_last4 = models.CharField(max_length=4, blank=True, default="")
    coupon = models.ForeignKey(
        "billing.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "subscription"
        verbose_name_plural = "subscriptions"
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                condition=models.Q(status__in=["TRIALING", "ACTIVE", "PAST_DUE"]),
                name="billing_one_active_subscription_per_org",
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization_id} · {self.plan.code} ({self.status})"


class SubscriptionItem(TenantModel):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="items",
    )
    sku = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)


class UsageMetric(models.TextChoices):
    """NP-282 — metered usage dimensions."""

    ACTIVE_CUSTOMERS = "active_customers", "Aktif müşteri"
    MONTHLY_INVOICES = "monthly_invoices", "Aylık işlenen fatura"
    API_REQUESTS = "api_requests", "API isteği"
    AI_TOKENS = "ai_tokens", "AI token"
    EMAILS_SENT = "emails_sent", "Gönderilen e-posta"
    WHATSAPP_SENT = "whatsapp_sent", "Gönderilen WhatsApp"
    FILE_STORAGE_BYTES = "file_storage_bytes", "Dosya depolama (byte)"
    INTEGRATION_SYNCS = "integration_syncs", "Entegrasyon senkronizasyonu"


class UsageRecord(TenantModel):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    metric = models.CharField(max_length=64)  # UsageMetric values
    quantity = models.PositiveBigIntegerField(default=0)
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_start",)
        indexes = [
            models.Index(fields=["organization", "metric", "period_start"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "subscription", "metric", "period_start", "period_end"),
                name="billing_usage_uniq_org_sub_metric_period",
            )
        ]


class BillingInvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Taslak"
    OPEN = "OPEN", "Açık"
    PAID = "PAID", "Ödendi"
    VOID = "VOID", "İptal"
    UNCOLLECTIBLE = "UNCOLLECTIBLE", "Tahsil edilemez"


class BillingInvoice(TenantModel):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="billing_invoices",
    )
    number = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=BillingInvoiceStatus.choices,
        default=BillingInvoiceStatus.DRAFT,
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    currency = models.CharField(max_length=3, default="TRY")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    pdf_path = models.CharField(max_length=512, blank=True, default="")
    line_items = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="billing_invoice_uniq_org_number",
            )
        ]


class PaymentAttemptStatus(models.TextChoices):
    PENDING = "PENDING", "Bekliyor"
    SUCCEEDED = "SUCCEEDED", "Başarılı"
    FAILED = "FAILED", "Başarısız"


class PaymentAttempt(TenantModel):
    billing_invoice = models.ForeignKey(
        BillingInvoice,
        on_delete=models.CASCADE,
        related_name="payment_attempts",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=16,
        choices=PaymentAttemptStatus.choices,
        default=PaymentAttemptStatus.PENDING,
    )
    provider = models.CharField(max_length=32, blank=True)
    provider_reference = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)
    attempted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-attempted_at",)


class Coupon(models.Model):
    code = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True)
    percent_off = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    amount_off = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    redeemed_count = models.PositiveIntegerField(default=0)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code
