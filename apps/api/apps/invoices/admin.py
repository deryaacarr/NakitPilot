from django.contrib import admin

from apps.invoices.models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "customer",
        "organization",
        "invoice_date",
        "due_date",
        "total_amount",
        "currency",
        "status",
        "created_at",
    )
    list_filter = ("status", "currency", "organization")
    search_fields = ("number", "customer__name", "customer__code", "description")
    readonly_fields = ("cancelled_at", "payment_completion_date", "created_at", "updated_at")
    raw_id_fields = ("customer", "assigned_user", "organization")
