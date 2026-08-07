from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Issue JWT pair using email + password; return distinct error codes for UI."""

    default_error_messages = {
        "invalid_email": "No account found with this email.",
        "invalid_password": "Incorrect password.",
        "inactive_account": "This account is inactive.",
    }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        return token

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        password = attrs.get("password")

        if not email or password is None:
            raise serializers.ValidationError("Email and password are required.")

        normalized = User.objects.normalize_email(email)
        user = User.objects.filter(email__iexact=normalized).first()

        if user is None:
            raise AuthenticationFailed(
                detail={
                    "code": "invalid_email",
                    "detail": self.error_messages["invalid_email"],
                },
                code="invalid_email",
            )

        if not user.is_active:
            raise AuthenticationFailed(
                detail={
                    "code": "inactive_account",
                    "detail": self.error_messages["inactive_account"],
                },
                code="inactive_account",
            )

        if not user.check_password(password):
            raise AuthenticationFailed(
                detail={
                    "code": "invalid_password",
                    "detail": self.error_messages["invalid_password"],
                },
                code="invalid_password",
            )

        refresh = self.get_token(user)
        self.user = user
        update_last_login(None, user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data,
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "last_login",
            "created_at",
        )
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
