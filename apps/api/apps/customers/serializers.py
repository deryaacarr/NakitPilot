from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer, CustomerContact, RiskStatus
from apps.customers.validators import validate_turkish_tax_number

User = get_user_model()


class CustomerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerContact
        fields = (
            "id",
            "customer",
            "organization",
            "full_name",
            "title",
            "email",
            "phone",
            "is_primary",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "customer", "organization", "created_at", "updated_at")

    def validate_email(self, value: str) -> str:
        return (value or "").strip().lower()

    def create(self, validated_data):
        customer = self.context["customer"]
        validated_data["customer"] = customer
        validated_data["organization"] = customer.organization
        return self._save_with_primary(CustomerContact(**validated_data))

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        return self._save_with_primary(instance)

    def _save_with_primary(self, contact: CustomerContact) -> CustomerContact:
        with transaction.atomic():
            contact.save()
            if contact.is_primary:
                (
                    CustomerContact.objects.filter(customer_id=contact.customer_id, is_primary=True)
                    .exclude(pk=contact.pk)
                    .update(is_primary=False)
                )
        return contact


class CustomerSerializer(serializers.ModelSerializer):
    assigned_user_name = serializers.SerializerMethodField()
    open_balance = serializers.SerializerMethodField()
    overdue_balance = serializers.SerializerMethodField()
    disputed_balance = serializers.SerializerMethodField()
    unallocated_payment_balance = serializers.SerializerMethodField()
    avg_delay_days = serializers.SerializerMethodField()
    oldest_overdue_days = serializers.SerializerMethodField()
    primary_contact_name = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = (
            "id",
            "organization",
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
            "assigned_user",
            "assigned_user_name",
            "notes",
            "collection_strategy",
            "source",
            "external_id",
            "local_field_overrides",
            "last_synced_at",
            "last_contact_at",
            "is_active",
            "open_balance",
            "overdue_balance",
            "disputed_balance",
            "unallocated_payment_balance",
            "avg_delay_days",
            "oldest_overdue_days",
            "primary_contact_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "source",
            "external_id",
            "local_field_overrides",
            "last_synced_at",
            "created_at",
            "updated_at",
            "assigned_user_name",
            "open_balance",
            "overdue_balance",
            "disputed_balance",
            "unallocated_payment_balance",
            "avg_delay_days",
            "oldest_overdue_days",
            "primary_contact_name",
        )

    def get_assigned_user_name(self, obj: Customer) -> str | None:
        user = obj.assigned_user
        if user is None:
            return None
        full = f"{user.first_name} {user.last_name}".strip()
        return full or user.email

    def get_open_balance(self, obj: Customer) -> str:
        return str(self._metrics(obj)["open_balance"])

    def get_overdue_balance(self, obj: Customer) -> str:
        return str(self._metrics(obj)["overdue_balance"])

    def get_disputed_balance(self, obj: Customer) -> str:
        return str(self._metrics(obj)["disputed_balance"])

    def get_unallocated_payment_balance(self, obj: Customer) -> str:
        return str(self._metrics(obj)["unallocated_payment_balance"])

    def get_avg_delay_days(self, obj: Customer) -> int | None:
        return self._metrics(obj)["avg_delay_days"]

    def get_oldest_overdue_days(self, obj: Customer) -> int | None:
        return self._metrics(obj)["oldest_overdue_days"]

    def get_primary_contact_name(self, obj: Customer) -> str | None:
        if hasattr(obj, "primary_contact_name_anno"):
            return obj.primary_contact_name_anno
        contact = obj.contacts.filter(is_primary=True).first()
        return contact.full_name if contact else None

    def _metrics(self, obj: Customer) -> dict:
        cache = getattr(self, "_metrics_cache", None)
        if cache is None:
            cache = {}
            self._metrics_cache = cache
        if obj.pk not in cache:
            cache[obj.pk] = customer_financial_metrics(obj)
        return cache[obj.pk]

    def validate_code(self, value: str) -> str:
        return (value or "").strip()

    def validate_tax_number(self, value: str) -> str:
        value = (value or "").strip()
        validate_turkish_tax_number(value)
        return value

    def validate_email(self, value: str) -> str:
        return (value or "").strip().lower()

    def validate_payment_term_days(self, value: int) -> int:
        if value is None:
            return 30
        if value < 0:
            raise serializers.ValidationError("Vade günü negatif olamaz.")
        return value

    def validate_credit_limit(self, value: Decimal) -> Decimal:
        if value is None:
            return Decimal("0.00")
        if value < 0:
            raise serializers.ValidationError("Kredi limiti negatif olamaz.")
        return value

    def validate_risk_status(self, value: str) -> str:
        if value not in RiskStatus.values:
            raise serializers.ValidationError("Geçersiz risk seviyesi.")
        return value

    def validate_risk_score(self, value: int) -> int:
        if value < 0 or value > 100:
            raise serializers.ValidationError("Risk skoru 0–100 arasında olmalıdır.")
        return value

    def validate_assigned_user(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        organization = getattr(getattr(request, "user", None), "current_organization", None)
        if organization is None and request is not None:
            from apps.organizations.tenancy import get_request_organization

            organization = get_request_organization(request)
        if organization is None:
            return value
        if not value.memberships.filter(organization=organization, is_active=True).exists():
            raise serializers.ValidationError(
                "Sorumlu kullanıcı bu organizasyonda aktif üye değil."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        code = attrs.get("code", getattr(self.instance, "code", ""))
        if not code:
            return attrs

        request = self.context.get("request")
        organization = None
        if self.instance is not None:
            organization = self.instance.organization
        elif request is not None:
            from apps.organizations.tenancy import get_request_organization

            organization = get_request_organization(request)

        if organization is None:
            return attrs

        qs = Customer.objects.filter(organization=organization, code=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"code": "Bu müşteri kodu aynı organizasyonda zaten kullanılıyor."}
            )
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"code": "Bu müşteri kodu aynı organizasyonda zaten kullanılıyor."}
            ) from exc

    def update(self, instance, validated_data):
        from apps.customers.field_ownership import KOLAYBI_MANAGED_CUSTOMER_FIELDS
        from apps.customers.models import CustomerSource

        if instance.source == CustomerSource.KOLAYBI:
            overrides = list(instance.local_field_overrides or [])
            for field in KOLAYBI_MANAGED_CUSTOMER_FIELDS:
                if field in validated_data and validated_data[field] != getattr(instance, field):
                    if field not in overrides:
                        overrides.append(field)
            validated_data["local_field_overrides"] = overrides

        try:
            return super().update(instance, validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"code": "Bu müşteri kodu aynı organizasyonda zaten kullanılıyor."}
            ) from exc


class CustomerDetailSerializer(CustomerSerializer):
    contacts = CustomerContactSerializer(many=True, read_only=True)

    class Meta(CustomerSerializer.Meta):
        fields = (*CustomerSerializer.Meta.fields, "contacts")
