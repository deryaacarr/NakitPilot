from rest_framework import serializers

from apps.legal.models import (
    LegalCase,
    LegalCaseActivity,
    LegalCaseDocument,
    LegalCaseInvoice,
    LegalCaseStatus,
    LegalCaseStatusHistory,
)
from apps.legal.workflow import lawyer_safe_case_payload


class LegalCaseInvoiceSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)

    class Meta:
        model = LegalCaseInvoice
        fields = ("id", "invoice", "invoice_number", "amount_at_link", "created_at")


class LegalCaseActivitySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = LegalCaseActivity
        fields = (
            "id",
            "summary",
            "notes",
            "is_lawyer_visible",
            "created_by",
            "created_by_email",
            "occurred_at",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")


class LegalCaseDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = LegalCaseDocument
        fields = (
            "id",
            "original_filename",
            "content_type",
            "file_size",
            "notes",
            "uploaded_by",
            "uploaded_by_email",
            "created_at",
        )
        read_only_fields = fields


class LegalCaseStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.EmailField(source="changed_by.email", read_only=True)

    class Meta:
        model = LegalCaseStatusHistory
        fields = (
            "id",
            "from_status",
            "to_status",
            "note",
            "changed_by",
            "changed_by_email",
            "occurred_at",
        )


class LegalCaseSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    assigned_lawyer_email = serializers.EmailField(
        source="assigned_lawyer.email", read_only=True
    )
    case_invoices = LegalCaseInvoiceSerializer(many=True, read_only=True)
    activities = LegalCaseActivitySerializer(many=True, read_only=True)
    documents = LegalCaseDocumentSerializer(many=True, read_only=True)
    status_history = LegalCaseStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = LegalCase
        fields = (
            "id",
            "customer",
            "customer_name",
            "title",
            "status",
            "balance_at_open",
            "criteria_snapshot",
            "manager_approved",
            "manager_approved_at",
            "assigned_lawyer",
            "assigned_lawyer_email",
            "package_path",
            "package_generated_at",
            "notes",
            "opened_at",
            "closed_at",
            "created_by",
            "created_at",
            "updated_at",
            "case_invoices",
            "activities",
            "documents",
            "status_history",
        )
        read_only_fields = (
            "id",
            "balance_at_open",
            "criteria_snapshot",
            "manager_approved",
            "manager_approved_at",
            "package_path",
            "package_generated_at",
            "opened_at",
            "closed_at",
            "created_by",
            "created_at",
            "updated_at",
            "customer_name",
            "assigned_lawyer_email",
            "case_invoices",
            "activities",
            "documents",
            "status_history",
        )


class LegalCaseListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    assigned_lawyer_email = serializers.EmailField(
        source="assigned_lawyer.email", read_only=True
    )

    class Meta:
        model = LegalCase
        fields = (
            "id",
            "customer",
            "customer_name",
            "title",
            "status",
            "balance_at_open",
            "manager_approved",
            "assigned_lawyer",
            "assigned_lawyer_email",
            "opened_at",
            "updated_at",
        )


class LawyerCaseSerializer(serializers.Serializer):
    """NP-353 restricted representation."""

    def to_representation(self, instance: LegalCase):
        data = lawyer_safe_case_payload(instance)
        data["activities"] = LegalCaseActivitySerializer(
            instance.activities.filter(is_lawyer_visible=True),
            many=True,
        ).data
        data["documents"] = LegalCaseDocumentSerializer(
            instance.documents.all(),
            many=True,
        ).data
        data["status_history"] = LegalCaseStatusHistorySerializer(
            instance.status_history.all()[:20],
            many=True,
        ).data
        return data


class LegalCaseCreateSerializer(serializers.Serializer):
    customer = serializers.IntegerField()
    title = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    invoice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )


class LegalCaseStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LegalCaseStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class LegalCaseHandoffSerializer(serializers.Serializer):
    lawyer_id = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True, default="")


class LegalActivityCreateSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
