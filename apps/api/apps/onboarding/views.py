"""EPIC 29 — onboarding API (NP-290–294)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.analytics import AnalyticsError, track_event
from apps.onboarding.guidance import guidance_payload
from apps.onboarding.models import OnboardingStep, WIZARD_STEPS
from apps.onboarding.progress import compute_score, ensure_state
from apps.onboarding.sample_data import disable_sample_data, enable_sample_data, sample_summary
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class OnboardingStateView(APIView):
    """NP-290 wizard state."""

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
        state = ensure_state(organization)
        score = compute_score(organization)
        return Response(
            {
                "current_step": state.current_step,
                "completed_steps": state.completed_steps or [],
                "wizard_completed": state.wizard_completed,
                "sample_data_enabled": state.sample_data_enabled,
                "steps": [
                    {"key": s.value, "label": s.label} for s in OnboardingStep
                ],
                "progress": score,
            }
        )

    def patch(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        state = ensure_state(organization)
        step = (request.data.get("current_step") or "").strip()
        if step and step not in WIZARD_STEPS:
            return Response({"detail": "Geçersiz adım."}, status=400)
        completed = request.data.get("completed_steps")
        if step:
            state.current_step = step
            done = list(state.completed_steps or [])
            if step not in done:
                # mark previous as done when advancing
                idx = WIZARD_STEPS.index(step)
                for prev in WIZARD_STEPS[:idx]:
                    if prev not in done:
                        done.append(prev)
                state.completed_steps = done
        if isinstance(completed, list):
            state.completed_steps = [s for s in completed if s in WIZARD_STEPS]
        if request.data.get("wizard_completed") is True or state.current_step == OnboardingStep.DASHBOARD:
            if request.data.get("wizard_completed") is True:
                state.wizard_completed = True
                state.completed_steps = list(WIZARD_STEPS)
                try:
                    track_event(organization, "wizard_completed", {"source": "wizard"})
                except AnalyticsError:
                    pass
        # Company step → flag
        if OnboardingStep.COMPANY in (state.completed_steps or []):
            flags = dict(state.flags or {})
            flags["company_completed"] = True
            state.flags = flags
        state.save()
        return Response(
            {
                "current_step": state.current_step,
                "completed_steps": state.completed_steps,
                "wizard_completed": state.wizard_completed,
                "progress": compute_score(organization),
            }
        )


class OnboardingProgressView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        return Response(compute_score(organization))


class SampleDataView(APIView):
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
        return Response(sample_summary(organization))

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        result = enable_sample_data(organization)
        try:
            track_event(organization, "sample_data_enabled", {"customers": result.get("customers", 0)})
        except AnalyticsError:
            pass
        return Response(result, status=status.HTTP_201_CREATED)

    def delete(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        return Response(disable_sample_data(organization))


class GuidanceView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        return Response(guidance_payload(organization))


class AnalyticsEventView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.VIEW_REPORTS

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        try:
            event = track_event(
                organization,
                request.data.get("event_name") or "",
                request.data.get("properties") if isinstance(request.data.get("properties"), dict) else {},
            )
        except AnalyticsError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=400)
        return Response(
            {
                "id": event.id,
                "event_name": event.event_name,
                "properties": event.properties,
                "occurred_at": event.occurred_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )
