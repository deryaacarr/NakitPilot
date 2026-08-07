from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import (
    delay_days_for_risk,
    invoice_actual_delay_days,
    invoice_overdue_days,
)

ZERO = Decimal("0.00")


class InvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    assigned_user_name = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    allocated_amount = serializers.SerializerMethodField()
    overdue_days = serializers.SerializerMethodField()
    actual_delay_days = serializers.SerializerMethodField()
    delay_days_for_risk = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "id",
            "organization",
            "customer",
            "customer_name",
            "customer_code",
            "number",
            "invoice_date",
            "due_date",
            "currency",
            "subtotal_amount",
            "tax_amount",
            "total_amount",
            "remaining_amount",
            "allocated_amount",
            "overdue_days",
            "actual_delay_days",
            "delay_days_for_risk",
            "status",
            "description",
            "notes",
            "assigned_user",
            "assigned_user_name",
            "payment_completion_date",
            "cancelled_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "customer_name",
            "customer_code",
            "remaining_amount",
            "allocated_amount",
            "overdue_days",
            "actual_delay_days",
            "delay_days_for_risk",
            "cancelled_at",
            "created_at",
            "updated_at",
            "assigned_user_name",
        )

    def get_assigned_user_name(self, obj: Invoice) -> str | None:
        user = obj.assigned_user
        if user is None:
            return None
        full = f"{user.first_name} {user.last_name}".strip()
        return full or user.email

    def get_remaining_amount(self, obj: Invoice) -> str:
        return str(obj.remaining_amount())

    def get_allocated_amount(self, obj: Invoice) -> str:
        return str(obj.allocated_amount())

    def get_overdue_days(self, obj: Invoice) -> int:
        return invoice_overdue_days(obj)

    def get_actual_delay_days(self, obj: Invoice) -> int | None:
        return invoice_actual_delay_days(obj)

    def get_delay_days_for_risk(self, obj: Invoice) -> int | None:
        return delay_days_for_risk(obj)

    def validate_number(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Fatura numarası gerekli.")
        return value

    def validate_currency(self, value: str) -> str:
        value = (value or "TRY").upper().strip()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Para birimi 3 harfli ISO kodu olmalıdır.")
        return value

    def validate_subtotal_amount(self, value: Decimal) -> Decimal:
        if value is not None and value < ZERO:
            raise serializers.ValidationError("Ara toplam negatif olamaz.")
        return value if value is not None else ZERO

    def validate_tax_amount(self, value: Decimal) -> Decimal:
        if value is not None and value < ZERO:
            raise serializers.ValidationError("Vergi negatif olamaz.")
        return value if value is not None else ZERO

    def validate_total_amount(self, value: Decimal) -> Decimal:
        if value is None:
            raise serializers.ValidationError("Tutar gerekli.")
        if value < ZERO:
            raise serializers.ValidationError("Fatura tutarı negatif olamaz.")
        return value

    def validate_status(self, value: str) -> str:
        if value not in InvoiceStatus.values:
            raise serializers.ValidationError("Geçersiz fatura durumu.")
        return value

    def validate_customer(self, value: Customer) -> Customer:
        request = self.context.get("request")
        organization = getattr(getattr(request, "user", None), "current_organization", None)
        if organization is None and request is not None:
            from apps.organizations.tenancy import get_request_organization

            organization = get_request_organization(request)
        if organization is not None and value.organization_id != organization.id:
            raise serializers.ValidationError("Müşteri bu organizasyona ait değil.")
        if not value.is_active:
            raise serializers.ValidationError("Pasif müşteriye fatura kesilemez.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance

        if instance is not None and instance.status == InvoiceStatus.CANCELLED:
            raise serializers.ValidationError("İptal edilmiş fatura güncellenemez.")

        invoice_date = attrs.get("invoice_date", getattr(instance, "invoice_date", None))
        due_date = attrs.get("due_date", getattr(instance, "due_date", None))
        if invoice_date and due_date and due_date < invoice_date:
            raise serializers.ValidationError(
                {"due_date": "Vade tarihi fatura tarihinden önce olamaz."}
            )

        subtotal = attrs.get(
            "subtotal_amount",
            getattr(instance, "subtotal_amount", ZERO)
            if instance
            else attrs.get("subtotal_amount"),
        )
        tax = attrs.get(
            "tax_amount",
            getattr(instance, "tax_amount", ZERO) if instance else attrs.get("tax_amount"),
        )
        if "subtotal_amount" in attrs or "tax_amount" in attrs:
            subtotal = attrs.get("subtotal_amount", getattr(instance, "subtotal_amount", ZERO))
            tax = attrs.get("tax_amount", getattr(instance, "tax_amount", ZERO))
            computed = (subtotal or ZERO) + (tax or ZERO)
            if "total_amount" not in attrs or attrs.get("total_amount") is None:
                attrs["total_amount"] = computed
            elif abs(attrs["total_amount"] - computed) > Decimal("0.01"):
                raise serializers.ValidationError(
                    {"total_amount": "Toplam, ara toplam + vergiye eşit olmalıdır."}
                )

        number = attrs.get("number", getattr(instance, "number", None))
        request = self.context.get("request")
        organization = None
        if instance is not None:
            organization = instance.organization
        elif request is not None:
            from apps.organizations.tenancy import get_request_organization

            organization = get_request_organization(request)

        if organization and number:
            qs = Invoice.objects.filter(organization=organization, number=number)
            if instance is not None:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"number": "Bu fatura numarası aynı organizasyonda zaten kullanılıyor."}
                )

        return attrs

    def create(self, validated_data):
        validated_data.setdefault("status", InvoiceStatus.OPEN)
        if validated_data["status"] not in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}:
            due = validated_data.get("due_date")
            remaining = validated_data.get("total_amount", ZERO)
            # No allocations on create → remaining == total
            if remaining == ZERO:
                validated_data["status"] = InvoiceStatus.PAID
                validated_data.setdefault("payment_completion_date", timezone.localdate())
            elif due and due < timezone.localdate():
                validated_data["status"] = InvoiceStatus.OVERDUE
            elif validated_data["status"] not in {
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.PAID,
                InvoiceStatus.OVERDUE,
            }:
                validated_data["status"] = InvoiceStatus.OPEN
        try:
            invoice = super().create(validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"number": "Bu fatura numarası aynı organizasyonda zaten kullanılıyor."}
            ) from exc
        # NP-103: yeni fatura → risk
        from apps.risk.triggers import bump_customer_risk

        bump_customer_risk(invoice.customer_id)
        return invoice

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"number": "Bu fatura numarası aynı organizasyonda zaten kullanılıyor."}
            ) from exc


