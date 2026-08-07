from django.urls import path

from apps.invoices.views import InvoiceCancelView, InvoiceDetailView, InvoiceListCreateView

urlpatterns = [
    path("", InvoiceListCreateView.as_view(), name="invoice-list-create"),
    path("<int:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("<int:pk>/cancel/", InvoiceCancelView.as_view(), name="invoice-cancel"),
]
