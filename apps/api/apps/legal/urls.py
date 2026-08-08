from django.urls import path

from apps.legal.views import (
    LegalCaseActivityCreateView,
    LegalCaseApproveView,
    LegalCaseDetailView,
    LegalCaseDocumentUploadView,
    LegalCaseHandoffView,
    LegalCaseListCreateView,
    LegalCasePackageDownloadView,
    LegalCasePackageView,
    LegalCaseStatusView,
    LegalCriteriaView,
)

urlpatterns = [
    path("cases/", LegalCaseListCreateView.as_view(), name="legal-case-list"),
    path("cases/<int:pk>/", LegalCaseDetailView.as_view(), name="legal-case-detail"),
    path(
        "cases/<int:pk>/approve/",
        LegalCaseApproveView.as_view(),
        name="legal-case-approve",
    ),
    path(
        "cases/<int:pk>/handoff/",
        LegalCaseHandoffView.as_view(),
        name="legal-case-handoff",
    ),
    path(
        "cases/<int:pk>/status/",
        LegalCaseStatusView.as_view(),
        name="legal-case-status",
    ),
    path(
        "cases/<int:pk>/package/",
        LegalCasePackageView.as_view(),
        name="legal-case-package",
    ),
    path(
        "cases/<int:pk>/package/download/",
        LegalCasePackageDownloadView.as_view(),
        name="legal-case-package-download",
    ),
    path(
        "cases/<int:pk>/activities/",
        LegalCaseActivityCreateView.as_view(),
        name="legal-case-activity",
    ),
    path(
        "cases/<int:pk>/documents/",
        LegalCaseDocumentUploadView.as_view(),
        name="legal-case-document",
    ),
    path(
        "criteria/<int:customer_id>/",
        LegalCriteriaView.as_view(),
        name="legal-criteria",
    ),
]
