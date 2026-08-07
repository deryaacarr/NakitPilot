from rest_framework import serializers

from apps.payables.models import (
    BankAccount,
    ExpectedExpense,
    ExpenseCategory,
    Payable,
    RecurringExpense,
)


class BankAccountSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = (
            "id",
            "organization",
            "name",
            "bank_name",
            "iban",
            "currency",
            "current_balance",
            "blocked_amount",
            "available_balance",
            "is_active",
            "notes",
            "as_of",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "available_balance",
            "created_at",
            "updated_at",
        )

    def get_available_balance(self, obj: BankAccount) -> str:
        return str(obj.available_balance)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ("id", "organization", "name", "code", "is_active", "created_at")
        read_only_fields = ("id", "organization", "created_at")


class PayableSerializer(serializers.ModelSerializer):
    remaining_amount = serializers.SerializerMethodField()

    class Meta:
        model = Payable
        fields = (
            "id",
            "organization",
            "vendor_name",
            "description",
            "category",
            "due_date",
            "amount",
            "paid_amount",
            "remaining_amount",
            "currency",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
            "remaining_amount",
        )

    def get_remaining_amount(self, obj: Payable) -> str:
        return str(obj.remaining_amount)


class RecurringExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringExpense
        fields = (
            "id",
            "organization",
            "name",
            "category",
            "amount",
            "currency",
            "day_of_month",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class ExpectedExpenseSerializer(serializers.ModelSerializer):
    expected_amount = serializers.SerializerMethodField()

    class Meta:
        model = ExpectedExpense
        fields = (
            "id",
            "organization",
            "title",
            "category",
            "expected_date",
            "amount",
            "currency",
            "probability",
            "expected_amount",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "expected_amount",
            "created_at",
            "updated_at",
        )

    def get_expected_amount(self, obj: ExpectedExpense) -> str:
        return str(obj.expected_amount)
