from django.urls import path

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
