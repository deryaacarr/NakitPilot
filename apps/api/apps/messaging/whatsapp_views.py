"""NP-242 / NP-245 — WhatsApp HTTP API."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.messaging.models import (
    InboundWhatsApp,
    OutboundWhatsApp,
    ResponseClassification,
    WhatsAppApprovedTemplate,
    WhatsAppOptOut,
    WhatsAppTemplateStatus,
)
from apps.messaging.serializers import (
    WhatsAppBulkSendSerializer,
    WhatsAppClassifySerializer,
    WhatsAppInboundSerializer,
    WhatsAppProviderConfigSerializer,
    WhatsAppSendSerializer,
    WhatsAppStatusUpdateSerializer,
    WhatsAppTemplateSerializer,
)
from apps.messaging.services import MessagingError
from apps.messaging.whatsapp_service import (
    bulk_send_whatsapp,
    clear_opt_out,
    confirm_classification,
    create_and_send_whatsapp,
    get_provider_config,
    ingest_inbound_whatsapp,
    provider_config_public,
    serialize_inbound_wa,
    serialize_outbound_wa,
    serialize_wa_template,
    update_message_status,
    upsert_provider_config,
)
from apps.organizations.mixins import RequireTenantContextPermission
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class WhatsAppTemplateListCreateView(APIView):
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
        qs = WhatsAppApprovedTemplate.objects.for_organization(organization).order_by(
            "name"
        )
        status_filter = (request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        approved_only = (request.query_params.get("approved") or "").lower()
        if approved_only in {"1", "true"}:
            qs = qs.filter(status=WhatsAppTemplateStatus.APPROVED)
        return Response({"results": [serialize_wa_template(t) for t in qs]})

    def post(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ser = WhatsAppTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        tpl = WhatsAppApprovedTemplate.objects.create(
            organization=organization,
            name=data["name"],
            language_code=data.get("language_code") or "tr",
            category=data.get("category") or "",
            body=data["body"],
            header=data.get("header") or "",
            footer=data.get("footer") or "",
            status=data.get("status") or WhatsAppTemplateStatus.DRAFT,
            external_template_id=data.get("external_template_id") or "",
            message_template_id=data.get("message_template_id"),
            variables_schema=data.get("variables_schema") or [],
        )
        return Response(serialize_wa_template(tpl), status=status.HTTP_201_CREATED)


class WhatsAppTemplateDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def _get(self, request, pk: int):
        organization = get_request_organization(request)
        if organization is None:
            return None, Response({"detail": "Organization required."}, status=400)
        tpl = (
            WhatsAppApprovedTemplate.objects.for_organization(organization)
            .filter(pk=pk)
            .first()
        )
        if tpl is None:
            return None, Response({"detail": "Not found."}, status=404)
        return tpl, None

    def get(self, request, pk: int):
        tpl, err = self._get(request, pk)
        if err:
            return err
        return Response(serialize_wa_template(tpl))

    def patch(self, request, pk: int):
        tpl, err = self._get(request, pk)
        if err:
            return err
        ser = WhatsAppTemplateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for key, value in ser.validated_data.items():
            if key == "message_template_id":
                tpl.message_template_id = value
            else:
                setattr(tpl, key, value)
        tpl.save()
        return Response(serialize_wa_template(tpl))

    def delete(self, request, pk: int):
        tpl, err = self._get(request, pk)
        if err:
            return err
        tpl.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WhatsAppSendView(APIView):
    """POST /api/message-templates/whatsapp/send/ — tekil gönderim."""

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
        ser = WhatsAppSendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            msg = create_and_send_whatsapp(
                organization=organization,
                actor=request.user,
                **ser.validated_data,
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serialize_outbound_wa(msg), status=status.HTTP_201_CREATED)


class WhatsAppBulkSendView(APIView):
    """POST /api/message-templates/whatsapp/bulk-send/"""

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
        ser = WhatsAppBulkSendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = bulk_send_whatsapp(
                organization=organization,
                actor=request.user,
                **ser.validated_data,
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result, status=status.HTTP_201_CREATED)


class WhatsAppOutboundListView(APIView):
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
        qs = OutboundWhatsApp.objects.for_organization(organization).order_by(
            "-created_at"
        )
        customer_id = request.query_params.get("customer_id")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        status_filter = (request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        batch_id = request.query_params.get("batch_id")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        return Response({"results": [serialize_outbound_wa(m) for m in qs[:100]]})


class WhatsAppOutboundDetailView(APIView):
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
        msg = (
            OutboundWhatsApp.objects.for_organization(organization)
            .filter(pk=pk)
            .first()
        )
        if msg is None:
            return Response({"detail": "Not found."}, status=404)
        data = serialize_outbound_wa(msg)
        data["events"] = [
            {
                "status": ev.status,
                "occurred_at": ev.occurred_at.isoformat(),
                "meta": ev.meta,
            }
            for ev in msg.events.all()[:50]
        ]
        return Response(data)


class WhatsAppStatusUpdateView(APIView):
    """POST status webhook / manual status update."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request, pk: int | None = None):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ser = WhatsAppStatusUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            msg = update_message_status(
                organization_id=organization.id,
                message_id=pk,
                provider_message_id=ser.validated_data.get("provider_message_id") or "",
                status=ser.validated_data["status"],
                meta=ser.validated_data.get("meta") or {},
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if msg is None:
            return Response({"detail": "Not found."}, status=404)
        return Response(serialize_outbound_wa(msg))


