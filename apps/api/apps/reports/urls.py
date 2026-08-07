from django.urls import path

from apps.reports.views import (
    ExportJobDetailView,
    ExportJobDownloadView,
    ExportJobListCreateView,
    ReportPreviewView,
)

urlpatterns = [
    path(
        "overdue-receivables/",
        ReportPreviewView.as_view(),
        {"report_slug": "overdue-receivables"},
        name="report-overdue-receivables",
    ),
    path(
        "collection-activity/",
        ReportPreviewView.as_view(),
        {"report_slug": "collection-activity"},
        name="report-collection-activity",
    ),
    path(
        "customer-risk/",
        ReportPreviewView.as_view(),
        {"report_slug": "customer-risk"},
        name="report-customer-risk",
    ),
    path("exports/", ExportJobListCreateView.as_view(), name="report-export-list"),
    path("exports/<int:pk>/", ExportJobDetailView.as_view(), name="report-export-detail"),
    path(
        "exports/<int:pk>/download/",
        ExportJobDownloadView.as_view(),
        name="report-export-download",
    ),
]
