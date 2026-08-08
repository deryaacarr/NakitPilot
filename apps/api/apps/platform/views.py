"""EPIC 36 — platform console APIs."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform.audit import write_platform_audit
from apps.platform.flags import evaluate_flags, flag_payload, is_feature_enabled
from apps.platform.impersonation import (
    ImpersonationError,
    end_impersonation,
    get_active_session_from_token,
    start_impersonation,
)
from apps.platform.maintenance import maintenance_state
from apps.platform.models import (
    FeatureFlag,
    FeatureFlagKey,
    ImpersonationSession,
    MaintenanceWindow,
    SupportTicket,
)
from apps.platform.overview import build_platform_overview
from apps.platform.permissions import IsPlatformStaff
from apps.platform.serializers import (
    FeatureFlagSerializer,
    FeatureFlagUpsertSerializer,
    ImpersonationStartSerializer,
    MaintenanceCreateSerializer,
    MaintenanceWindowSerializer,
    SupportTicketCreateSerializer,
    SupportTicketSerializer,
)
from apps.organizations.tenancy import get_request_organization


class PlatformOverviewView(APIView):
    """NP-360 — aggregated console (no customer PII by default)."""

    permission_classes = [IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        include = str(request.query_params.get("include_customer_data") or "").lower() in {
            "1",
            "true",
            "yes",
        }
        # Even with flag, overview only returns aggregate counts — never PII rows.
        data = build_platform_overview(include_customer_data=include)
        write_platform_audit(
            actor=request.user,
            action="platform.overview.view",
            entity_type="PlatformOverview",
            summary="Super admin paneli görüntülendi",
            changes={"include_customer_data": include},
        )
        return Response(data)


class FeatureFlagListUpsertView(APIView):
    """NP-362."""

    permission_classes = [IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        # Ensure known keys exist as rows (disabled by default)
        for key, label in FeatureFlagKey.choices:
            FeatureFlag.objects.get_or_create(
                key=key, defaults={"description": label, "enabled": False}
            )
        flags = FeatureFlag.objects.all()
        return Response(
            {"results": [flag_payload(f) for f in flags], "known_keys": list(FeatureFlagKey.values)}
        )

    def post(self, request):
        ser = FeatureFlagUpsertSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        flag, created = FeatureFlag.objects.update_or_create(
            key=data["key"],
            defaults={
                "description": data.get("description") or "",
                "enabled": bool(data.get("enabled", False)),
                "environments": data.get("environments") or [],
                "plan_codes": [str(p).upper() for p in (data.get("plan_codes") or [])],
                "organization_ids": data.get("organization_ids") or [],
                "rollout_percentage": data.get("rollout_percentage", 100),
            },
        )
        write_platform_audit(
            actor=request.user,
            action="feature_flag.upsert",
            entity_type="FeatureFlag",
            entity_id=flag.id,
            summary=f"Flag {flag.key}={'on' if flag.enabled else 'off'}",
            changes=FeatureFlagSerializer(flag).data,
        )
        return Response(flag_payload(flag), status=status.HTTP_201_CREATED if created else 200)


class FeatureFlagEvaluateView(APIView):
    """Org-context evaluation for product UI (any authenticated member)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = get_request_organization(request)
        keys = request.query_params.getlist("key") or None
        return Response(
            {
                "flags": evaluate_flags(organization=org, user=request.user, keys=keys),
                "organization_id": org.pk if org else None,
            }
        )


class MaintenanceListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        rows = MaintenanceWindow.objects.select_related("organization").all()[:100]
        return Response({"results": MaintenanceWindowSerializer(rows, many=True).data})

    def post(self, request):
        ser = MaintenanceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        window = MaintenanceWindow.objects.create(
            scope=data["scope"],
            mode=data["mode"],
            organization_id=data.get("organization_id"),
            module=(data.get("module") or "").strip(),
            message=data.get("message") or "",
            starts_at=data.get("starts_at") or timezone.now(),
            ends_at=data.get("ends_at"),
            is_active=bool(data.get("is_active", True)),
            created_by=request.user,
        )
        write_platform_audit(
            actor=request.user,
            action="maintenance.create",
            entity_type="MaintenanceWindow",
            entity_id=window.id,
            organization=window.organization,
            summary=f"{window.scope}/{window.mode}",
            changes=MaintenanceWindowSerializer(window).data,
        )
        return Response(MaintenanceWindowSerializer(window).data, status=201)


class MaintenanceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformStaff]

    def patch(self, request, pk: int):
        window = MaintenanceWindow.objects.filter(pk=pk).first()
        if window is None:
            return Response(status=404)
        for field in ("is_active", "message", "ends_at", "mode", "module"):
            if field in request.data:
                setattr(window, field, request.data[field])
        window.save()
        write_platform_audit(
            actor=request.user,
            action="maintenance.update",
            entity_type="MaintenanceWindow",
            entity_id=window.id,
            summary="Bakım penceresi güncellendi",
            changes=MaintenanceWindowSerializer(window).data,
        )
        return Response(MaintenanceWindowSerializer(window).data)


class MaintenanceStatusView(APIView):
    """Public-ish for authenticated users — current maintenance for tenant."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = get_request_organization(request)
        state = maintenance_state(organization=org, path=request.query_params.get("path") or "")
        return Response({"maintenance": state})


class ImpersonationStartView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformStaff]

    def post(self, request):
        ser = ImpersonationStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            _session, tokens = start_impersonation(
                staff_user=request.user,
                target_user_id=ser.validated_data["user_id"],
                organization_id=ser.validated_data["organization_id"],
                reason=ser.validated_data["reason"],
                duration_minutes=ser.validated_data.get("duration_minutes") or 30,
                notify_target=bool(ser.validated_data.get("notify_target", True)),
            )
        except ImpersonationError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(tokens, status=201)


class ImpersonationEndView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session = get_active_session_from_token(getattr(request, "auth", None))
        if session is None:
            # Staff can end by session id
            session_id = request.data.get("session_id")
            if session_id and (request.user.is_staff or request.user.is_superuser):
                session = ImpersonationSession.objects.filter(pk=session_id).first()
        if session is None:
            return Response({"detail": "Aktif oturum yok."}, status=404)
        # Only staff who started it, or current impersonated token
        if not (
            request.user.is_staff
            or request.user.is_superuser
            or request.user.pk == session.target_user_id
        ):
            return Response(status=403)
        end_impersonation(session=session, ended_by=request.user, end_reason="manual")
        return Response({"ended": True, "session_id": str(session.id)})


class ImpersonationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = get_active_session_from_token(getattr(request, "auth", None))
        if session is None:
            return Response({"active": False})
        return Response(
            {
                "active": True,
                "session_id": str(session.id),
                "reason": session.reason,
                "expires_at": session.expires_at.isoformat(),
                "organization_id": session.organization_id,
                "staff_email": session.staff_user.email,
                "target_email": session.target_user.email,
                "banner": (
                    f"Destek modu aktif ({session.staff_user.email}). "
                    f"Hassas finansal işlemler engellenir. Bitiş: {session.expires_at.isoformat()}"
                ),
                "sensitive_writes_blocked": True,
            }
        )


class SupportTicketListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        rows = SupportTicket.objects.select_related("organization").all()[:100]
        return Response({"results": SupportTicketSerializer(rows, many=True).data})

    def post(self, request):
        ser = SupportTicketCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ticket = SupportTicket.objects.create(
            organization_id=ser.validated_data["organization_id"],
            subject=ser.validated_data["subject"],
            body=ser.validated_data.get("body") or "",
            status=ser.validated_data.get("status") or "OPEN",
            created_by=request.user,
        )
        return Response(SupportTicketSerializer(ticket).data, status=201)


class FeatureFlagCheckView(APIView):
    """Single key check for gated modules."""

    permission_classes = [IsAuthenticated]

    def get(self, request, key: str):
        org = get_request_organization(request)
        return Response(
            {
                "key": key,
                "enabled": is_feature_enabled(key, organization=org, user=request.user),
            }
        )
