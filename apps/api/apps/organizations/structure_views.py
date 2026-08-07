"""NP-300–302 API — custom roles, branches, teams, assignments."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.subscription_service import Feature, can_use
from apps.organizations.custom_roles import ensure_role_templates, role_payload
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.resource_scope import get_resource_rules
from apps.organizations.roles import Permission
from apps.organizations.structure import Branch, CustomRole, CustomerAssignment, Team, TeamMembership
from apps.organizations.tenancy import get_request_organization


class CustomRoleListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_USERS
    write_permission = Permission.MANAGE_USERS

    def get(self, request):
        org = get_request_organization(request)
        if org is None:
            return Response({"detail": "Organization required."}, status=400)
        ensure_role_templates(org)
        roles = CustomRole.objects.filter(organization=org, is_active=True)
        return Response({"results": [role_payload(r) for r in roles]})

    def post(self, request):
        org = get_request_organization(request)
        if org is None:
            return Response({"detail": "Organization required."}, status=400)
        if not can_use(org, Feature.CUSTOM_ROLES).allowed:
            return Response(
                {"detail": "Özel roller Business/Enterprise paketinde kullanılabilir."},
                status=403,
            )
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name required"}, status=400)
        role = CustomRole.objects.create(
            organization=org,
            name=name,
            description=request.data.get("description") or "",
            permissions=request.data.get("permissions") or [],
            resource_rules=request.data.get("resource_rules") or {},
        )
        return Response(role_payload(role), status=status.HTTP_201_CREATED)


class CustomRoleDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_USERS
    write_permission = Permission.MANAGE_USERS

    def patch(self, request, pk: int):
        org = get_request_organization(request)
        role = CustomRole.objects.filter(organization=org, pk=pk).first()
        if role is None:
            return Response({"detail": "Not found"}, status=404)
        for field in ("name", "description", "permissions", "resource_rules", "is_active"):
            if field in request.data:
                setattr(role, field, request.data[field])
        role.save()
        return Response(role_payload(role))

    def delete(self, request, pk: int):
        org = get_request_organization(request)
        role = CustomRole.objects.filter(organization=org, pk=pk).first()
        if role is None:
            return Response({"detail": "Not found"}, status=404)
        if role.is_system_template:
            role.is_active = False
            role.save(update_fields=["is_active", "updated_at"])
        else:
            role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyResourceRulesView(APIView):
    """NP-301 — current membership resource rules."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request):
        membership = getattr(request, "membership", None)
        if membership is None:
            from apps.organizations.services import get_active_membership

            org = get_request_organization(request)
            membership = get_active_membership(request.user, org) if org else None
        if membership is None:
            return Response({"detail": "Membership required."}, status=400)
        return Response(
            {
                "role": membership.role,
                "custom_role_id": membership.custom_role_id,
                "branch_id": membership.branch_id,
                "resource_rules": get_resource_rules(membership),
            }
        )


class BranchListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_USERS
    write_permission = Permission.MANAGE_USERS

    def get(self, request):
        org = get_request_organization(request)
        if org is None:
            return Response({"detail": "Organization required."}, status=400)
        branches = Branch.objects.filter(organization=org, is_active=True)
        return Response(
            {
                "results": [
                    {"id": b.id, "name": b.name, "code": b.code, "city": b.city}
                    for b in branches
                ]
            }
        )

    def post(self, request):
        org = get_request_organization(request)
        if org is None:
            return Response({"detail": "Organization required."}, status=400)
        if not can_use(org, Feature.BRANCHES).allowed:
            return Response({"detail": "Şube yapısı Business/Enterprise gerektirir."}, status=403)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name required"}, status=400)
        b = Branch.objects.create(
            organization=org,
            name=name,
            code=(request.data.get("code") or "")[:32],
            city=(request.data.get("city") or "")[:100],
        )
        return Response(
            {"id": b.id, "name": b.name, "code": b.code, "city": b.city},
            status=201,
        )


class TeamListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.MANAGE_USERS
    write_permission = Permission.MANAGE_USERS

    def get(self, request):
        org = get_request_organization(request)
        teams = Team.objects.filter(organization=org, is_active=True)
        return Response(
            {
                "results": [
                    {"id": t.id, "name": t.name, "branch_id": t.branch_id}
                    for t in teams
                ]
            }
        )

    def post(self, request):
        org = get_request_organization(request)
        if not can_use(org, Feature.BRANCHES).allowed:
            return Response({"detail": "Ekip yapısı Business/Enterprise gerektirir."}, status=403)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name required"}, status=400)
        t = Team.objects.create(
            organization=org,
            name=name,
            branch_id=request.data.get("branch_id") or None,
        )
        return Response({"id": t.id, "name": t.name, "branch_id": t.branch_id}, status=201)


class TeamMemberView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_USERS

    def post(self, request, team_id: int):
        org = get_request_organization(request)
        team = Team.objects.filter(organization=org, pk=team_id).first()
        if team is None:
            return Response({"detail": "Not found"}, status=404)
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id required"}, status=400)
        tm, _ = TeamMembership.objects.get_or_create(
            organization=org,
            team=team,
            user_id=user_id,
            defaults={"is_lead": bool(request.data.get("is_lead"))},
        )
        return Response({"id": tm.id, "team_id": team.id, "user_id": tm.user_id}, status=201)


class CustomerAssignmentView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.MANAGE_USERS

    def post(self, request):
        org = get_request_organization(request)
        customer_id = request.data.get("customer_id")
        if not customer_id:
            return Response({"detail": "customer_id required"}, status=400)
        a = CustomerAssignment.objects.create(
            organization=org,
            customer_id=customer_id,
            user_id=request.data.get("user_id") or None,
            team_id=request.data.get("team_id") or None,
            branch_id=request.data.get("branch_id") or None,
        )
        return Response(
            {
                "id": a.id,
                "customer_id": a.customer_id,
                "user_id": a.user_id,
                "team_id": a.team_id,
                "branch_id": a.branch_id,
            },
            status=201,
        )
