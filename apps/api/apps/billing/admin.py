from django.contrib import admin

from apps.billing.models import (
    BillingInvoice,
    Coupon,
    PaymentAttempt,
    Subscription,
    SubscriptionPlan,
    UsageRecord,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "price_monthly", "is_active", "sort_order")
    list_filter = ("is_active",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "plan",
        "status",
        "read_only",
        "trial_ends_at",
        "dunning_step",
    )
    list_filter = ("status", "read_only", "plan")
    search_fields = ("organization__name", "organization__slug")


@admin.register(BillingInvoice)
class BillingInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "organization", "status", "total", "currency", "paid_at")
    list_filter = ("status",)


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "billing_invoice", "amount", "status", "provider", "attempted_at")
    list_filter = ("status", "provider")


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ("organization", "metric", "quantity", "period_start", "period_end")
    list_filter = ("metric",)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "amount_off", "is_active", "redeemed_count")
