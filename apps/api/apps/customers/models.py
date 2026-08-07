from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.organizations.tenancy import TenantModel


class RiskStatus(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class CustomerSource(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    KOLAYBI = "KOLAYBI", "KolayBi"


class Customer(TenantModel):
    """Debtor / cari account belonging to a single organization."""

    code = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=255)
    tax_number = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=100, blank=True)
    sector = models.CharField(max_length=100, blank=True)
    payment_term_days = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(0)],
    )
    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    risk_status = models.CharField(
        max_length=16,
        choices=RiskStatus.choices,
        default=RiskStatus.LOW,
    )
    risk_score = models.PositiveSmallIntegerField(default=0)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_customers",
    )
    notes = models.TextField(blank=True)
    # Free-form string tags for workflow actions (NP-213).
    tags = models.JSONField(default=list, blank=True)
    collection_strategy = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="NakitPilot-managed tahsilat stratejisi (entegrasyon ezmez).",
    )
    source = models.CharField(
        max_length=32,
        choices=CustomerSource.choices,
        default=CustomerSource.MANUAL,
        db_index=True,
    )
    external_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    # KolayBi-owned fields the user edited locally — sync must not overwrite these.
    local_field_overrides = models.JSONField(default=list, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_contact_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "customer"
        verbose_name_plural = "customers"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="uniq_customer_code_per_organization",
                condition=~models.Q(code=""),
            ),
            models.UniqueConstraint(
                fields=("organization", "source", "external_id"),
                name="uniq_customer_external_per_org_source",
                condition=~models.Q(external_id=""),
            ),
        ]

    def __str__(self) -> str:
        return self.name


class CustomerContact(TenantModel):
    """Contact person for a customer (NP-045)."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    full_name = models.CharField(max_length=255)
    title = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_primary", "full_name")
        verbose_name = "customer contact"
        verbose_name_plural = "customer contacts"

    def __str__(self) -> str:
        return self.full_name
