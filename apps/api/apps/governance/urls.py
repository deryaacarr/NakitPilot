from django.urls import path

from apps.governance.views import (
    AccessReportView,
    ApprovalDecideView,
    ApprovalListCreateView,
    DataExportDownloadView,
    DataExportView,
    DeletionCancelView,
    DeletionProcessView,
    DeletionRequestView,
    MaskPreviewView,
    ProcessingInventoryView,
    RetentionPolicyView,
    RetentionPurgeView,
    SSODiscoverView,
    SSOProviderView,
    SSOStartView,
    SessionListView,
    SessionRevokeAllView,
    SessionRevokeView,
)

urlpatterns = [
    path("approvals/", ApprovalListCreateView.as_view(), name="governance-approvals"),
    path("approvals/<int:pk>/decide/", ApprovalDecideView.as_view(), name="governance-approval-decide"),
    path("sso/providers/", SSOProviderView.as_view(), name="governance-sso-providers"),
    path("sso/discover/", SSODiscoverView.as_view(), name="governance-sso-discover"),
    path("retention/", RetentionPolicyView.as_view(), name="governance-retention"),
    path("retention/purge/", RetentionPurgeView.as_view(), name="governance-retention-purge"),
    path("exports/", DataExportView.as_view(), name="governance-exports"),
    path("exports/<int:pk>/download/", DataExportDownloadView.as_view(), name="governance-export-download"),
    path("deletion-requests/", DeletionRequestView.as_view(), name="governance-deletion"),
    path(
        "deletion-requests/<int:pk>/cancel/",
        DeletionCancelView.as_view(),
        name="governance-deletion-cancel",
    ),
    path("deletion-requests/process/", DeletionProcessView.as_view(), name="governance-deletion-process"),
    path("mask-preview/", MaskPreviewView.as_view(), name="governance-mask-preview"),
    path("access-report/", AccessReportView.as_view(), name="governance-access-report"),
    path("inventory/", ProcessingInventoryView.as_view(), name="governance-inventory"),
]

# Auth-adjacent session + SSO start mounted from accounts urls too
session_urlpatterns = [
    path("sessions/", SessionListView.as_view(), name="auth-sessions"),
    path("sessions/<int:pk>/revoke/", SessionRevokeView.as_view(), name="auth-session-revoke"),
    path("sessions/revoke-all/", SessionRevokeAllView.as_view(), name="auth-sessions-revoke-all"),
    path("sso/discover", SSODiscoverView.as_view(), name="auth-sso-discover"),
    path("sso/<str:protocol>/start", SSOStartView.as_view(), name="auth-sso-start"),
]
