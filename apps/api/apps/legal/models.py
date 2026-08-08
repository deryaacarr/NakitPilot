"""EPIC 35 — legal collection preparation (not automated legal decisions)."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel

ZERO = Decimal("0.00")


class LegalCaseStatus(models.TextChoices):
    """NP-354 — process tracking statuses (preparation / handoff only)."""

    PREPARING = "PREPARING", "Hazırlanıyor"
    HANDED_TO_LAWYER = "HANDED_TO_LAWYER", "Avukata aktarıldı"
    NOTICE = "NOTICE", "İhtar aşaması"
    MEDIATION = "MEDIATION", "Arabuluculuk"
    LAWSUIT = "LAWSUIT", "Dava"
    ENFORCEMENT = "ENFORCEMENT", "İcra"
    COLLECTED = "COLLECTED", "Tahsil edildi"
    CLOSED = "CLOSED", "Kapatıldı"


LEGAL_TERMINAL_STATUSES = frozenset(
    {
        LegalCaseStatus.COLLECTED,
        LegalCaseStatus.CLOSED,
    }
)


class LegalCase(TenantModel):
    """NP-350 — legal case file (preparation & tracking, not legal advice)."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="legal_cases",
    )
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=32,
        choices=LegalCaseStatus.choices,
        default=LegalCaseStatus.PREPARING,
        db_index=True,
    )
    balance_at_open = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    criteria_snapshot = models.JSONField(default=dict, blank=True)
    manager_approved = models.BooleanField(default=False)
    manager_approved_at = models.DateTimeField(null=True, blank=True)
    manager_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_legal_cases",
    )
    assigned_lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_legal_cases",
    )
    approval_request = models.ForeignKey(
        "governance.ApprovalRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legal_cases",
    )
    package_path = models.CharField(max_length=512, blank=True)
    package_generated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_legal_cases",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-opened_at", "-id")
        verbose_name = "legal case"
        verbose_name_plural = "legal cases"
        indexes = [
            models.Index(fields=("organization", "status")),
            models.Index(fields=("organization", "assigned_lawyer")),
            models.Index(fields=("organization", "customer")),
        ]

    def __str__(self) -> str:
        return self.title or f"LegalCase #{self.pk} — {self.customer_id}"


class LegalCaseInvoice(TenantModel):
    """NP-350 — invoices linked to a legal case."""

    legal_case = models.ForeignKey(
        LegalCase,
        on_delete=models.CASCADE,
        related_name="case_invoices",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.CASCADE,
        related_name="legal_case_links",
    )
    amount_at_link = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "legal case invoice"
        verbose_name_plural = "legal case invoices"
        constraints = [
            models.UniqueConstraint(
                fields=("legal_case", "invoice"),
                name="legal_case_invoice_uniq",
            )
        ]


class LegalCaseActivity(TenantModel):
    """NP-350 — notes / process activity on a legal case."""

    legal_case = models.ForeignKey(
        LegalCase,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    summary = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    is_lawyer_visible = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legal_case_activities",
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        verbose_name = "legal case activity"
        verbose_name_plural = "legal case activities"


class LegalCaseDocument(TenantModel):
    """NP-350 — documents attached to a legal case."""

    legal_case = models.ForeignKey(
        LegalCase,
        on_delete=models.CASCADE,
        related_name="documents",
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
        related_name="legal_case_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "legal case document"
        verbose_name_plural = "legal case documents"

    def __str__(self) -> str:
        return self.original_filename


class LegalCaseStatusHistory(TenantModel):
    """NP-350 / NP-354 — status transition audit."""

    legal_case = models.ForeignKey(
        LegalCase,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, choices=LegalCaseStatus.choices)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legal_status_changes",
    )
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-occurred_at", "-id")
        verbose_name = "legal case status history"
        verbose_name_plural = "legal case status histories"
