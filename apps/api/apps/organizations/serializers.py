from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organizations.invitations import build_invite_link
from apps.organizations.models import Invitation, Membership, Organization, Role

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "tax_number",
            "phone",
            "email",
            "default_currency",
            "timezone",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
        }

    def validate_default_currency(self, value: str) -> str:
        value = value.upper().strip()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code.")
        return value

    def validate_slug(self, value: str) -> str:
        return value.strip().lower() if value else value


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.filter(is_active=True),
    )

    class Meta:
        model = Membership
        fields = (
            "id",
            "organization",
            "user_id",
            "user_email",
            "role",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "organization", "user_email", "created_at")

    def validate_role(self, value: str) -> str:
        if value not in Role.values:
            raise serializers.ValidationError("Invalid role.")
        return value


class MembershipCreateSerializer(MembershipSerializer):
    """Create membership; organization comes from URL."""

    class Meta(MembershipSerializer.Meta):
        fields = (
            "id",
            "user_id",
            "user_email",
            "role",
            "is_active",
            "created_at",
        )


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices, default=Role.VIEWER)

    def validate_role(self, value: str) -> str:
        if value == Role.OWNER:
            raise serializers.ValidationError("Cannot invite a user as OWNER.")
        return value


class InvitationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    invite_link = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = (
            "id",
            "organization",
            "organization_name",
            "email",
            "role",
            "token",
            "status",
            "expires_at",
            "accepted_at",
            "created_at",
            "invite_link",
        )
        read_only_fields = fields

    def get_invite_link(self, obj: Invitation) -> str:
        return build_invite_link(obj.token)


class InvitationPublicSerializer(serializers.ModelSerializer):
    """Safe payload for unauthenticated invite preview."""

    organization_name = serializers.CharField(source="organization.name", read_only=True)
    invite_link = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = (
            "email",
            "role",
            "status",
            "expires_at",
            "organization_name",
            "invite_link",
        )

    def get_invite_link(self, obj: Invitation) -> str:
        return build_invite_link(obj.token)


class InvitationAcceptSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
