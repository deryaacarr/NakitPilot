"""Public v1 serializers — slim stable contracts."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.payments.models import PaymentMethod
from apps.payments.serializers import PaymentAllocationInputSerializer
from apps.payments.services import PaymentValidationError, create_payment

ZERO = Decimal("0.00")


class PublicCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "id",
            "code",
            "name",
            "tax_number",
            "email",
            "phone",
            "city",
            "sector",
            "payment_term_days",
            "credit_limit",
            "risk_status",
            "risk_score",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "risk_status",
            "risk_score",
            "created_at",
            "updated_at",
        )

    def validate_name(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Müşteri adı gerekli.")
        return value

    def validate_code(self, value: str) -> str:
        return (value or "").strip()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        code = attrs.get("code") or ""
        if not code:
            return attrs
        organization = self.context["organization"]
        qs = Customer.objects.filter(organization=organization, code=code)
        if qs.exists():
            raise serializers.ValidationError(
                {"code": "Bu müşteri kodu aynı organizasyonda zaten kullanılıyor."}
            )
        return attrs


class PublicInvoiceSerializer(serializers.ModelSerializer):
    remaining_amount = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "id",
            "customer",
            "number",
            "invoice_date",
            "due_date",
            "currency",
            "subtotal_amount",
            "tax_amount",
            "total_amount",
            "remaining_amount",
            "status",
            "description",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "remaining_amount",
            "created_at",
            "updated_at",
        )

    def get_remaining_amount(self, obj: Invoice) -> str:
        return str(obj.remaining_amount())

    def validate_customer(self, value: Customer) -> Customer:
        organization = self.context["organization"]
        if value.organization_id != organization.id:
            raise serializers.ValidationError("Müşteri bu organizasyona ait değil.")
        if not value.is_active:
            raise serializers.ValidationError("Pasif müşteriye fatura kesilemez.")
        return value

    def validate_number(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Fatura numarası gerekli.")
        return value

    def validate_total_amount(self, value: Decimal) -> Decimal:
        if value is None or value < ZERO:
            raise serializers.ValidationError("Fatura tutarı geçerli olmalı.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        invoice_date = attrs.get("invoice_date")
        due_date = attrs.get("due_date")
        if invoice_date and due_date and due_date < invoice_date:
            raise serializers.ValidationError(
                {"due_date": "Vade tarihi fatura tarihinden önce olamaz."}
            )
        organization = self.context["organization"]
        number = attrs.get("number")
        if number and Invoice.objects.filter(organization=organization, number=number).exists():
            raise serializers.ValidationError(
                {"number": "Bu fatura numarası organizasyonda zaten var."}
            )
        if "status" not in attrs or not attrs.get("status"):
            attrs["status"] = InvoiceStatus.OPEN
        return attrs


class PublicPaymentCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    payment_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.CharField(required=False, default="TRY", max_length=3)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    allocations = PaymentAllocationInputSerializer(many=True, required=False)
    auto_allocate = serializers.BooleanField(required=False, default=False)

    def validate_customer(self, value: Customer) -> Customer:
        organization = self.context["organization"]
        if value.organization_id != organization.id:
            raise serializers.ValidationError("Müşteri bu organizasyona ait değil.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        organization = self.context["organization"]
        try:
            return create_payment(
                organization=organization,
                customer=validated_data["customer"],
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


class PublicPaymentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    customer = serializers.IntegerField(source="customer_id")
    payment_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    method = serializers.CharField()
    reference = serializers.CharField()
    notes = serializers.CharField()
    unallocated_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    created_at = serializers.DateTimeField()