class InvoiceDetailSerializer(InvoiceSerializer):
    """Detail payload with related sections (stubs until modules land)."""

    payment_allocations = serializers.SerializerMethodField()
    collection_tasks = serializers.SerializerMethodField()
    payment_promises = serializers.SerializerMethodField()
    contact_history = serializers.SerializerMethodField()
    audit_log = serializers.SerializerMethodField()
    collection_outlook = serializers.SerializerMethodField()

    class Meta(InvoiceSerializer.Meta):
        fields = (
            *InvoiceSerializer.Meta.fields,
            "payment_allocations",
            "collection_tasks",
            "payment_promises",
            "contact_history",
            "audit_log",
            "collection_outlook",
        )

    def get_collection_outlook(self, obj: Invoice) -> dict:
        """NP-225: 7/30/60d collection probabilities + expected date."""
        from apps.forecasting.probability import calculate_collection_horizons

        if obj.status in (
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.DRAFT,
        ):
            return {
                "probability_7d": None,
                "probability_30d": None,
                "probability_60d": None,
                "expected_collection_date": None,
            }
        result = calculate_collection_horizons(obj)
        return {
            "probability_7d": str(result["probability_7d"]),
            "probability_30d": str(result["probability_30d"]),
            "probability_60d": str(result["probability_60d"]),
            "expected_collection_date": result["expected_collection_date"],
            "expected_amount_7d": str(result["expected_amount_7d"]),
            "expected_amount_30d": str(result["expected_amount_30d"]),
            "expected_amount_60d": str(result["expected_amount_60d"]),
            "overdue_days": result["overdue_days"],
            "adjustments": [
                {
                    "code": a["code"],
                    "label": a["label"],
                    "delta": str(a["delta"]),
                }
                for a in result.get("adjustments", [])
            ],
        }

    def get_payment_allocations(self, obj: Invoice) -> list:
        allocations = getattr(obj, "allocations", None)
        if allocations is None:
            return []
        rows = allocations.select_related("payment").filter(payment__cancelled_at__isnull=True)
        return [
            {
                "id": row.id,
                "amount": str(row.amount),
                "payment_id": row.payment_id,
                "payment_date": row.payment.payment_date if row.payment_id else None,
            }
            for row in rows
        ]

    def get_collection_tasks(self, _obj: Invoice) -> list:
        return []

    def get_payment_promises(self, _obj: Invoice) -> list:
        return []

    def get_contact_history(self, _obj: Invoice) -> list:
        return []

    def get_audit_log(self, obj: Invoice) -> list:
        from apps.audit.models import AuditLog

        rows = (
            AuditLog.objects.filter(
                organization_id=obj.organization_id,
                entity_type="Invoice",
                entity_id=str(obj.id),
            )
            .select_related("actor")
            .order_by("-created_at")[:50]
        )
        return [
            {
                "id": row.id,
                "action": row.action,
                "summary": row.summary,
                "actor_id": row.actor_id,
                "actor_email": row.actor.email if row.actor_id else None,
                "changes": row.changes,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
