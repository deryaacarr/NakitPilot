from django.urls import path

from apps.payments.views import (
    PaymentAllocationsView,
    PaymentCancelView,
    PaymentDetailView,
    PaymentListCreateView,
)

urlpatterns = [
    path("", PaymentListCreateView.as_view(), name="payment-list-create"),
    path("<int:pk>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("<int:pk>/allocations/", PaymentAllocationsView.as_view(), name="payment-allocations"),
    path("<int:pk>/cancel/", PaymentCancelView.as_view(), name="payment-cancel"),
]
