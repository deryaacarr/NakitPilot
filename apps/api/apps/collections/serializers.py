from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.collections.models import (
    CallOutcome,
    CollectionTask,
    CollectionTaskStatus,
    CollectionTaskType,
)
from apps.collections.services import (
    CollectionValidationError,
    assign_tasks,
    cancel_task,
    complete_task,
    create_task,
)
from apps.customers.metrics import customer_financial_metrics
from apps.customers.models import Customer
from apps.invoices.models import Invoice

User = get_user_model()


class CollectionTaskSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_risk_status = serializers.CharField(source="customer.risk_status", read_only=True)
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    overdue_balance = serializers.SerializerMethodField()
    overdue_days = serializers.SerializerMethodField()
    last_contact_at = serializers.DateTimeField(source="customer.last_contact_at", read_only=True)
    payment_promise = serializers.SerializerMethodField()
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)

    class Meta:
        model = CollectionTask
        fields = (
            "id",
            "organization",
            "customer",
            "customer_name",
            "customer_risk_status",
            "invoice",
            "invoice_number",
            "related_promise",
            "task_type",
            "status",
            "priority",
            "priority_score",
            "title",
            "description",
            "due_date",
            "assigned_to",
            "assigned_to_email",
            "assigned_to_name",
            "created_by",
            "source",
            "outcome",
            "outcome_notes",
            "callback_date",
            "completed_at",
            "cancelled_at",
            "cancellation_reason",
            "overdue_balance",
            "overdue_days",
            "last_contact_at",
            "payment_promise",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "priority",
            "priority_score",
            "created_by",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
            "customer_name",
            "customer_risk_status",
            "assigned_to_email",
            "assigned_to_name",
            "overdue_balance",
            "overdue_days",
            "last_contact_at",
            "payment_promise",
            "invoice_number",
        )

    def get_assigned_to_name(self, obj: CollectionTask) -> str | None:
        user = obj.assigned_to
        if user is None:
            return None
        full = f"{user.first_name} {user.last_name}".strip()
        return full or user.email

    def get_overdue_balance(self, obj: CollectionTask) -> str:
        return str(customer_financial_metrics(obj.customer)["overdue_balance"])

    def get_overdue_days(self, obj: CollectionTask) -> int | None:
        return customer_financial_metrics(obj.customer)["oldest_overdue_days"]

    def get_payment_promise(self, obj: CollectionTask) -> dict | None:
        promise = obj.related_promise
        if promise is None:
            # nearest pending promise
            promise = (
                obj.customer.payment_promises.filter(status="PENDING")
                .order_by("promised_date")
                .first()
            )
        if promise is None:
            return None
        return {
            "id": promise.id,
            "promised_date": promise.promised_date.isoformat(),
            "amount": str(promise.amount),
            "status": promise.status,
        }


class CollectionTaskCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    invoice = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(), required=False, allow_null=True
    )
    task_type = serializers.ChoiceField(choices=CollectionTaskType.choices, required=False)
    title = serializers.CharField(required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    due_date = serializers.DateField()
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    def create(self, validated_data):
        request = self.context["request"]
        organization = self.context["organization"]
        try:
            task = create_task(
                organization=organization,
                customer=validated_data["customer"],
                due_date=validated_data["due_date"],
                title=validated_data.get("title") or "",
                description=validated_data.get("description") or "",
                task_type=validated_data.get("task_type") or CollectionTaskType.CALL,
                assigned_to=validated_data.get("assigned_to"),
                created_by=request.user,
                invoice=validated_data.get("invoice"),
            )
        except CollectionValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc
        return task


class CollectionTaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionTask
        fields = (
            "task_type",
            "title",
            "description",
            "due_date",
            "assigned_to",
            "status",
        )

    def validate_status(self, value: str) -> str:
        if value in {CollectionTaskStatus.COMPLETED, CollectionTaskStatus.CANCELLED}:
            raise serializers.ValidationError(
                "Tamamlama/iptal için ilgili endpointleri kullanın."
            )
        return value

    def update(self, instance, validated_data):
        assignee = validated_data.get("assigned_to", serializers.empty)
        if assignee is not serializers.empty and assignee is not None and not assignee.is_active:
            self.context["assign_warning"] = "assigned_user_inactive"
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        from apps.collections.services import refresh_task_priority

        refresh_task_priority(instance)
        return instance


class CompleteTaskSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=CallOutcome.choices)
    outcome_notes = serializers.CharField()
    create_follow_up = serializers.BooleanField(required=False, default=False)
    promise_given = serializers.BooleanField(required=False, default=False)
    callback_date = serializers.DateField(required=False, allow_null=True)
    promise_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0.01")
    )
    promise_date = serializers.DateField(required=False, allow_null=True)

    def save(self, **kwargs):
        task: CollectionTask = self.context["task"]
        actor = self.context["request"].user
        try:
            return complete_task(
                task,
                actor=actor,
                outcome=self.validated_data["outcome"],
                outcome_notes=self.validated_data["outcome_notes"],
                create_follow_up=bool(self.validated_data.get("create_follow_up")),
                promise_given=bool(self.validated_data.get("promise_given")),
                callback_date=self.validated_data.get("callback_date"),
                promise_amount=self.validated_data.get("promise_amount"),
                promise_date=self.validated_data.get("promise_date"),
            )
        except CollectionValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc


class CancelTaskSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        task: CollectionTask = self.context["task"]
        try:
            return cancel_task(
                task,
                actor=self.context["request"].user,
                reason=self.validated_data.get("reason", ""),
            )
        except CollectionValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc


class BulkAssignSerializer(serializers.Serializer):
    task_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    def save(self, **kwargs):
        organization = self.context["organization"]
        try:
            return assign_tasks(
                organization=organization,
                task_ids=self.validated_data["task_ids"],
                assigned_to=self.validated_data["assigned_to"],
                actor=self.context["request"].user,
            )
        except CollectionValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc


class ParseNotesSerializer(serializers.Serializer):
    """NP-232 — draft only."""

    raw_notes = serializers.CharField()

    def create(self, validated_data):
        from apps.collections.note_parser import parse_call_notes

        return parse_call_notes(validated_data["raw_notes"])


class ConfirmStructuredNotesSerializer(serializers.Serializer):
    """NP-232 — persist only after explicit confirmation."""

    raw_notes = serializers.CharField()
    promised_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0.01")
    )
    promised_date = serializers.DateField(required=False, allow_null=True)
    next_action_date = serializers.DateField(required=False, allow_null=True)
    sentiment = serializers.ChoiceField(
        choices=["positive", "neutral", "negative"],
        required=False,
        default="neutral",
    )
    objection = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    complete_task = serializers.BooleanField(required=False, default=False)
    confirmed = serializers.BooleanField()

    def validate(self, attrs):
        if not attrs.get("confirmed"):
            raise serializers.ValidationError(
                {"confirmed": "Onay olmadan kayıt oluşturulamaz."}
            )
        amount = attrs.get("promised_amount")
        pdate = attrs.get("promised_date")
        if (amount is None) ^ (pdate is None):
            raise serializers.ValidationError(
                {"promised_amount": "Ödeme sözü için tutar ve tarih birlikte gerekli."}
            )
        return attrs

    def save(self, **kwargs):
        from apps.collections.services import confirm_structured_call_notes

        task: CollectionTask = self.context["task"]
        try:
            return confirm_structured_call_notes(
                task,
                actor=self.context["request"].user,
                raw_notes=self.validated_data["raw_notes"],
                promised_amount=self.validated_data.get("promised_amount"),
                promised_date=self.validated_data.get("promised_date"),
                next_action_date=self.validated_data.get("next_action_date"),
                sentiment=self.validated_data.get("sentiment") or "neutral",
                objection=(self.validated_data.get("objection") or None) or None,
                complete_task_flag=bool(self.validated_data.get("complete_task")),
            )
        except CollectionValidationError as exc:
            raise serializers.ValidationError({"code": exc.code, "detail": exc.message}) from exc


class AcceptPaymentPlanSerializer(serializers.Serializer):
    """NP-234 — persist plan only after explicit confirmation."""

    option_id = serializers.ChoiceField(
        choices=[
            "UPFRONT_PLUS_INSTALLMENTS",
            "WEEKLY",
            "OLDEST_INVOICES_FIRST",
        ]
    )
    confirmed = serializers.BooleanField()

    def validate(self, attrs):
        if not attrs.get("confirmed"):
            raise serializers.ValidationError(
                {"confirmed": "Onay olmadan ödeme planı kaydedilemez."}
            )
        return attrs
