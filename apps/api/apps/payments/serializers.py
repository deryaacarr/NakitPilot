from decimal import Decimal

from rest_framework import serializers

from apps.customers.models import Customer
from apps.payments.models import Payment, PaymentAllocation, PaymentMethod
from apps.payments.services import PaymentValidationError, create_payment, replace_allocations


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ("id", "invoice", "invoice_number", "amount", "created_at")
        read_only_fields = fields


class PaymentAllocationInputSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True)
    cancelled_by_email = serializers.EmailField(source="cancelled_by.email", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    is_cancelled = serializers.BooleanField(read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "organization",
            "customer",
            "customer_name",
            "payment_date",
            "amount",
            "currency",
            "method",
            "reference",
            "notes",
            "unallocated_amount",
            "recorded_by",
            "recorded_by_email",
            "cancelled_at",
            "cancelled_by",
            "cancelled_by_email",
            "cancellation_reason",
            "is_cancelled",
            "allocations",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    payment_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.CharField(required=False, default="TRY", max_length=3)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    allocations = PaymentAllocationInputSerializer(many=True, required=False)
    auto_allocate = serializers.BooleanField(required=False, default=False)

    def create(self, validated_data):
        request = self.context["request"]
        organization = self.context["organization"]
        customer = validated_data["customer"]
        try:
            return create_payment(
                organization=organization,
                customer=customer,
                payment_date=validated_data["payment_date"],
                amount=validated_data["amount"],
                currency=validated_data.get("currency", "TRY"),
                method=validated_data.get("method") or PaymentMethod.BANK_TRANSFER,
                reference=validated_data.get("reference", ""),
                notes=validated_data.get("notes", ""),
                recorded_by=request.user,
                allocations=validated_data.get("allocations"),
                auto_allocate=bool(validated_data.get("auto_allocate")),
            )
        except PaymentValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc


class PaymentAllocationsUpdateSerializer(serializers.Serializer):
    allocations = PaymentAllocationInputSerializer(many=True)
    auto_allocate = serializers.BooleanField(required=False, default=False)

    def save(self, **kwargs):
        payment: Payment = self.context["payment"]
        actor = self.context["request"].user
        auto = bool(self.validated_data.get("auto_allocate"))
        if auto:
            from apps.payments.services import auto_allocate_oldest_first

            plan = auto_allocate_oldest_first(
                organization=payment.organization,
                customer=payment.customer,
                payment_amount=payment.amount,
                currency=payment.currency,
            )
        else:
            plan = self.validated_data["allocations"]
        try:
            return replace_allocations(payment, plan, actor=actor)
        except PaymentValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc


class PaymentCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
