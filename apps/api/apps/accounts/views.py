from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    LogoutSerializer,
    UserSerializer,
)
from apps.security.throttles import AuthLoginThrottle, AuthRefreshThrottle

User = get_user_model()


class LoginView(APIView):
    """POST /api/auth/login — email + password → access/refresh tokens."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [AuthLoginThrottle]

    def post(self, request):
        serializer = EmailTokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                payload = detail
            else:
                payload = {"code": getattr(exc, "default_code", "authentication_failed"), "detail": detail}
            return Response(payload, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh — rotate/renew access (and refresh if configured)."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRefreshThrottle]


class LogoutView(APIView):
    """POST /api/auth/logout — blacklist refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me — current authenticated user."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """POST /api/auth/change-password — update password for current user."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
