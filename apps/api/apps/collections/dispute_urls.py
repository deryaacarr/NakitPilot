from django.urls import path

from apps.collections.dispute_views import (
    DisputeAttachmentDeleteView,
    DisputeAttachmentKindListView,
    DisputeAttachmentListCreateView,
    DisputeCategoryListView,
    DisputeDetailView,
    DisputeListCreateView,
    DisputeResolveView,
    DisputeStatusListView,
    DisputeTransitionView,
)
from apps.collections.dispute_report import DisputeResolutionReportView

urlpatterns = [
    path("", DisputeListCreateView.as_view(), name="dispute-list-create"),
    path("categories/", DisputeCategoryListView.as_view(), name="dispute-categories"),
    path("statuses/", DisputeStatusListView.as_view(), name="dispute-statuses"),
    path(
        "attachment-kinds/",
        DisputeAttachmentKindListView.as_view(),
        name="dispute-attachment-kinds",
    ),
    path(
        "resolution-report/",
        DisputeResolutionReportView.as_view(),
        name="dispute-resolution-report",
    ),
    path("<int:pk>/", DisputeDetailView.as_view(), name="dispute-detail"),
    path(
        "<int:pk>/transition/",
        DisputeTransitionView.as_view(),
        name="dispute-transition",
    ),
    path("<int:pk>/resolve/", DisputeResolveView.as_view(), name="dispute-resolve"),
    path(
        "<int:pk>/attachments/",
        DisputeAttachmentListCreateView.as_view(),
        name="dispute-attachments",
    ),
    path(
        "<int:pk>/attachments/<int:attachment_id>/",
        DisputeAttachmentDeleteView.as_view(),
        name="dispute-attachment-delete",
    ),
]
