from decimal import Decimal

from rest_framework import serializers

from apps.collections.models import PaymentPromise
from apps.collections.promises import (
    PromiseValidationError,
    cancel_promise,
    create_promise,
    update_promise,
)
from apps.customers.models import Customer
from apps.invoices.models import Invoice


class PaymentPromiseSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = PaymentPromise
        fields = (
            "id",
            "organization",
            "customer",
            "customer_name",
            "invoice",
            "invoice_number",
            "promised_date",
            "amount",
            "currency",
            "status",
            "notes",
            "created_by",
            "created_by_email",
            "fulfilled_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PaymentPromiseCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(), required=False, allow_null=True
    )
    promised_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.CharField(required=False, default="TRY", max_length=3)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def create(self, validated_data):
        try:
            promise, warnings = create_promise(
                organization=self.context["organization"],
                customer=validated_data["customer"],
                promised_date=validated_data["promised_date"],
                amount=validated_data["amount"],
                currency=validated_data.get("currency", "TRY"),
                notes=validated_data.get("notes", ""),
                invoice=validated_data.get("invoice"),
                created_by=self.context["request"].user,
            )
        except PromiseValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc
        self.context["warnings"] = warnings
        return promise


class PaymentPromiseUpdateSerializer(serializers.Serializer):
    promised_date = serializers.DateField(required=False)
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(), required=False, allow_null=True
    )

    def update(self, instance, validated_data):
        clear_invoice = "invoice" in validated_data and validated_data.get("invoice") is None
        try:
            promise, warnings = update_promise(
                instance,
                actor=self.context["request"].user,
                promised_date=validated_data.get("promised_date"),
                amount=validated_data.get("amount"),
                notes=validated_data.get("notes"),
                invoice=validated_data.get("invoice"),
                clear_invoice=clear_invoice,
            )
        except PromiseValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc
        self.context["warnings"] = warnings
        return promise


class PaymentPromiseCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        promise: PaymentPromise = self.context["promise"]
        try:
            return cancel_promise(
                promise,
                actor=self.context["request"].user,
                reason=self.validated_data.get("reason", ""),
            )
        except PromiseValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc


def serialize_promise(promise: PaymentPromise) -> dict:
    return PaymentPromiseSerializer(promise).data
