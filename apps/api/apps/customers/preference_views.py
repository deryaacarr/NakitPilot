"""NP-243 / NP-244 — communication preferences and frequency check API."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.messaging.frequency import check_frequency
from apps.messaging.preferences import get_or_create_preference, serialize_preference
from apps.messaging.serializers import CommunicationPreferenceSerializer
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class CustomerCommunicationPreferenceView(APIView):
    """GET/PUT /api/customers/{id}/communication-preferences/ (NP-243)."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def _customer(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return None, Response({"detail": "Organization required."}, status=400)
        customer = Customer.objects.for_organization(organization).filter(pk=pk).first()
        if customer is None:
            return None, Response({"detail": "Not found."}, status=404)
        return customer, None

    def get(self, request, pk: int):
        customer, err = self._customer(request, pk)
        if err:
            return err
        pref = get_or_create_preference(customer)
        return Response(serialize_preference(pref))

    def put(self, request, pk: int):
        customer, err = self._customer(request, pk)
        if err:
            return err
        ser = CommunicationPreferenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pref = get_or_create_preference(customer)
        for key, value in ser.validated_data.items():
            setattr(pref, key, value)
        pref.save()
        return Response(serialize_preference(pref))


class CustomerFrequencyCheckView(APIView):
    """GET /api/customers/{id}/communication-frequency/ (NP-244)."""

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
        customer = Customer.objects.for_organization(organization).filter(pk=pk).first()
        if customer is None:
            return Response({"detail": "Not found."}, status=404)
        is_automatic = (request.query_params.get("is_automatic") or "true").lower()
        automatic = is_automatic not in {"0", "false", "no"}
        result = check_frequency(customer, is_automatic=automatic)
        return Response(result.as_dict())
