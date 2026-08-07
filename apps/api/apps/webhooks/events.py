"""Webhook event type registry (NP-203)."""

from __future__ import annotations

from django.db import models


class WebhookEventType(models.TextChoices):
    INVOICE_CREATED = "invoice.created", "Invoice created"
    INVOICE_OVERDUE = "invoice.overdue", "Invoice overdue"
    INVOICE_PAID = "invoice.paid", "Invoice paid"
    PAYMENT_CREATED = "payment.created", "Payment created"
    PAYMENT_CANCELLED = "payment.cancelled", "Payment cancelled"
    PAYMENT_PROMISE_CREATED = "payment_promise.created", "Payment promise created"
    PAYMENT_PROMISE_BROKEN = "payment_promise.broken", "Payment promise broken"
    CUSTOMER_RISK_CHANGED = "customer.risk_changed", "Customer risk changed"
    COLLECTION_TASK_CREATED = "collection_task.created", "Collection task created"
    FORECAST_UPDATED = "forecast.updated", "Forecast updated"


ALL_EVENT_TYPES: tuple[str, ...] = tuple(WebhookEventType.values)
