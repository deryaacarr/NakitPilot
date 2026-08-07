from django.contrib import admin

from apps.payments.models import Payment, PaymentAllocation


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    readonly_fields = ("invoice", "amount", "created_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "payment_date",
        "amount",
        "currency",
        "method",
        "unallocated_amount",
        "cancelled_at",
        "organization",
    )
    list_filter = ("method", "currency", "organization")
    search_fields = ("reference", "customer__name", "customer__code")
    readonly_fields = ("cancelled_at", "cancelled_by", "created_at", "updated_at")
    inlines = [PaymentAllocationInline]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "invoice", "amount", "organization")
    list_filter = ("organization",)