class WhatsAppInboundListCreateView(APIView):
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
        qs = InboundWhatsApp.objects.for_organization(organization).order_by(
            "-received_at"
        )
        customer_id = request.query_params.get("customer_id")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        unconfirmed = (request.query_params.get("unconfirmed") or "").lower()
        if unconfirmed in {"1", "true"}:
            qs = qs.filter(classification_confirmed=False)
        return Response({"results": [serialize_inbound_wa(m) for m in qs[:100]]})

    def post(self, request):
        """Ingest inbound (webhook simulation / provider callback)."""
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ser = WhatsAppInboundSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        inbound = ingest_inbound_whatsapp(
            organization=organization,
            **ser.validated_data,
        )
        return Response(serialize_inbound_wa(inbound), status=status.HTTP_201_CREATED)


class WhatsAppClassifyView(APIView):
    """POST /whatsapp/inbound/{id}/classify/ — kullanıcı onaylı sınıflandırma (NP-245)."""

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
        inbound = (
            InboundWhatsApp.objects.for_organization(organization).filter(pk=pk).first()
        )
        if inbound is None:
            return Response({"detail": "Not found."}, status=404)
        ser = WhatsAppClassifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            inbound = confirm_classification(
                inbound,
                classification=ser.validated_data["classification"],
                actor=request.user,
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serialize_inbound_wa(inbound))


class WhatsAppClassificationOptionsView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.VIEW_REPORTS

    def get(self, request):
        return Response(
            {
                "results": [
                    {"value": c.value, "label": c.label} for c in ResponseClassification
                ]
            }
        )


class WhatsAppOptOutListView(APIView):
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
        qs = WhatsAppOptOut.objects.for_organization(organization).filter(is_active=True)
        return Response(
            {
                "results": [
                    {
                        "id": o.id,
                        "customer_id": o.customer_id,
                        "phone": o.phone,
                        "reason": o.reason,
                        "opted_out_at": o.opted_out_at.isoformat()
                        if o.opted_out_at
                        else None,
                    }
                    for o in qs[:200]
                ]
            }
        )

    def delete(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        phone = (request.data.get("phone") or request.query_params.get("phone") or "").strip()
        if not phone:
            return Response({"detail": "phone required"}, status=400)
        cleared = clear_opt_out(organization, phone)
        return Response({"cleared": cleared})


class WhatsAppProviderConfigView(APIView):
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
        config = get_provider_config(organization)
        if config is None:
            return Response({"configured": False, "mock_mode": True})
        data = provider_config_public(config)
        data["configured"] = True
        return Response(data)

    def put(self, request):
        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ser = WhatsAppProviderConfigSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        creds = {}
        if data.get("access_token"):
            creds["access_token"] = data["access_token"]
        if data.get("api_key"):
            creds["api_key"] = data["api_key"]
        config = upsert_provider_config(
            organization,
            phone_number_id=data.get("phone_number_id") or "",
            waba_id=data.get("waba_id") or "",
            display_phone=data.get("display_phone") or "",
            mock_mode=bool(data.get("mock_mode", True)),
            credentials=creds or None,
        )
        out = provider_config_public(config)
        out["configured"] = True
        return Response(out)
