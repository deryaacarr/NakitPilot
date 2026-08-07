"""NP-300–302 — custom roles, resource rules, branch/team structure."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.organizations.tenancy import TenantModel


# Canonical resource rule values (NP-301)
class ResourceScope(models.TextChoices):
    ALL = "all", "Tümü"
    ASSIGNED = "assigned_only", "Sadece atananlar"
    BRANCH = "branch", "Şube"
    TEAM = "team", "Ekip"
    NONE = "none", "Yok"


class ResourceAccess(models.TextChoices):
    FULL = "full", "Tam"
    READ = "read", "Salt okunur"
    DENY = "deny", "Yok"


DEFAULT_ROLE_TEMPLATES = [
    {
        "name": "Bölge Tahsilat Uzmanı",
        "slug": "bolge-tahsilat-uzmani",
        "permissions": [
            "manage_collection_task",
            "view_reports",
            "add_customer",
        ],
        "resource_rules": {
            "customers": ResourceScope.ASSIGNED,
            "invoices": ResourceScope.ASSIGNED,
            "payments": ResourceAccess.READ,
            "risk_score": True,
            "risk_reasons": False,
        },
    },
    {
        "name": "Tahsilat Yöneticisi",
        "slug": "tahsilat-yoneticisi",
        "permissions": [
            "manage_collection_task",
            "add_customer",
            "add_invoice",
            "add_payment",
            "view_reports",
        ],
        "resource_rules": {
            "customers": ResourceScope.TEAM,
            "invoices": ResourceScope.TEAM,
            "payments": ResourceAccess.FULL,
            "risk_score": True,
            "risk_reasons": True,
        },
    },
    {
        "name": "Finans Direktörü",
        "slug": "finans-direktoru",
        "permissions": [
            "add_customer",
            "add_invoice",
            "add_payment",
            "manage_collection_task",
            "view_reports",
            "manage_settings",
        ],
        "resource_rules": {
            "customers": ResourceScope.ALL,
            "invoices": ResourceScope.ALL,
            "payments": ResourceAccess.FULL,
            "risk_score": True,
            "risk_reasons": True,
        },
    },
    {
        "name": "Sadece Rapor",
        "slug": "sadece-rapor",
        "permissions": ["view_reports"],
        "resource_rules": {
            "customers": ResourceScope.ALL,
            "invoices": ResourceScope.ALL,
            "payments": ResourceAccess.READ,
            "risk_score": True,
            "risk_reasons": False,
        },
    },
    {
        "name": "Dış Muhasebeci",
        "slug": "dis-muhasebeci",
        "permissions": ["view_reports", "add_invoice", "add_payment"],
        "resource_rules": {
            "customers": ResourceScope.BRANCH,
            "invoices": ResourceScope.BRANCH,
            "payments": ResourceAccess.READ,
            "risk_score": False,
            "risk_reasons": False,
        },
    },
]


class CustomRole(TenantModel):
    """NP-300 — org-defined role with permission + resource rules."""

    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list, blank=True)
    # NP-301 resource rules: customers/invoices scopes, payments access, risk flags
    resource_rules = models.JSONField(default=dict, blank=True)
    is_system_template = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"),
                name="uniq_custom_role_slug_per_org",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:128] or "rol"
        super().save(*args, **kwargs)


class Branch(TenantModel):
    """NP-302 — organizational branch / şube."""

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "branches"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="uniq_branch_code_per_org",
                condition=~models.Q(code=""),
            )
        ]

    def __str__(self) -> str:
        return self.name


class Team(TenantModel):
    """NP-302 — team within a branch (optional)."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
    )
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "name"),
                name="uniq_team_name_per_org",
            )
        ]

    def __str__(self) -> str:
        return self.name


class TeamMembership(TenantModel):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    is_lead = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("team", "user"),
                name="uniq_team_user_membership",
            )
        ]


class CustomerAssignment(TenantModel):
    """NP-301/302 — assign customer to user/team/branch."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="customer_assignments",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_assignments",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "user"]),
            models.Index(fields=["organization", "customer"]),
        ]
