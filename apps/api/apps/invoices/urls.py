from django.urls import path

from apps.invoices.bulk import InvoiceBulkActionView
from apps.invoices.views import InvoiceCancelView, InvoiceDetailView, InvoiceListCreateView

urlpatterns = [
    path("", InvoiceListCreateView.as_view(), name="invoice-list-create"),
    path("bulk/", InvoiceBulkActionView.as_view(), name="invoice-bulk"),
    path("<int:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("<int:pk>/cancel/", InvoiceCancelView.as_view(), name="invoice-cancel"),
]
