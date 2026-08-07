"""EPIC 32/33 ops API."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.read_models import refresh_organization_daily_metrics
from apps.ops.alerts import ensure_default_rules, evaluate_alerts
from apps.ops.archive import ARCHIVABLE, archive_entity
from apps.ops.loadtest import PROFILES, run_benchmark
from apps.ops.metrics import business_metrics, technical_metrics
from apps.ops.models import AlertEvent, AlertRule, LoadTestRun
from apps.ops.status import status_payload
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization

def _runbook_dir() -> Path:
    base = Path(settings.BASE_DIR).resolve()
    candidates = [
        base.parent.parent / "docs" / "ops" / "runbooks",  # .../NakitPilot/docs/...
        base.parent / "docs" / "ops" / "runbooks",
        Path.cwd() / "docs" / "ops" / "runbooks",
        Path.cwd().parent / "docs" / "ops" / "runbooks",
        Path.cwd().parent.parent / "docs" / "ops" / "runbooks",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


RUNBOOK_DIR = _runbook_dir()


class TechnicalMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response(technical_metrics())


class BusinessMetricsView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        org = get_request_organization(request)
        return Response(business_metrics(org))


class AlertRulesView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        ensure_default_rules()
        rules = AlertRule.objects.all()
        return Response(
            {
                "results": [
                    {
                        "key": r.key,
                        "name": r.name,
                        "severity": r.severity,
                        "metric_name": r.metric_name,
                        "operator": r.operator,
                        "threshold": r.threshold,
                        "runbook_key": r.runbook_key,
                        "is_enabled": r.is_enabled,
                    }
                    for r in rules
                ]
            }
        )


class AlertEvaluateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        return Response({"fired": evaluate_alerts()})


class AlertEventsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        rows = AlertEvent.objects.select_related("rule").order_by("-created_at")[:50]
        return Response(
            {
                "results": [
                    {
                        "id": e.id,
                        "rule": e.rule.key,
                        "message": e.message,
                        "value": e.value,
                        "is_active": e.is_active,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in rows
                ]
            }
        )


class StatusPageView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(status_payload())


class ArchiveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response({"entities": list(ARCHIVABLE.keys())})

    def post(self, request):
        entity = (request.data.get("entity") or "").strip()
        days = int(request.data.get("older_than_days") or 365)
        dry = request.data.get("dry_run", True)
        if isinstance(dry, str):
            dry = dry.lower() not in {"0", "false", "no"}
        try:
            run = archive_entity(
                entity,
                older_than_days=days,
                dry_run=bool(dry),
                user=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "id": run.id,
                "entity": run.entity,
                "rows_moved": run.rows_moved,
                "dry_run": run.dry_run,
                "details": run.details,
            }
        )


class LoadTestView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        org = get_request_organization(request)
        rows = LoadTestRun.objects.filter(organization=org).order_by("-created_at")[:10]
        return Response(
            {
                "profiles": PROFILES,
                "results": [
                    {
                        "id": r.id,
                        "profile": r.profile,
                        "customers": r.customers,
                        "invoices": r.invoices,
                        "activities": r.activities,
                        "timings_ms": r.timings_ms,
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in rows
                ],
            }
        )

    def post(self, request):
        org = get_request_organization(request)
        profile = (request.data.get("profile") or "small").strip()
        if profile == "full" and not request.data.get("confirm_full"):
            return Response(
                {"detail": "full profil için confirm_full=true gerekli (yıkıcı hacim)."},
                status=400,
            )
        try:
            run = run_benchmark(org, profile=profile, user=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "id": run.id,
                "profile": run.profile,
                "timings_ms": run.timings_ms,
                "customers": run.customers,
                "invoices": run.invoices,
                "activities": run.activities,
            },
            status=201,
        )


class RefreshReadModelView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        org = get_request_organization(request)
        metrics = refresh_organization_daily_metrics(org.id)
        return Response(
            {
                "day": metrics.day.isoformat(),
                "open_balance": str(metrics.open_balance),
                "overdue_balance": str(metrics.overdue_balance),
                "updated_at": metrics.updated_at.isoformat(),
            }
        )


class RunbookListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        root = RUNBOOK_DIR
        files = []
        if root.exists():
            for p in sorted(root.glob("*.md")):
                files.append({"key": p.stem, "title": p.stem, "path": str(p.name)})
        return Response({"results": files})


class RunbookDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, key: str):
        path = RUNBOOK_DIR / f"{key}.md"
        if not path.exists():
            return Response({"detail": "Not found"}, status=404)
        return Response({"key": key, "content": path.read_text(encoding="utf-8")})
