from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_keys.models import ApiKey
from apps.api_keys.scopes import AVAILABLE_SCOPES
from apps.api_keys.serializers import ApiKeyCreateSerializer, ApiKeySerializer
from apps.api_keys.services import ApiKeyError, create_api_key, revoke_api_key
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission

_TENANT_PERMS = [
    IsAuthenticated,
    RequireTenantContextPermission,
    HasOrganizationPermission,
]


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ApiKeyScopeListView(APIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "scopes": [
                    {"value": scope, "label": scope}
                    for scope in AVAILABLE_SCOPES
                ]
            }
        )


class ApiKeyListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    pagination_class = StandardResultsSetPagination
    queryset = ApiKey.objects.select_related("created_by").all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ApiKeyCreateSerializer
        return ApiKeySerializer

    def create(self, request, *args, **kwargs):
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            api_key, raw_key = create_api_key(
                organization=self.get_current_organization(),
                name=serializer.validated_data["name"],
                scopes=serializer.validated_data["scopes"],
                created_by=request.user,
            )
        except ApiKeyError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        payload = ApiKeySerializer(api_key).data
        payload["key"] = raw_key
        return Response(payload, status=status.HTTP_201_CREATED)


class ApiKeyDetailView(TenantQuerysetMixin, generics.RetrieveAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    serializer_class = ApiKeySerializer
    queryset = ApiKey.objects.select_related("created_by").all()


class ApiKeyRevokeView(TenantQuerysetMixin, generics.GenericAPIView):
    permission_classes = _TENANT_PERMS
    required_permission = Permission.MANAGE_SETTINGS
    queryset = ApiKey.objects.select_related("created_by").all()

    def post(self, request, *args, **kwargs):
        api_key = self.get_object()
        try:
            api_key = revoke_api_key(api_key)
        except ApiKeyError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        return Response(ApiKeySerializer(api_key).data)
