from rest_framework.permissions import BasePermission


class IsPlatformStaff(BasePermission):
    """Django staff (or superuser) — platform console only."""

    message = "Platform personeli yetkisi gerekli."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
        )
