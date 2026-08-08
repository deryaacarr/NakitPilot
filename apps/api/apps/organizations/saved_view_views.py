"""HTTP API for saved table views (NP-402)."""

from __future__ import annotations

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer
from rest_framework.views import APIView

from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.saved_views import SavedTableView
from apps.organizations.tenancy import get_request_organization


class SavedTableViewSerializer(ModelSerializer):
    class Meta:
        model = SavedTableView
        fields = (
            "id",
            "organization",
            "resource",
            "name",
            "filters",
            "hidden_columns",
            "sort",
            "is_default",
            "is_shared",
            "share_token",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "share_token",
            "created_by",
            "created_at",
            "updated_at",
        )


class SavedTableViewListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    """GET/POST /api/saved-views/"""

    serializer_class = SavedTableViewSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS
    queryset = SavedTableView.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        resource = (self.request.query_params.get("resource") or "").strip()
        if resource:
            qs = qs.filter(resource=resource)
        # Own views + shared team views
        user = self.request.user
        from django.db.models import Q

        return qs.filter(Q(created_by=user) | Q(is_shared=True)).distinct()

    def perform_create(self, serializer):
        org = self.get_current_organization()
        view = serializer.save(organization=org, created_by=self.request.user)
        if view.is_shared:
            view.ensure_share_token()
        if view.is_default:
            SavedTableView.set_default(
                organization_id=org.id,
                resource=view.resource,
                view_id=view.id,
                user_id=self.request.user.id,
            )


class SavedTableViewDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/saved-views/{id}/"""

    serializer_class = SavedTableViewSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS
    queryset = SavedTableView.objects.all()
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_update(self, serializer):
        view = serializer.save()
        if view.is_shared:
            view.ensure_share_token()
        if view.is_default:
            SavedTableView.set_default(
                organization_id=view.organization_id,
                resource=view.resource,
                view_id=view.id,
                user_id=self.request.user.id,
            )


class SavedTableViewSetDefaultView(TenantQuerysetMixin, APIView):
    """POST /api/saved-views/{id}/set-default/"""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    write_permission = Permission.VIEW_REPORTS
    read_permission = Permission.VIEW_REPORTS

    def post(self, request, pk: int):
        org = get_request_organization(request)
        try:
            view = SavedTableView.set_default(
                organization_id=org.id,
                resource=SavedTableView.objects.get(pk=pk, organization=org).resource,
                view_id=pk,
                user_id=request.user.id,
            )
        except SavedTableView.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SavedTableViewSerializer(view).data)


class SavedTableViewByTokenView(APIView):
    """GET /api/saved-views/by-token/<token>/ — resolve shared link."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS

    def get(self, request, token: str):
        org = get_request_organization(request)
        try:
            view = SavedTableView.objects.get(
                organization=org, share_token=token, is_shared=True
            )
        except SavedTableView.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SavedTableViewSerializer(view).data)
