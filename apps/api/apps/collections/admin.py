from django.contrib import admin

from apps.collections.models import CollectionActivity, CollectionTask, PaymentPromise


@admin.register(PaymentPromise)
class PaymentPromiseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "promised_date",
        "amount",
        "currency",
        "status",
        "organization",
    )
    list_filter = ("status", "currency", "organization")


@admin.register(CollectionTask)
class CollectionTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "customer",
        "status",
        "priority",
        "due_date",
        "assigned_to",
        "organization",
    )
    list_filter = ("status", "priority", "task_type", "source", "organization")
    search_fields = ("title", "customer__name")


@admin.register(CollectionActivity)
class CollectionActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "activity_type", "summary", "occurred_at", "organization")
    list_filter = ("activity_type", "organization")
