from django.urls import path

from apps.collections.views import (
    CustomerPaymentPlanAcceptView,
    CustomerPaymentPlanSuggestView,
    CustomerTimelineView,
)
from apps.customers.views import (
    CustomerContactDetailView,
    CustomerContactListCreateView,
    CustomerDetailView,
    CustomerFeaturesView,
    CustomerListCreateView,
)
from apps.risk.views import (
    CustomerRiskExplanationView,
    CustomerRiskHistoryView,
    CustomerSummaryView,
)

urlpatterns = [
    path("", CustomerListCreateView.as_view(), name="customer-list-create"),
    path("<int:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
    path(
        "<int:pk>/timeline/",
        CustomerTimelineView.as_view(),
        name="customer-timeline",
    ),
    path(
        "<int:pk>/payment-plan-suggestions/",
        CustomerPaymentPlanSuggestView.as_view(),
        name="customer-payment-plan-suggestions",
    ),
    path(
        "<int:pk>/payment-plan-suggestions/accept/",
        CustomerPaymentPlanAcceptView.as_view(),
        name="customer-payment-plan-accept",
    ),
    path(
        "<int:pk>/risk-history/",
        CustomerRiskHistoryView.as_view(),
        name="customer-risk-history",
    ),
    path(
        "<int:pk>/risk-explanation/",
        CustomerRiskExplanationView.as_view(),
        name="customer-risk-explanation",
    ),
    path(
        "<int:pk>/summary/",
        CustomerSummaryView.as_view(),
        name="customer-summary",
    ),
    path(
        "<int:pk>/features/",
        CustomerFeaturesView.as_view(),
        name="customer-features",
    ),
    path(
        "<int:customer_id>/contacts/",
        CustomerContactListCreateView.as_view(),
        name="customer-contact-list-create",
    ),
    path(
        "<int:customer_id>/contacts/<int:pk>/",
        CustomerContactDetailView.as_view(),
        name="customer-contact-detail",
    ),
]
