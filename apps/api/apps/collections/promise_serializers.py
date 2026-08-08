from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.collections.models import PaymentPromise
from apps.collections.promises import (
    PromiseValidationError,
    cancel_promise,
    create_promise,
    paid_toward_promise,
    update_promise,
)
from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.payments.models import ZERO

User = get_user_model()


class PaymentPromiseSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    paid_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    delay_days = serializers.SerializerMethodField()
    assigned_to = serializers.IntegerField(
        source="customer.assigned_user_id", read_only=True, allow_null=True
    )
    assigned_to_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.SerializerMethodField()

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
            "paid_amount",
            "remaining_amount",
            "delay_days",
            "assigned_to",
            "assigned_to_name",
            "assigned_to_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _paid(self, obj: PaymentPromise) -> Decimal:
        cache = self.context.setdefault("_promise_paid", {})
        if obj.id not in cache:
            cache[obj.id] = paid_toward_promise(obj)
        return cache[obj.id]

    def get_paid_amount(self, obj: PaymentPromise) -> str:
        return str(min(self._paid(obj), obj.amount).quantize(Decimal("0.01")))

    def get_remaining_amount(self, obj: PaymentPromise) -> str:
        paid = self._paid(obj)
        remaining = obj.amount - paid
        if remaining < ZERO:
            remaining = ZERO
        return str(remaining.quantize(Decimal("0.01")))

    def get_delay_days(self, obj: PaymentPromise) -> int:
        today = timezone.localdate()
        if obj.status in {"FULFILLED", "CANCELLED"}:
            return 0
        if obj.promised_date >= today:
            return 0
        return (today - obj.promised_date).days

    def get_assigned_to_name(self, obj: PaymentPromise) -> str | None:
        user = obj.customer.assigned_user
        if user is None:
            return None
        full = f"{user.first_name} {user.last_name}".strip()
        return full or user.email

    def get_assigned_to_email(self, obj: PaymentPromise) -> str | None:
        user = obj.customer.assigned_user
        return user.email if user else None


class PaymentPromiseCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(), required=False, allow_null=True
    )
    promised_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.CharField(required=False, default="TRY", max_length=3)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    create_follow_up = serializers.BooleanField(required=False, default=False)
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    follow_up_due_date = serializers.DateField(required=False, allow_null=True)

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
                create_follow_up=bool(validated_data.get("create_follow_up")),
                assigned_to=validated_data.get("assigned_to"),
                follow_up_due_date=validated_data.get("follow_up_due_date"),
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
