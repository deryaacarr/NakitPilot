from django.urls import path

from apps.organizations.structure_views import (
    BranchListCreateView,
    CustomRoleDetailView,
    CustomRoleListCreateView,
    CustomerAssignmentView,
    MyResourceRulesView,
    TeamListCreateView,
    TeamMemberView,
)
from apps.organizations.views import (
    InvitationAcceptView,
    InvitationCreateView,
    InvitationDetailView,
    MembershipDetailView,
    MembershipListCreateView,
    OrganizationDetailView,
    OrganizationListCreateView,
)

urlpatterns = [
    path("invitations", InvitationCreateView.as_view(), name="invitation-create"),
    path(
        "invitations/<str:token>",
        InvitationDetailView.as_view(),
        name="invitation-detail",
    ),
    path(
        "invitations/<str:token>/accept",
        InvitationAcceptView.as_view(),
        name="invitation-accept",
    ),
    path("roles/", CustomRoleListCreateView.as_view(), name="org-custom-roles"),
    path("roles/<int:pk>/", CustomRoleDetailView.as_view(), name="org-custom-role-detail"),
    path("resource-rules/me/", MyResourceRulesView.as_view(), name="org-resource-rules-me"),
    path("branches/", BranchListCreateView.as_view(), name="org-branches"),
    path("teams/", TeamListCreateView.as_view(), name="org-teams"),
    path("teams/<int:team_id>/members/", TeamMemberView.as_view(), name="org-team-members"),
    path("customer-assignments/", CustomerAssignmentView.as_view(), name="org-customer-assignments"),
    path("", OrganizationListCreateView.as_view(), name="organization-list-create"),
    path("<int:pk>/", OrganizationDetailView.as_view(), name="organization-detail"),
    path(
        "<int:organization_id>/memberships/",
        MembershipListCreateView.as_view(),
        name="membership-list-create",
    ),
    path(
        "<int:organization_id>/memberships/<int:pk>/",
        MembershipDetailView.as_view(),
        name="membership-detail",
    ),
]
