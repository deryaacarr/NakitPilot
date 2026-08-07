"""Risk HTTP views (NP-104, NP-221, NP-222)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization
from apps.risk.enums import DEFAULT_TARGET_LABEL, RiskModelStatus
from apps.risk.models import RiskModelVersion, RiskPrediction
from apps.risk.registry import publish_model_version
from apps.risk.services import HISTORY_RANGES, customer_risk_history
from apps.risk.tasks import resolve_outcomes_task, train_models_task


class CustomerRiskHistoryView(APIView):
    """GET /api/customers/{id}/risk-history/?range=30d|90d|12m — NP-104."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        from apps.customers.models import Customer

        if not Customer.objects.for_organization(organization).filter(pk=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        range_key = (request.query_params.get("range") or "30d").strip()
        if range_key not in HISTORY_RANGES:
            return Response(
                {"detail": f"range must be one of: {', '.join(HISTORY_RANGES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(customer_risk_history(pk, range_key=range_key))


class CustomerRiskExplanationView(APIView):
    """GET /api/customers/{id}/risk-explanation/ — NP-224."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        from apps.customers.models import Customer
        from apps.risk.explain import explain_customer_risk

        if not Customer.objects.for_organization(organization).filter(pk=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(explain_customer_risk(pk))


class RiskModelListView(APIView):
    """GET /api/risk/models/ — list registry versions for the tenant."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        qs = RiskModelVersion.objects.filter(organization=organization).order_by(
            "-created_at"
        )[:50]
        results = [
            {
                "id": m.id,
                "name": m.name,
                "version": m.version,
                "algorithm": m.algorithm,
                "target_label": m.target_label,
                "status": m.status,
                "trained_at": m.trained_at.isoformat() if m.trained_at else None,
                "training_data_range": m.training_data_range,
                "metrics_json": m.metrics_json,
                "feature_list_json": m.feature_list_json,
                "comparison": m.comparison,
                "published_at": m.published_at.isoformat() if m.published_at else None,
            }
            for m in qs
        ]
        return Response({"results": results})


class RiskModelTrainView(APIView):
    """POST /api/risk/models/train/ — enqueue NP-222 pipeline."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        publish = bool(request.data.get("publish", False))
        synthetic = bool(request.data.get("synthetic", False))
        target_label = (request.data.get("target_label") or DEFAULT_TARGET_LABEL).strip()
        async_mode = request.data.get("async", True)

        if async_mode:
            async_result = train_models_task.delay(
                organization.id,
                target_label=target_label,
                publish=publish,
                synthetic=synthetic,
            )
            return Response(
                {"task_id": async_result.id, "status": "queued"},
                status=status.HTTP_202_ACCEPTED,
            )

        try:
            result = train_models_task(
                organization.id,
                target_label=target_label,
                publish=publish,
                synthetic=synthetic,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(result)


class RiskModelPublishView(APIView):
    """POST /api/risk/models/{id}/publish/ — activate a ready model."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        try:
            version = RiskModelVersion.objects.get(pk=pk, organization=organization)
        except RiskModelVersion.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if version.status not in (
            RiskModelStatus.CANDIDATE,
            RiskModelStatus.ACTIVE,
            RiskModelStatus.RETIRED,
        ):
            return Response(
                {"detail": f"Cannot activate status={version.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not version.artifact:
            return Response(
                {"detail": "Model has no artifact."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        publish_model_version(version)
        return Response(
            {
                "id": version.id,
                "version": version.version,
                "status": version.status,
                "published_at": version.published_at.isoformat()
                if version.published_at
                else None,
            }
        )


class RiskPredictionListView(APIView):
    """GET /api/risk/predictions/ — recent dataset rows (NP-221)."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        qs = (
            RiskPrediction.objects.filter(organization=organization)
            .select_related("model_version")
            .order_by("-prediction_date", "-id")[:100]
        )
        results = [
            {
                "id": p.id,
                "customer_id": p.customer_id,
                "feature_values": p.feature_values,
                "rule_score": p.rule_score,
                "model_score": p.model_score,
                "final_score": p.final_score,
                "prediction_date": p.prediction_date.isoformat(),
                "outcome_date": p.outcome_date.isoformat() if p.outcome_date else None,
                "actual_outcome": p.actual_outcome,
                "model_version": p.model_version.version if p.model_version else None,
            }
            for p in qs
        ]
        return Response({"results": results})


class RiskResolveOutcomesView(APIView):
    """POST /api/risk/predictions/resolve-outcomes/."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_SETTINGS
    write_permission = Permission.MANAGE_SETTINGS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        async_mode = request.data.get("async", True)
        if async_mode:
            async_result = resolve_outcomes_task.delay(organization_id=organization.id)
            return Response(
                {"task_id": async_result.id, "status": "queued"},
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(resolve_outcomes_task(organization_id=organization.id))


class RiskMonitoringDashboardView(APIView):
    """GET /api/risk/monitoring/ — NP-226 accuracy dashboard.

    Business metrics: any VIEW_REPORTS user.
    Technical metrics (precision/recall/AUC/calibration): MANAGE_SETTINGS only.
    """

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        from apps.organizations.roles import role_has_permission
        from apps.risk.monitoring import build_monitoring_dashboard

        membership = getattr(request, "membership", None)
        include_technical = False
        if membership is not None:
            include_technical = role_has_permission(
                membership.role, Permission.MANAGE_SETTINGS
            )

        lookback = request.query_params.get("lookback_days") or "180"
        try:
            lookback_days = max(30, min(730, int(lookback)))
        except ValueError:
            lookback_days = 180

        payload = build_monitoring_dashboard(
            organization,
            include_technical=include_technical,
            lookback_days=lookback_days,
        )
        payload["technical_visible"] = include_technical
        return Response(payload)


class CustomerSummaryView(APIView):
    """GET /api/customers/{id}/summary/ — NP-230 DB-sourced assistant summary."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)

        from apps.customers.models import Customer
        from apps.risk.summaries import summarize_customer_id

        if not Customer.objects.for_organization(organization).filter(pk=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(summarize_customer_id(pk, organization=organization))
