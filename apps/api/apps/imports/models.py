from django.conf import settings
from django.db import models

from apps.organizations.tenancy import TenantModel


class ImportType(models.TextChoices):
    INVOICES = "invoices", "Invoices"


class ImportJobStatus(models.TextChoices):
    """NP-066 lifecycle."""

    PENDING = "PENDING", "Pending"
    VALIDATING = "VALIDATING", "Validating"
    READY = "READY", "Ready"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class DuplicatePolicy(models.TextChoices):
    """NP-065 — MVP default: SKIP."""

    SKIP = "SKIP", "Skip row"
    UPDATE = "UPDATE", "Update existing"
    CREATE = "CREATE", "Create as new"


class ImportJob(TenantModel):
    """Excel/CSV import job."""

    import_type = models.CharField(
        max_length=32,
        choices=ImportType.choices,
        default=ImportType.INVOICES,
    )
    status = models.CharField(
        max_length=32,
        choices=ImportJobStatus.choices,
        default=ImportJobStatus.PENDING,
    )
    duplicate_policy = models.CharField(
        max_length=16,
        choices=DuplicatePolicy.choices,
        default=DuplicatePolicy.SKIP,
    )
    original_filename = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=512)
    content_type = models.CharField(max_length=128, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    file_hash = models.CharField(max_length=64, db_index=True)
    headers = models.JSONField(default=list, blank=True)
    column_mapping = models.JSONField(default=dict, blank=True)
    preview_summary = models.JSONField(default=dict, blank=True)
    preview_errors = models.JSONField(default=list, blank=True)
    result_summary = models.JSONField(default=dict, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    successful_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    skipped_duplicates = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_jobs",
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "import job"
        verbose_name_plural = "import jobs"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "file_hash"),
                name="uniq_import_file_hash_per_organization",
                condition=~models.Q(status=ImportJobStatus.CANCELLED),
            )
        ]

    def __str__(self) -> str:
        return f"{self.import_type}:{self.original_filename}"


class ImportErrorKind(models.TextChoices):
    VALIDATION = "VALIDATION", "Validation"
    DUPLICATE = "DUPLICATE", "Duplicate"
    SKIPPED = "SKIPPED", "Skipped"
    SYSTEM = "SYSTEM", "System"


class ImportError(TenantModel):
    """Row-level import error / skip reason."""

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="errors")
    row_number = models.PositiveIntegerField()
    field_name = models.CharField(max_length=64, blank=True)
    raw_value = models.TextField(blank=True)
    error_message = models.TextField()
    kind = models.CharField(
        max_length=16,
        choices=ImportErrorKind.choices,
        default=ImportErrorKind.VALIDATION,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("row_number", "id")
        verbose_name = "import error"
        verbose_name_plural = "import errors"
