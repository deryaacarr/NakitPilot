from django.urls import path

from apps.workflows import views

urlpatterns = [
    path("meta/", views.WorkflowMetaView.as_view(), name="workflow-meta"),
    path("holidays/", views.OrganizationHolidayListCreateView.as_view(), name="workflow-holidays"),
    path(
        "holidays/<int:pk>/",
        views.OrganizationHolidayDetailView.as_view(),
        name="workflow-holiday-detail",
    ),
    path(
        "approvals/<int:pk>/decide/",
        views.WorkflowApprovalDecideView.as_view(),
        name="workflow-approval-decide",
    ),
    path("", views.WorkflowListCreateView.as_view(), name="workflow-list-create"),
    path("<int:pk>/", views.WorkflowDetailView.as_view(), name="workflow-detail"),
    path("<int:pk>/graph/", views.WorkflowGraphReplaceView.as_view(), name="workflow-graph"),
    path("<int:pk>/activate/", views.WorkflowActivateView.as_view(), name="workflow-activate"),
    path("<int:pk>/publish/", views.WorkflowPublishView.as_view(), name="workflow-publish"),
    path(
        "<int:pk>/deactivate/",
        views.WorkflowDeactivateView.as_view(),
        name="workflow-deactivate",
    ),
    path("<int:pk>/archive/", views.WorkflowArchiveView.as_view(), name="workflow-archive"),
    path("<int:pk>/versions/", views.WorkflowVersionsView.as_view(), name="workflow-versions"),
    path("<int:pk>/simulate/", views.WorkflowSimulateView.as_view(), name="workflow-simulate"),
    path("<int:pk>/test-run/", views.WorkflowTestRunView.as_view(), name="workflow-test-run"),
    path(
        "<int:pk>/executions/",
        views.WorkflowExecutionListView.as_view(),
        name="workflow-executions",
    ),
]
