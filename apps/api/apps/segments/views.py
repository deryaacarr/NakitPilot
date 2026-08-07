"""NP-260–263 HTTP API."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization
from apps.segments.models import CollectionStrategy, CustomerSegment, MessageABTest
from apps.segments.rules import RuleError, evaluate_segment_customers, validate_rules
from apps.segments.services import (
    assign_ab_variants,
    create_segment,
    ensure_default_segments,
    serialize_ab_test,
    serialize_segment,
    serialize_strategy,
)


class SegmentListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ensure_default_segments(organization)
        qs = CustomerSegment.objects.for_organization(organization).filter(is_active=True)
        return Response({"results": [serialize_segment(s) for s in qs]})

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name required"}, status=400)
        try:
            seg = create_segment(
                organization,
                name=name,
                rules=request.data.get("rules") or {},
                slug=(request.data.get("slug") or "").strip(),
                description=(request.data.get("description") or "").strip(),
                actor=request.user,
            )
        except RuleError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serialize_segment(seg), status=status.HTTP_201_CREATED)


class SegmentDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        seg = CustomerSegment.objects.for_organization(organization).filter(pk=pk).first()
        if seg is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(serialize_segment(seg, with_count=True))

    def patch(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        seg = CustomerSegment.objects.for_organization(organization).filter(pk=pk).first()
        if seg is None:
            return Response({"detail": "Not found."}, status=404)
        if "name" in request.data:
            seg.name = (request.data.get("name") or seg.name).strip()
        if "description" in request.data:
            seg.description = request.data.get("description") or ""
        if "rules" in request.data:
            try:
                seg.rules = validate_rules(request.data.get("rules") or {})
            except RuleError as exc:
                return Response(
                    {"detail": exc.message, "code": exc.code},
                    status=400,
                )
        if "is_active" in request.data:
            seg.is_active = bool(request.data.get("is_active"))
        seg.save()
        return Response(serialize_segment(seg, with_count=True))


class SegmentPreviewView(APIView):
    """POST rules → matching customers (NP-261)."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        rules = request.data.get("rules") or {}
        try:
            members = evaluate_segment_customers(organization, rules)
        except RuleError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=400,
            )
        return Response(
            {
                "count": len(members),
                "customer_ids": [c.id for c in members[:200]],
                "customers": [
                    {"id": c.id, "name": c.name, "risk_status": c.risk_status}
                    for c in members[:50]
                ],
            }
        )


class StrategyListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ensure_default_segments(organization)
        qs = CollectionStrategy.objects.for_organization(organization).filter(
            is_active=True
        )
        segment_id = request.query_params.get("segment_id")
        if segment_id:
            qs = qs.filter(segment_id=segment_id)
        return Response({"results": [serialize_strategy(s) for s in qs]})

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        segment_id = request.data.get("segment_id")
        segment = (
            CustomerSegment.objects.for_organization(organization)
            .filter(pk=segment_id)
            .first()
        )
        if segment is None:
            return Response({"detail": "segment_id required"}, status=400)
        s = CollectionStrategy.objects.create(
            organization=organization,
            segment=segment,
            name=(request.data.get("name") or f"{segment.name} stratejisi").strip(),
            steps=request.data.get("steps") or [],
        )
        return Response(serialize_strategy(s), status=201)


class StrategyDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        s = CollectionStrategy.objects.for_organization(organization).filter(pk=pk).first()
        if s is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(serialize_strategy(s))

    def patch(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        s = CollectionStrategy.objects.for_organization(organization).filter(pk=pk).first()
        if s is None:
            return Response({"detail": "Not found."}, status=404)
        if "name" in request.data:
            s.name = request.data["name"]
        if "steps" in request.data:
            s.steps = request.data["steps"] or []
        if "is_active" in request.data:
            s.is_active = bool(request.data["is_active"])
        s.save()
        return Response(serialize_strategy(s))


class ABTestListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        qs = MessageABTest.objects.for_organization(organization)
        return Response(
            {"results": [serialize_ab_test(t, with_metrics=True) for t in qs[:50]]}
        )

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name required"}, status=400)
        test = MessageABTest.objects.create(
            organization=organization,
            name=name,
            segment_id=request.data.get("segment_id"),
            variant_a=request.data.get("variant_a")
            or {
                "subject": "",
                "tone": "polite",
                "send_hour": 10,
                "channel": "EMAIL",
                "reminder_interval_days": 7,
            },
            variant_b=request.data.get("variant_b")
            or {
                "subject": "",
                "tone": "firm",
                "send_hour": 14,
                "channel": "WHATSAPP",
                "reminder_interval_days": 3,
            },
            created_by=request.user,
        )
        return Response(serialize_ab_test(test), status=201)


class ABTestDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        test = MessageABTest.objects.for_organization(organization).filter(pk=pk).first()
        if test is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(serialize_ab_test(test, with_metrics=True))


class ABTestAssignView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        test = MessageABTest.objects.for_organization(organization).filter(pk=pk).first()
        if test is None:
            return Response({"detail": "Not found."}, status=404)
        customer_ids = request.data.get("customer_ids")
        if not customer_ids and test.segment_id:
            members = evaluate_segment_customers(
                organization, test.segment.rules or {}
            )
            customer_ids = [c.id for c in members]
        if not customer_ids:
            return Response({"detail": "customer_ids or segment required"}, status=400)
        assigned = assign_ab_variants(test, list(customer_ids))
        return Response(
            {
                "assigned": assigned,
                "metrics": serialize_ab_test(test, with_metrics=True)["metrics"],
            }
        )
