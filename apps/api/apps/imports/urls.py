from django.urls import path

from apps.imports.views import (
    CanonicalImportFieldsView,
    ImportCommitView,
    ImportErrorsExportView,
    ImportJobDetailView,
    ImportMappingView,
    ImportPreviewView,
    InvoiceImportTemplateView,
    InvoiceImportUploadView,
)

urlpatterns = [
    path(
        "invoices/template/",
        InvoiceImportTemplateView.as_view(),
        name="import-invoice-template",
    ),
    path(
        "invoices/upload/",
        InvoiceImportUploadView.as_view(),
        name="import-invoice-upload",
    ),
    path("fields/", CanonicalImportFieldsView.as_view(), name="import-canonical-fields"),
    path("<int:pk>/", ImportJobDetailView.as_view(), name="import-job-detail"),
    path("<int:pk>/mapping/", ImportMappingView.as_view(), name="import-job-mapping"),
    path("<int:pk>/preview/", ImportPreviewView.as_view(), name="import-job-preview"),
    path("<int:pk>/commit/", ImportCommitView.as_view(), name="import-job-commit"),
    path(
        "<int:pk>/errors/export/",
        ImportErrorsExportView.as_view(),
        name="import-job-errors-export",
    ),
]
