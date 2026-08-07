"""NP-250 — dispute serializers."""

from rest_framework import serializers

from apps.collections.models import Dispute, DisputeCategory, DisputeStatus


class DisputeSerializer(serializers.ModelSerializer):
    assigned_user_name = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()
    category_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = (
            "id",
            "organization",
            "customer",
            "customer_name",
            "invoice",
            "invoice_number",
            "category",
            "category_label",
            "status",
            "status_label",
            "amount",
            "opened_at",
            "assigned_user",
            "assigned_user_name",
            "description",
            "resolution_note",
            "resolved_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "resolved_at",
            "created_by",
            "created_at",
            "updated_at",
            "customer_name",
            "invoice_number",
            "assigned_user_name",
            "category_label",
            "status_label",
        )

    def get_assigned_user_name(self, obj: Dispute) -> str:
        user = obj.assigned_user
        if user is None:
            return ""
        return getattr(user, "email", "") or str(user)

    def get_customer_name(self, obj: Dispute) -> str:
        return obj.customer.name if obj.customer_id else ""

    def get_invoice_number(self, obj: Dispute) -> str:
        return obj.invoice.number if obj.invoice_id else ""

    def get_category_label(self, obj: Dispute) -> str:
        return DisputeCategory(obj.category).label if obj.category else ""

    def get_status_label(self, obj: Dispute) -> str:
        return DisputeStatus(obj.status).label if obj.status else ""

    def validate_category(self, value: str) -> str:
        if value not in DisputeCategory.values:
            raise serializers.ValidationError("Geçersiz itiraz kategorisi.")
        return value

    def validate_status(self, value: str) -> str:
        if value not in DisputeStatus.values:
            raise serializers.ValidationError("Geçersiz itiraz durumu.")
        return value
