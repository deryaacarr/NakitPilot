from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.invitations import accept_invitation, create_invitation
from apps.organizations.models import Invitation, Membership, Role
from apps.organizations.permissions import (
    CanManageOrganizationSettings,
    HasOrganizationPermission,
    IsOrganizationMember,
)
from apps.organizations.roles import Permission
from apps.organizations.serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationPublicSerializer,
    InvitationSerializer,
    MembershipCreateSerializer,
    MembershipSerializer,
    OrganizationSerializer,
)
from apps.organizations.services import user_organizations_queryset
from apps.organizations.tenancy import get_request_organization


class OrganizationListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/organizations/ — list memberships' orgs; create + OWNER membership."""

    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return user_organizations_queryset(self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        organization = serializer.save()
        Membership.objects.create(
            organization=organization,
            user=self.request.user,
            role=Role.OWNER,
            is_active=True,
        )
        # NP-283 / NP-294 — start trial + analytics (no PII)
        try:
            from apps.billing.subscription_service import ensure_subscription

            ensure_subscription(organization)
        except Exception:  # noqa: BLE001
            pass
        try:
            from apps.onboarding.analytics import track_event
            from apps.onboarding.progress import ensure_state

            ensure_state(organization)
            track_event(organization, "organization_created", {"source": "api"})
        except Exception:  # noqa: BLE001
            pass


class OrganizationDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH/PUT /api/organizations/<id>/ — member can view; settings role can update."""

    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageOrganizationSettings]
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return user_organizations_queryset(self.request.user)


class MembershipListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/organizations/<organization_id>/memberships/"""

    permission_classes = [permissions.IsAuthenticated, HasOrganizationPermission]
    required_permission = Permission.MANAGE_USERS

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MembershipCreateSerializer
        return MembershipSerializer

    def get_queryset(self):
        return Membership.objects.filter(
            organization_id=self.kwargs["organization_id"]
        ).select_related("user", "organization")

    def perform_create(self, serializer):
        serializer.save(organization_id=self.kwargs["organization_id"])


class MembershipDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/organizations/<organization_id>/memberships/<id>/"""

    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrganizationPermission]
    required_permission = Permission.MANAGE_USERS
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Membership.objects.filter(
            organization_id=self.kwargs["organization_id"]
        ).select_related("user", "organization")

    def perform_update(self, serializer):
        from apps.audit.models import write_audit_log

        previous_role = serializer.instance.role
        previous_active = serializer.instance.is_active
        super().perform_update(serializer)
        membership = serializer.instance
        if membership.role != previous_role or membership.is_active != previous_active:
            write_audit_log(
                organization=membership.organization,
                actor=self.request.user,
                action="membership.role_change",
                entity_type="Membership",
                entity_id=membership.id,
                summary=(
                    f"Kullanıcı rolü değişti: {membership.user.email} "
                    f"{previous_role} → {membership.role}"
                ),
                changes={
                    "user_id": membership.user_id,
                    "previous_role": previous_role,
                    "role": membership.role,
                    "previous_is_active": previous_active,
                    "is_active": membership.is_active,
                },
            )

class MyMembershipsView(generics.ListAPIView):
    """GET /api/memberships/me/ — current user's memberships."""

    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Membership.objects.filter(
            user=self.request.user,
            is_active=True,
        ).select_related("user", "organization")


class InvitationCreateView(APIView):
    """POST /api/organizations/invitations — create invite + shareable link."""

    permission_classes = [permissions.IsAuthenticated, HasOrganizationPermission]
    required_permission = Permission.MANAGE_USERS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response(
                {"detail": "Valid X-Organization-Id with active membership is required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = create_invitation(
                organization=organization,
                email=serializer.validated_data["email"],
                role=serializer.validated_data["role"],
                invited_by=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            InvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )


class InvitationDetailView(APIView):
    """GET /api/organizations/invitations/{token} — public invite preview."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, _request, token: str):
        invitation = Invitation.objects.select_related("organization").filter(token=token).first()
        if invitation is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        invitation.mark_expired_if_needed()
        return Response(InvitationPublicSerializer(invitation).data)


class InvitationAcceptView(APIView):
    """POST /api/organizations/invitations/{token}/accept — create/join via invite link."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, token: str):
        invitation = Invitation.objects.select_related("organization").filter(token=token).first()
        if invitation is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, membership, created_user = accept_invitation(
                invitation,
                password=serializer.validated_data["password"],
                first_name=serializer.validated_data.get("first_name", ""),
                last_name=serializer.validated_data.get("last_name", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Invitation accepted.",
                "created_user": created_user,
                "user_id": user.id,
                "membership_id": membership.id,
                "organization_id": membership.organization_id,
                "role": membership.role,
            },
            status=status.HTTP_200_OK,
        )


__all__ = [
    "OrganizationListCreateView",
    "OrganizationDetailView",
    "MembershipListCreateView",
    "MembershipDetailView",
    "MyMembershipsView",
    "InvitationCreateView",
    "InvitationDetailView",
    "InvitationAcceptView",
    "IsOrganizationMember",
]
