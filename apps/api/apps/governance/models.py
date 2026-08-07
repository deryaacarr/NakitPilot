"""EPIC 30/31 — approvals, SSO, sessions, KVKK governance."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.organizations.tenancy import TenantModel


class ApprovalActionType(models.TextChoices):
    HIGH_VALUE_PAYMENT_CANCEL = "high_value_payment_cancel", "Yüksek tutarlı ödeme iptali"
    BULK_MESSAGE = "bulk_message", "Toplu mesaj gönderimi"
    LEGAL_HANDOFF = "legal_handoff", "Hukuki sürece aktarma"
    CREDIT_LIMIT_CHANGE = "credit_limit_change", "Kredi limiti değiştirme"
    MANUAL_RISK_CHANGE = "manual_risk_change", "Manuel risk durumu değişikliği"
    LARGE_PAYMENT_PLAN = "large_payment_plan", "Büyük ödeme planı"


class ApprovalStatus(models.TextChoices):
    PENDING = "PENDING", "Bekliyor"
    APPROVED = "APPROVED", "Onaylandı"
    REJECTED = "REJECTED", "Reddedildi"
    CANCELLED = "CANCELLED", "İptal"


class ApprovalRequest(TenantModel):
    """NP-303 — dual-control for sensitive operations."""

    action_type = models.CharField(max_length=64, choices=ApprovalActionType.choices)
    status = models.CharField(
        max_length=16, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approval_requests_made",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_decided",
    )
    payload = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    decision_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class SSOProtocol(models.TextChoices):
    SAML = "SAML", "SAML"
    OIDC = "OIDC", "OpenID Connect"
    GOOGLE_WORKSPACE = "GOOGLE_WORKSPACE", "Google Workspace"
    MICROSOFT_ENTRA = "MICROSOFT_ENTRA", "Microsoft Entra ID"


class SSOProviderConfig(TenantModel):
    """NP-304 — enterprise SSO (Enterprise plan)."""

    protocol = models.CharField(max_length=32, choices=SSOProtocol.choices)
    name = models.CharField(max_length=128)
    is_enabled = models.BooleanField(default=False)
    # Non-secret metadata; secrets stored encrypted/ref only
    issuer_url = models.URLField(blank=True)
    client_id = models.CharField(max_length=255, blank=True)
    metadata_url = models.URLField(blank=True)
    entity_id = models.CharField(max_length=255, blank=True)
    acs_url = models.URLField(blank=True)
    domains = models.JSONField(default=list, blank=True)  # allowed email domains
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "SSO provider config"


class UserSession(models.Model):
    """NP-305 — active device/session inventory (JWT refresh jti)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_sessions",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_sessions",
    )
    refresh_jti = models.CharField(max_length=64, unique=True, db_index=True)
    device_label = models.CharField(max_length=128, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    is_suspicious = models.BooleanField(default=False)

    class Meta:
        ordering = ("-last_seen_at",)


class RetentionPolicy(TenantModel):
    """NP-310 — org-level retention windows (days)."""

    activity_logs_days = models.PositiveIntegerField(default=365 * 5)
    audit_logs_days = models.PositiveIntegerField(default=365 * 10)
    import_files_days = models.PositiveIntegerField(default=90)
    failed_webhook_bodies_days = models.PositiveIntegerField(default=30)
    ai_requests_days = models.PositiveIntegerField(default=30)
    deleted_user_data_days = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "retention policies"
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                name="uniq_retention_policy_per_org",
            )
        ]


class DataExportStatus(models.TextChoices):
    PENDING = "PENDING", "Bekliyor"
    RUNNING = "RUNNING", "Çalışıyor"
    READY = "READY", "Hazır"
    FAILED = "FAILED", "Başarısız"
    EXPIRED = "EXPIRED", "Süresi doldu"


class DataExportJob(TenantModel):
    """NP-311 — org admin data export."""

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="data_export_jobs",
    )
    # customers, invoices, payments, tasks, activities, files, audit
    datasets = models.JSONField(default=list)
    status = models.CharField(
        max_length=16, choices=DataExportStatus.choices, default=DataExportStatus.PENDING
    )
    file_path = models.CharField(max_length=512, blank=True)
    row_counts = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class DeletionRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Bekliyor"
    WAITING = "WAITING", "Bekleme süresi"
    CANCELLED = "CANCELLED", "İptal"
    PROCESSING = "PROCESSING", "İşleniyor"
    COMPLETED = "COMPLETED", "Tamamlandı"


class DeletionRequest(TenantModel):
    """NP-312 — soft deletion with waiting period."""

    target_type = models.CharField(max_length=32)  # organization | user
    target_id = models.CharField(max_length=64)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="deletion_requests",
    )
    status = models.CharField(
        max_length=16,
        choices=DeletionRequestStatus.choices,
        default=DeletionRequestStatus.PENDING,
    )
    waiting_until = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_report = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class DataAccessAction(models.TextChoices):
    VIEW_CUSTOMER = "view_customer", "Müşteri görüntüleme"
    DOWNLOAD_REPORT = "download_report", "Rapor indirme"
    EXPORT_DATA = "export_data", "Veri dışa aktarma"
    ACCESS_INTEGRATION = "access_integration", "Entegrasyon erişimi"


class DataAccessEvent(TenantModel):
    """NP-314 — who accessed what."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="data_access_events",
    )
    action = models.CharField(max_length=32, choices=DataAccessAction.choices)
    resource_type = models.CharField(max_length=64)
    resource_id = models.CharField(max_length=64, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["organization", "action", "created_at"]),
            models.Index(fields=["organization", "actor", "created_at"]),
        ]


class ProcessingInventoryItem(TenantModel):
    """NP-315 — data processing inventory (KVKK art. inventory)."""

    field_key = models.CharField(max_length=128)
    data_type = models.CharField(max_length=64)  # personal | financial | technical
    purpose = models.CharField(max_length=255)
    source = models.CharField(max_length=128)
    retention_days = models.PositiveIntegerField(default=0)
    roles_allowed = models.JSONField(default=list, blank=True)
    transferred_systems = models.JSONField(default=list, blank=True)
    deletion_method = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("field_key",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "field_key"),
                name="uniq_processing_inventory_field",
            )
        ]
