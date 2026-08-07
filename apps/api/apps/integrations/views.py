from django.db.models import Exists, OuterRef
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations import connection_actions
from apps.integrations.connection_actions import ConnectionActionError
from apps.integrations.conflicts import ConflictResolutionError, resolve_conflict
from apps.integrations.connectors import list_providers
from apps.integrations.models import IntegrationConnection, IntegrationCredential, SyncConflict
from apps.integrations.monitoring import build_monitoring_payload
from apps.integrations.serializers import (
    CompanyOptionSerializer,
    IntegrationConnectionSerializer,
    IntegrationCredentialStatusSerializer,
    IntegrationCredentialWriteSerializer,
    ProviderSerializer,
    ResolveConflictSerializer,
    SelectCompanySerializer,
    StartSyncSerializer,
    SyncConflictSerializer,
    SyncJobSerializer,
    SyncSettingsSerializer,
)
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


_TENANT_PERMS = [
    IsAuthenticated,
    RequireTenantContextPermission,
    HasOrganizationPermission,
]


class IntegrationConnectionListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = IntegrationConnectionSerializer
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    pagination_class = StandardResultsSetPagination
    queryset = IntegrationConnection.objects.all()

    def get_queryset(self):
        cred_exists = IntegrationCredential.objects.filter(connection_id=OuterRef("pk"))
        return (
            super()
            .get_queryset()
            .select_related("credential")
            .annotate(_has_credentials=Exists(cred_exists))
            .all()
        )


class IntegrationConnectionDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = IntegrationConnectionSerializer
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    queryset = IntegrationConnection.objects.select_related("credential").all()


class IntegrationCredentialView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    queryset = IntegrationConnection.objects.select_related("credential").all()
    lookup_url_kwarg = "connection_id"

    def get_connection(self) -> IntegrationConnection:
        return self.get_object()

    def get(self, request, *args, **kwargs):
        connection = self.get_connection()
        try:
            credential = connection.credential
        except IntegrationCredential.DoesNotExist:
            credential = None
        payload = {
            "has_credentials": credential is not None,
            "key_hint": credential.key_hint if credential else "",
            "rotated_at": credential.rotated_at if credential else None,
        }
        return Response(IntegrationCredentialStatusSerializer(payload).data)

    def put(self, request, *args, **kwargs):
        connection = self.get_connection()
        serializer = IntegrationCredentialWriteSerializer(
            data=request.data,
            context={"connection": connection, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        credential = serializer.save()
        payload = {
            "has_credentials": True,
            "key_hint": credential.key_hint,
            "rotated_at": credential.rotated_at,
        }
        return Response(IntegrationCredentialStatusSerializer(payload).data)


class IntegrationProviderListView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS

    def get(self, request, *args, **kwargs):
        return Response(ProviderSerializer(list_providers(), many=True).data)


class _ConnectionActionMixin(TenantQuerysetMixin):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    queryset = IntegrationConnection.objects.select_related("credential").all()
    lookup_url_kwarg = "connection_id"

    def get_connection(self) -> IntegrationConnection:
        return self.get_object()


class IntegrationTestConnectionView(_ConnectionActionMixin, generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        connection = self.get_connection()
        try:
            result = connection_actions.test_connection(connection)
        except ConnectionActionError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        connection.refresh_from_db()
        http_status = status.HTTP_200_OK if result.get("ok") else status.HTTP_400_BAD_REQUEST
        return Response(
            {
                "result": result,
                "connection": IntegrationConnectionSerializer(connection).data,
            },
            status=http_status,
        )


class IntegrationCompaniesView(_ConnectionActionMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        connection = self.get_connection()
        try:
            companies = connection_actions.list_companies(connection)
        except ConnectionActionError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        return Response(CompanyOptionSerializer(companies, many=True).data)


class IntegrationSelectCompanyView(_ConnectionActionMixin, generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        connection = self.get_connection()
        serializer = SelectCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connection = connection_actions.select_company(
                connection,
                external_company_id=serializer.validated_data["external_company_id"],
                external_company_name=serializer.validated_data.get("external_company_name", ""),
            )
        except ConnectionActionError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        return Response(IntegrationConnectionSerializer(connection).data)


class IntegrationSyncSettingsView(_ConnectionActionMixin, generics.GenericAPIView):
    def patch(self, request, *args, **kwargs):
        connection = self.get_connection()
        serializer = SyncSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connection = connection_actions.update_sync_settings(
                connection,
                sync_frequency=serializer.validated_data["sync_frequency"],
                settings_json=serializer.validated_data.get("settings_json"),
            )
        except ConnectionActionError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        return Response(IntegrationConnectionSerializer(connection).data)


class IntegrationStartSyncView(_ConnectionActionMixin, generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        connection = self.get_connection()
        serializer = StartSyncSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            job = connection_actions.start_sync(
                connection,
                job_type=serializer.validated_data.get("job_type") or "manual",
            )
        except ConnectionActionError as exc:
            connection.refresh_from_db()
            return Response(
                {
                    "detail": str(exc),
                    "connection": IntegrationConnectionSerializer(connection).data,
                },
                status=exc.status_code,
            )
        connection.refresh_from_db()
        return Response(
            {
                "job": SyncJobSerializer(job).data,
                "connection": IntegrationConnectionSerializer(connection).data,
            },
            status=status.HTTP_201_CREATED,
        )


class IntegrationMonitoringView(_ConnectionActionMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        connection = self.get_connection()
        return Response(build_monitoring_payload(connection))


class IntegrationConflictListView(_ConnectionActionMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        connection = self.get_connection()
        qs = SyncConflict.objects.filter(connection=connection).order_by("-created_at")
        status_filter = request.query_params.get("status", "open").strip()
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        return Response(SyncConflictSerializer(qs[:100], many=True).data)


class IntegrationConflictResolveView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    queryset = SyncConflict.objects.select_related("connection").all()
    lookup_url_kwarg = "conflict_id"

    def get_queryset(self):
        return super().get_queryset().filter(connection_id=self.kwargs["connection_id"])

    def post(self, request, *args, **kwargs):
        conflict = self.get_object()
        serializer = ResolveConflictSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            conflict = resolve_conflict(
                conflict,
                resolution=serializer.validated_data["resolution"],
                user=request.user,
                field=serializer.validated_data.get("field") or "",
            )
        except ConflictResolutionError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        return Response(SyncConflictSerializer(conflict).data)
