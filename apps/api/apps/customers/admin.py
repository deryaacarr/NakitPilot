from django.contrib import admin

from apps.customers.models import Customer, CustomerContact


class CustomerContactInline(admin.TabularInline):
    model = CustomerContact
    extra = 0
    fields = ("full_name", "title", "email", "phone", "is_primary")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "organization",
        "risk_status",
        "assigned_user",
        "is_active",
        "created_at",
    )
    list_filter = ("risk_status", "is_active", "organization", "city", "sector")
    search_fields = ("name", "code", "tax_number", "email", "phone")
    readonly_fields = ("created_at", "updated_at")
    inlines = [CustomerContactInline]


@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "customer", "email", "phone", "is_primary", "organization")
    list_filter = ("is_primary", "organization")
    search_fields = ("full_name", "email", "phone", "customer__name")
