from django.urls import path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

from apps.public_api.views import (
    CashFlowForecastView,
    CustomerListCreateView,
    CustomerRiskView,
    InvoiceListCreateView,
    PaymentCreateView,
)


class PublicSchemaView(SpectacularAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []


class PublicDocsView(SpectacularSwaggerView):
    permission_classes = [AllowAny]
    authentication_classes = []


urlpatterns = [
    # Match ticket paths without trailing slash; also accept slash forms.
    path("customers", CustomerListCreateView.as_view(), name="public-v1-customers"),
    path("customers/", CustomerListCreateView.as_view()),
    path(
        "customers/<int:pk>/risk",
        CustomerRiskView.as_view(),
        name="public-v1-customer-risk",
    ),
    path("customers/<int:pk>/risk/", CustomerRiskView.as_view()),
    path("invoices", InvoiceListCreateView.as_view(), name="public-v1-invoices"),
    path("invoices/", InvoiceListCreateView.as_view()),
    path("payments", PaymentCreateView.as_view(), name="public-v1-payments"),
    path("payments/", PaymentCreateView.as_view()),
    path(
        "forecast/cash-flow",
        CashFlowForecastView.as_view(),
        name="public-v1-forecast-cash-flow",
    ),
    path("forecast/cash-flow/", CashFlowForecastView.as_view()),
    path("schema", PublicSchemaView.as_view(), name="public-v1-schema"),
    path("schema/", PublicSchemaView.as_view()),
    path(
        "docs",
        PublicDocsView.as_view(url_name="public-v1-schema"),
        name="public-v1-docs",
    ),
    path(
        "docs/",
        PublicDocsView.as_view(url_name="public-v1-schema"),
    ),
]
