from django.contrib import admin

from apps.organizations.models import Invitation, Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "tax_number",
        "default_currency",
        "timezone",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "default_currency", "timezone")
    search_fields = ("name", "slug", "tax_number", "email", "phone")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("organization__name", "user__email")
    autocomplete_fields = ("organization", "user")
    readonly_fields = ("created_at",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "role",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "role")
    search_fields = ("email", "token", "organization__name")
    readonly_fields = ("token", "created_at", "accepted_at")
    autocomplete_fields = ("organization", "invited_by")
