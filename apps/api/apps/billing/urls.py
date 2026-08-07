from django.urls import path

from apps.billing.views import (
    AdminRevenueView,
    BillingInvoiceDownloadView,
    BillingInvoiceListView,
    CheckoutView,
    DunningProcessView,
    EntitlementCheckView,
    PaymentMethodView,
    PaymentWebhookView,
    PlanListView,
    ScheduleDowngradeView,
    SubscriptionCancelView,
    SubscriptionMeView,
    TrialView,
    UsageView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="billing-plans"),
    path("subscription/", SubscriptionMeView.as_view(), name="billing-subscription"),
    path("subscription/cancel/", SubscriptionCancelView.as_view(), name="billing-cancel"),
    path(
        "subscription/schedule-downgrade/",
        ScheduleDowngradeView.as_view(),
        name="billing-schedule-downgrade",
    ),
    path("subscription/payment-method/", PaymentMethodView.as_view(), name="billing-payment-method"),
    path("checkout/", CheckoutView.as_view(), name="billing-checkout"),
    path("webhooks/payments/", PaymentWebhookView.as_view(), name="billing-payment-webhook"),
    path("usage/", UsageView.as_view(), name="billing-usage"),
    path("trial/", TrialView.as_view(), name="billing-trial"),
    path("invoices/", BillingInvoiceListView.as_view(), name="billing-invoices"),
    path(
        "invoices/<int:pk>/download/",
        BillingInvoiceDownloadView.as_view(),
        name="billing-invoice-download",
    ),
    path("can-use/", EntitlementCheckView.as_view(), name="billing-can-use"),
    path("admin/revenue/", AdminRevenueView.as_view(), name="billing-admin-revenue"),
    path("admin/dunning/process/", DunningProcessView.as_view(), name="billing-dunning-process"),
]
