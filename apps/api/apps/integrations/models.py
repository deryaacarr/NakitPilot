"""NP-190 — multi-tenant integration connection & sync models."""

from django.db import models

from apps.organizations.tenancy import TenantModel


class IntegrationProvider(models.TextChoices):
    KOLAYBI = "kolaybi", "KolayBi"


class ConnectionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONNECTED = "connected", "Connected"
    ERROR = "error", "Error"
    DISABLED = "disabled", "Disabled"


class SyncFrequency(models.TextChoices):
    MANUAL = "manual", "Manual"
    HOURLY = "hourly", "Hourly"
    DAILY = "daily", "Daily"


class IntegrationConnection(TenantModel):
    """Tenant-scoped link to an external provider company."""

    provider = models.CharField(max_length=64, choices=IntegrationProvider.choices, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.DRAFT,
        db_index=True,
    )
    external_company_id = models.CharField(max_length=128, blank=True, default="")
    external_company_name = models.CharField(max_length=255, blank=True, default="")
    settings_json = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_successful_sync_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True)
    sync_frequency = models.CharField(
        max_length=32,
        choices=SyncFrequency.choices,
        default=SyncFrequency.MANUAL,
    )
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "integration connection"
        verbose_name_plural = "integration connections"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "provider", "external_company_id"),
                name="uniq_integration_provider_company_per_org",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "provider"),
                name="integ_conn_org_provider_idx",
            ),
        ]

    def __str__(self) -> str:
        label = self.external_company_name or self.external_company_id or "—"
        return f"{self.provider}:{label}"


class IntegrationCredential(TenantModel):
    """Encrypted credentials for a connection. Plaintext never stored."""

    connection = models.OneToOneField(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name="credential",
    )
    encrypted_payload = models.TextField()
    key_hint = models.CharField(max_length=16, blank=True, default="")
    rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "integration credential"
        verbose_name_plural = "integration credentials"

    def __str__(self) -> str:
        return f"credential:{self.connection_id}"


class SyncJobStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class SyncJob(TenantModel):
    """One sync run for a connection."""

    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name="sync_jobs",
    )
    job_type = models.CharField(max_length=64, default="full")
    status = models.CharField(
        max_length=32,
        choices=SyncJobStatus.choices,
        default=SyncJobStatus.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    stats_json = models.JSONField(default=dict, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "sync job"
        verbose_name_plural = "sync jobs"

    def __str__(self) -> str:
        return f"sync:{self.connection_id}:{self.status}"


class SyncRecordAction(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    SKIPPED = "skipped", "Skipped"
    FAILED = "failed", "Failed"


class SyncRecord(TenantModel):
    """Per-entity outcome within a sync job."""

    job = models.ForeignKey(SyncJob, on_delete=models.CASCADE, related_name="records")
    entity_type = models.CharField(max_length=64, db_index=True)
    external_id = models.CharField(max_length=128, blank=True, default="")
    internal_id = models.CharField(max_length=64, blank=True, default="")
    action = models.CharField(max_length=32, choices=SyncRecordAction.choices)
    payload_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "sync record"
        verbose_name_plural = "sync records"


class SyncError(TenantModel):
    """Error captured during a sync job."""

    job = models.ForeignKey(SyncJob, on_delete=models.CASCADE, related_name="errors")
    record = models.ForeignKey(
        SyncRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="errors",
    )
    code = models.CharField(max_length=64, blank=True, default="")
    message = models.TextField()
    raw_detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "sync error"
        verbose_name_plural = "sync errors"


class ExternalObjectMapping(TenantModel):
    """Maps an external object id to an internal model instance."""

    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name="object_mappings",
    )
    entity_type = models.CharField(max_length=64, db_index=True)
    external_id = models.CharField(max_length=128)
    internal_model = models.CharField(max_length=128)
    internal_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "external object mapping"
        verbose_name_plural = "external object mappings"
        constraints = [
            models.UniqueConstraint(
                fields=("connection", "entity_type", "external_id"),
                name="uniq_external_object_per_connection",
            )
        ]
        indexes = [
            models.Index(
                fields=("organization", "internal_model", "internal_id"),
                name="integ_map_internal_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.external_id}→{self.internal_model}:{self.internal_id}"


class SyncEntityState(TenantModel):
    """Per-entity incremental sync bookmarks (NP-196)."""

    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name="sync_states",
    )
    entity_type = models.CharField(max_length=32, db_index=True)
    last_cursor = models.CharField(max_length=512, blank=True, default="")
    last_remote_update_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_successful_sync_at = models.DateTimeField(null=True, blank=True)
    checksums_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "sync entity state"
        verbose_name_plural = "sync entity states"
        constraints = [
            models.UniqueConstraint(
                fields=("connection", "entity_type"),
                name="uniq_sync_state_per_connection_entity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.connection_id}:{self.entity_type}"


class SyncConflictType(models.TextChoices):
    DUPLICATE_MANUAL_API = "duplicate_manual_api", "Duplicate manual + API"
    LOCAL_EDITED = "local_edited", "Locally edited"
    PAYMENT_AMOUNT_CHANGED = "payment_amount_changed", "Payment amount changed"
    CUSTOMER_MERGED_OR_DELETED = "customer_merged_or_deleted", "Customer merged or deleted"


class SyncConflictStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"


class SyncConflictResolution(models.TextChoices):
    USE_SOURCE = "use_source", "Use source"
    KEEP_LOCAL = "keep_local", "Keep local"
    MERGE = "merge", "Merge"
    SKIP_FIELD_FOREVER = "skip_field_forever", "Skip field forever"


class SyncConflict(TenantModel):
    """Unresolved sync conflict awaiting operator decision (NP-197)."""

    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name="conflicts",
    )
    job = models.ForeignKey(
        SyncJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conflicts",
    )
    entity_type = models.CharField(max_length=32, db_index=True)
    conflict_type = models.CharField(max_length=64, choices=SyncConflictType.choices)
    status = models.CharField(
        max_length=16,
        choices=SyncConflictStatus.choices,
        default=SyncConflictStatus.OPEN,
        db_index=True,
    )
    external_id = models.CharField(max_length=128, blank=True, default="")
    internal_model = models.CharField(max_length=128, blank=True, default="")
    internal_id = models.CharField(max_length=64, blank=True, default="")
    message = models.TextField(blank=True, default="")
    source_payload = models.JSONField(default=dict, blank=True)
    local_snapshot = models.JSONField(default=dict, blank=True)
    resolution = models.CharField(
        max_length=32,
        choices=SyncConflictResolution.choices,
        blank=True,
        default="",
    )
    resolution_detail = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_sync_conflicts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "sync conflict"
        verbose_name_plural = "sync conflicts"
        indexes = [
            models.Index(
                fields=("connection", "status", "entity_type"),
                name="integ_conflict_conn_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.conflict_type}:{self.external_id}:{self.status}"
