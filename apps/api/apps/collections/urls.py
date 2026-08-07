from django.urls import path

from apps.collections.views import (
    CollectionTaskBulkAssignView,
    CollectionTaskCancelView,
    CollectionTaskCompleteView,
    CollectionTaskConfirmNotesView,
    CollectionTaskDetailView,
    CollectionTaskListCreateView,
    CollectionTaskParseNotesView,
    CollectionTaskPrepareCallView,
    CollectionTaskTodayBoardView,
)

urlpatterns = [
    path("", CollectionTaskListCreateView.as_view(), name="collection-task-list"),
    path("today/", CollectionTaskTodayBoardView.as_view(), name="collection-task-today"),
    path(
        "bulk-assign/",
        CollectionTaskBulkAssignView.as_view(),
        name="collection-task-bulk-assign",
    ),
    path("<int:pk>/", CollectionTaskDetailView.as_view(), name="collection-task-detail"),
    path(
        "<int:pk>/complete/",
        CollectionTaskCompleteView.as_view(),
        name="collection-task-complete",
    ),
    path(
        "<int:pk>/cancel/",
        CollectionTaskCancelView.as_view(),
        name="collection-task-cancel",
    ),
    path(
        "<int:pk>/prepare-call/",
        CollectionTaskPrepareCallView.as_view(),
        name="collection-task-prepare-call",
    ),
    path(
        "<int:pk>/parse-notes/",
        CollectionTaskParseNotesView.as_view(),
        name="collection-task-parse-notes",
    ),
    path(
        "<int:pk>/confirm-notes/",
        CollectionTaskConfirmNotesView.as_view(),
        name="collection-task-confirm-notes",
    ),
]
