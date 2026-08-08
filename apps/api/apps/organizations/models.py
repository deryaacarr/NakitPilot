from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Organization(models.Model):
    """Tenant company that owns all business data."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    tax_number = models.CharField(max_length=32, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    default_currency = models.CharField(max_length=3, default="TRY")
    timezone = models.CharField(max_length=64, default="Europe/Istanbul")
    # ISO weekdays 1=Mon … 7=Sun (NP-214 business calendar).
    working_days = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_working_days(self) -> list[int]:
        days = self.working_days
        if isinstance(days, list) and days:
            return [int(d) for d in days]
        return [1, 2, 3, 4, 5]

    class Meta:
        ordering = ("name",)
        verbose_name = "organization"
        verbose_name_plural = "organizations"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.default_currency:
            self.default_currency = self.default_currency.upper()
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self) -> str:
        base = slugify(self.name) or "organization"
        candidate = base
        suffix = 2
        qs = Organization.objects.all()
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        while qs.filter(slug=candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate


class Role(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    FINANCE_MANAGER = "FINANCE_MANAGER", "Finance Manager"
    COLLECTION_AGENT = "COLLECTION_AGENT", "Collection Agent"
    VIEWER = "VIEWER", "Viewer"
    # NP-353 — external lawyer portal (assigned cases only)
    EXTERNAL_LAWYER = "EXTERNAL_LAWYER", "External Lawyer"


class Membership(models.Model):
    """Links a user to an organization with a role."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    # NP-300 — optional org-defined role (overrides built-in permission matrix)
    custom_role = models.ForeignKey(
        "organizations.CustomRole",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships",
    )
    # NP-302 — primary branch for resource scoping
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("organization_id", "user_id")
        verbose_name = "membership"
        verbose_name_plural = "memberships"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "user"),
                name="uniq_organization_user_membership",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.organization_id}:{self.role}"


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class Invitation(models.Model):
    """Organization invite delivered via link (email optional in later phases)."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.VIEWER)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    status = models.CharField(
        max_length=16,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "invitation"
        verbose_name_plural = "invitations"
        indexes = [
            models.Index(fields=("organization", "email", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.email} → {self.organization_id} ({self.status})"

    def mark_expired_if_needed(self) -> bool:
        from django.utils import timezone

        if self.status == InvitationStatus.PENDING and self.expires_at <= timezone.now():
            self.status = InvitationStatus.EXPIRED
            self.save(update_fields=["status"])
            return True
        return False

    @property
    def is_acceptable(self) -> bool:
        from django.utils import timezone

        return self.status == InvitationStatus.PENDING and self.expires_at > timezone.now()


class OrganizationHoliday(models.Model):
    """Org-specific non-working day for business-day calculations (NP-214)."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="holidays",
    )
    date = models.DateField()
    name = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("date",)
        verbose_name = "organization holiday"
        verbose_name_plural = "organization holidays"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "date"),
                name="uniq_org_holiday_date",
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization_id}:{self.date} {self.name}"


# NP-300–302 — imported so Django discovers models under this app label
from apps.organizations.structure import (  # noqa: E402
    Branch,
    CustomRole,
    CustomerAssignment,
    Team,
    TeamMembership,
)

# NP-402 — saved table views
from apps.organizations.saved_views import SavedTableView  # noqa: E402,F401
