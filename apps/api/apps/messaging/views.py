"""Message template HTTP API (NP-130–133, NP-233)."""

from __future__ import annotations

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.messaging.assistant import list_tones
from apps.messaging.models import MessageTemplate
from apps.messaging.serializers import (
    CopyRequestSerializer,
    GenerateMessageRequestSerializer,
    MessageTemplateSerializer,
    PreviewRequestSerializer,
)
from apps.messaging.services import (
    MessagingError,
    ensure_default_templates,
    generate_toned_message,
    preview_template,
    record_template_copy,
)
from apps.organizations.mixins import RequireTenantContextPermission, TenantQuerysetMixin
from apps.organizations.permissions import HasOrganizationPermission
from apps.organizations.roles import Permission
from apps.organizations.tenancy import get_request_organization


class MessageTemplateListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get_queryset(self):
        qs = super().get_queryset()
        channel = (self.request.query_params.get("channel") or "").strip().upper()
        if channel:
            qs = qs.filter(channel=channel)
        return qs

    def list(self, request, *args, **kwargs):
        organization = get_request_organization(request)
        if organization is not None:
            ensure_default_templates(organization)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        organization = get_request_organization(self.request)
        serializer.save(organization=organization)


class MessageTemplateDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK


class MessageTemplatePreviewView(APIView):
    """POST /api/message-templates/{id}/preview/ — NP-132."""

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
        template = (
            MessageTemplate.objects.for_organization(organization).filter(pk=pk).first()
        )
        if template is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = PreviewRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = preview_template(
                template,
                customer_id=ser.validated_data["customer_id"],
                invoice_id=ser.validated_data.get("invoice_id"),
                payment_link=ser.validated_data.get("payment_link") or "",
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class MessageTemplateCopyView(APIView):
    """POST /api/message-templates/{id}/copy/ — NP-133."""

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
        template = (
            MessageTemplate.objects.for_organization(organization).filter(pk=pk).first()
        )
        if template is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        ser = CopyRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = record_template_copy(
                template,
                customer_id=ser.validated_data["customer_id"],
                actor=request.user,
                invoice_id=ser.validated_data.get("invoice_id"),
                create_activity=ser.validated_data.get("create_activity", False),
                rendered_body=ser.validated_data.get("body") or "",
                rendered_subject=ser.validated_data.get("subject") or "",
                payment_link=ser.validated_data.get("payment_link") or "",
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class MessageToneListView(APIView):
    """GET /api/message-templates/tones/ — NP-233."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        return Response({"tones": list_tones()})


class MessageGenerateView(APIView):
    """POST /api/message-templates/generate/ — NP-233 tone assistant."""

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

        ser = GenerateMessageRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = generate_toned_message(
                organization,
                customer_id=ser.validated_data["customer_id"],
                tone=ser.validated_data["tone"],
                invoice_id=ser.validated_data.get("invoice_id"),
                payment_link=ser.validated_data.get("payment_link") or "",
                actor=request.user,
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class OutboundEmailListCreateView(APIView):
    """GET/POST /api/message-templates/emails/ — NP-240."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request):
        from apps.messaging.email_service import serialize_outbound_email
        from apps.messaging.models import OutboundEmail

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        qs = OutboundEmail.objects.for_organization(organization).order_by("-created_at")
        customer_id = request.query_params.get("customer_id")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        status_filter = (request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        results = [serialize_outbound_email(e) for e in qs[:50]]
        return Response({"results": results})

    def post(self, request):
        from apps.messaging.email_service import create_email_draft, serialize_outbound_email
        from apps.messaging.serializers import OutboundEmailCreateSerializer

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ser = OutboundEmailCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            email = create_email_draft(
                organization=organization,
                actor=request.user,
                **ser.validated_data,
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serialize_outbound_email(email), status=status.HTTP_201_CREATED)


class OutboundEmailDetailView(APIView):
    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def get(self, request, pk: int):
        from apps.messaging.email_service import serialize_outbound_email
        from apps.messaging.models import OutboundEmail

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        email = OutboundEmail.objects.for_organization(organization).filter(pk=pk).first()
        if email is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = serialize_outbound_email(email)
        data["events"] = [
            {
                "event_type": ev.event_type,
                "url": ev.url,
                "occurred_at": ev.occurred_at.isoformat(),
                "meta": ev.meta,
            }
            for ev in email.events.all()[:50]
        ]
        return Response(data)


class OutboundEmailPreviewView(APIView):
    """POST /api/message-templates/emails/{id}/preview/"""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request, pk: int):
        from apps.messaging.email_service import preview_outbound_email
        from apps.messaging.models import OutboundEmail

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        email = OutboundEmail.objects.for_organization(organization).filter(pk=pk).first()
        if email is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(preview_outbound_email(email))


class OutboundEmailApproveView(APIView):
    """POST /api/message-templates/emails/{id}/approve/ — user approval required."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_COLLECTION_TASK

    def post(self, request, pk: int):
        from apps.messaging.email_service import (
            approve_outbound_email,
            serialize_outbound_email,
        )
        from apps.messaging.models import OutboundEmail
        from apps.messaging.serializers import OutboundEmailApproveSerializer

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        email = OutboundEmail.objects.for_organization(organization).filter(pk=pk).first()
        if email is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        ser = OutboundEmailApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            email = approve_outbound_email(
                email,
                actor=request.user,
                confirmed=bool(ser.validated_data["confirmed"]),
                queue_send=bool(ser.validated_data.get("queue_send", True)),
            )
        except MessagingError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email.refresh_from_db()
        return Response(serialize_outbound_email(email))


class EmailProviderConfigView(APIView):
    """GET/PUT /api/message-templates/email-provider/ — SMTP / API settings."""

    permission_classes = [
        IsAuthenticated,
        RequireTenantContextPermission,
        HasOrganizationPermission,
    ]
    read_permission = Permission.VIEW_REPORTS
    write_permission = Permission.MANAGE_SETTINGS

    def get(self, request):
        from apps.messaging.email_service import get_provider_config, provider_config_public

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        config = get_provider_config(organization)
        if config is None:
            return Response({"configured": False})
        data = provider_config_public(config)
        data["configured"] = True
        return Response(data)

    def put(self, request):
        from apps.messaging.email_service import provider_config_public, upsert_provider_config
        from apps.messaging.serializers import EmailProviderConfigSerializer

        organization = get_request_organization(request)
        if organization is None:
            return Response({"detail": "Organization required."}, status=400)
        ser = EmailProviderConfigSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        creds = {}
        if data.get("username") or data.get("password"):
            creds["username"] = data.get("username") or ""
            creds["password"] = data.get("password") or ""
        if data.get("api_key"):
            creds["api_key"] = data["api_key"]
        config = upsert_provider_config(
            organization,
            provider=data.get("provider") or "SMTP",
            from_email=data["from_email"],
            from_name=data.get("from_name") or "",
            smtp_host=data.get("smtp_host") or "",
            smtp_port=data.get("smtp_port") or 587,
            smtp_use_tls=bool(data.get("smtp_use_tls", True)),
            smtp_use_ssl=bool(data.get("smtp_use_ssl", False)),
            credentials=creds or None,
        )
        out = provider_config_public(config)
        out["configured"] = True
        return Response(out)


class EmailOpenPixelView(APIView):
    """GET /api/public/email/o/{token}.gif — open tracking (no auth)."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, token: str):
        from django.http import HttpResponse

        from apps.messaging.email_service import record_open, tracking_pixel_bytes

        record_open(token, meta={"ua": request.META.get("HTTP_USER_AGENT", "")[:200]})
        return HttpResponse(tracking_pixel_bytes(), content_type="image/gif")


class EmailClickRedirectView(APIView):
    """GET /api/public/email/c/{token}/?u= — click tracking."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, token: str):
        from django.http import HttpResponseRedirect

        from apps.messaging.email_service import record_click

        raw_url = request.query_params.get("u") or ""
        _email, target = record_click(
            token,
            raw_url,
            meta={"ua": request.META.get("HTTP_USER_AGENT", "")[:200]},
        )
        if not target:
            return Response({"detail": "Invalid URL."}, status=400)
        return HttpResponseRedirect(target)


class EmailBounceWebhookView(APIView):
    """POST /api/public/email/bounce/ — bounce management."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        from apps.messaging.email_service import record_bounce, serialize_outbound_email
        from apps.messaging.serializers import EmailBounceSerializer

        ser = EmailBounceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = record_bounce(
            token=ser.validated_data.get("tracking_token") or "",
            provider_message_id=ser.validated_data.get("provider_message_id") or "",
            bounce_type=ser.validated_data.get("bounce_type") or "hard",
            detail=ser.validated_data.get("detail") or "",
        )
        if email is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_outbound_email(email))
