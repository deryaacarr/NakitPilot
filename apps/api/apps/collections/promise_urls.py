from django.urls import path

from apps.collections.promise_views import (
    PaymentPromiseCalendarView,
    PaymentPromiseCancelView,
    PaymentPromiseDetailView,
    PaymentPromiseListCreateView,
    PaymentPromiseStatusBoardView,
)

urlpatterns = [
    path("", PaymentPromiseListCreateView.as_view(), name="payment-promise-list"),
    path(
        "calendar/",
        PaymentPromiseCalendarView.as_view(),
        name="payment-promise-calendar",
    ),
    path(
        "board/",
        PaymentPromiseStatusBoardView.as_view(),
        name="payment-promise-board",
    ),
    path("<int:pk>/", PaymentPromiseDetailView.as_view(), name="payment-promise-detail"),
    path(
        "<int:pk>/cancel/",
        PaymentPromiseCancelView.as_view(),
        name="payment-promise-cancel",
    ),
]
