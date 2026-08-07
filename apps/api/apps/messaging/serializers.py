from rest_framework import serializers

from apps.messaging.models import MessageChannel, MessageTemplate


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = (
            "id",
            "organization",
            "name",
            "channel",
            "subject",
            "body",
            "is_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")

    def validate_channel(self, value: str) -> str:
        if value not in MessageChannel.values:
            raise serializers.ValidationError("Geçersiz kanal.")
        return value

    def validate_body(self, value: str) -> str:
        if not (value or "").strip():
            raise serializers.ValidationError("Mesaj metni zorunlu.")
        return value


class PreviewRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    invoice_id = serializers.IntegerField(required=False, allow_null=True)
    payment_link = serializers.CharField(required=False, allow_blank=True, default="")


class GenerateMessageRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    tone = serializers.CharField()
    invoice_id = serializers.IntegerField(required=False, allow_null=True)
    payment_link = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_tone(self, value: str) -> str:
        from apps.messaging.assistant import MessageTone

        tone = (value or "").strip().upper()
        if tone not in MessageTone.values:
            raise serializers.ValidationError(
                f"tone must be one of: {', '.join(MessageTone.values)}"
            )
        return tone


class CopyRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    invoice_id = serializers.IntegerField(required=False, allow_null=True)
    create_activity = serializers.BooleanField(default=False)
    payment_link = serializers.CharField(required=False, allow_blank=True, default="")
    body = serializers.CharField(required=False, allow_blank=True, default="")
    subject = serializers.CharField(required=False, allow_blank=True, default="")


class OutboundEmailCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    template_id = serializers.IntegerField(required=False, allow_null=True)
    invoice_id = serializers.IntegerField(required=False, allow_null=True)
    to_email = serializers.EmailField(required=False, allow_blank=True, default="")
    subject = serializers.CharField(required=False, allow_blank=True, default="")
    body = serializers.CharField(required=False, allow_blank=True, default="")
    require_approval = serializers.BooleanField(required=False, default=True)


class OutboundEmailApproveSerializer(serializers.Serializer):
    confirmed = serializers.BooleanField()
    queue_send = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if not attrs.get("confirmed"):
            raise serializers.ValidationError(
                {"confirmed": "Onay olmadan e-posta gönderilemez."}
            )
        return attrs


class EmailProviderConfigSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=["SMTP", "API", "CONSOLE"], required=False, default="SMTP"
    )
    from_email = serializers.EmailField()
    from_name = serializers.CharField(required=False, allow_blank=True, default="")
    smtp_host = serializers.CharField(required=False, allow_blank=True, default="")
    smtp_port = serializers.IntegerField(required=False, default=587)
    smtp_use_tls = serializers.BooleanField(required=False, default=True)
    smtp_use_ssl = serializers.BooleanField(required=False, default=False)
    username = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, allow_blank=True, default="")
    api_key = serializers.CharField(required=False, allow_blank=True, default="")


class EmailBounceSerializer(serializers.Serializer):
    tracking_token = serializers.CharField(required=False, allow_blank=True, default="")
    provider_message_id = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    bounce_type = serializers.CharField(required=False, default="hard")
    detail = serializers.CharField(required=False, allow_blank=True, default="")
