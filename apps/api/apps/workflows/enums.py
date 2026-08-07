"""Workflow enums and condition/action vocabularies (NP-210–214)."""

from __future__ import annotations

from django.db import models


class WorkflowTriggerType(models.TextChoices):
    INVOICE_OVERDUE = "invoice_overdue", "Fatura gecikti"
    RISK_LEVEL_CHANGED = "risk_level_changed", "Risk seviyesi değişti"
    PROMISE_MADE = "promise_made", "Ödeme sözü verildi"
    PROMISE_BROKEN = "promise_broken", "Ödeme sözü bozuldu"
    PAYMENT_RECEIVED = "payment_received", "Yeni ödeme geldi"
    CUSTOMER_UNREACHABLE = "customer_unreachable", "Müşteriye ulaşılamadı"
    OPEN_BALANCE_EXCEEDED = "open_balance_exceeded", "Açık bakiye limiti aştı"
    MANUAL = "manual", "Manuel"


class WorkflowLifecycleStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class WorkflowStepType(models.TextChoices):
    TRIGGER = "trigger", "Trigger"
    CONDITION = "condition", "Condition"
    DELAY = "delay", "Delay"
    ACTION = "action", "Action"
    BRANCH = "branch", "Branch"
    STOP = "stop", "Stop"


class WorkflowEdgeHandle(models.TextChoices):
    NEXT = "next", "Next"
    TRUE = "true", "True"
    FALSE = "false", "False"


class WorkflowConditionField(models.TextChoices):
    INVOICE_OVERDUE_DAYS = "invoice.overdue_days", "Invoice overdue days"
    INVOICE_STATUS = "invoice.status", "Invoice status"
    INVOICE_REMAINING = "invoice.remaining_amount", "Invoice remaining amount"
    PROMISE_STATUS = "promise.status", "Promise status"
    PROMISE_AMOUNT = "promise.amount", "Promise amount"
    CUSTOMER_RISK_LEVEL = "customer.risk_level", "Customer risk level"
    CUSTOMER_RISK_SCORE = "customer.risk_score", "Customer risk score"
    CUSTOMER_TAGS = "customer.tags", "Customer tags"
    CUSTOMER_OPEN_BALANCE = "customer.open_balance", "Customer open balance"
    CUSTOMER_CREDIT_LIMIT = "customer.credit_limit", "Customer credit limit"
    PAYMENT_AMOUNT = "payment.amount", "Payment amount"


class WorkflowConditionOperator(models.TextChoices):
    # Canonical short forms
    EQ = "eq", "Equals"
    NE = "ne", "Not equals"
    GT = "gt", "Greater than"
    GTE = "gte", "Greater or equal"
    LT = "lt", "Less than"
    LTE = "lte", "Less or equal"
    IN = "in", "In"
    NOT_IN = "not_in", "Not in"
    CONTAINS = "contains", "Contains"
    IS_EMPTY = "is_empty", "Is empty"
    IS_NOT_EMPTY = "is_not_empty", "Is not empty"
    # Ticket aliases (NP-212) — same semantics as short forms
    EQUALS = "equals", "Equals"
    NOT_EQUALS = "not_equals", "Not equals"
    GREATER_THAN = "greater_than", "Greater than"
    LESS_THAN = "less_than", "Less than"


class WorkflowConditionLogic(models.TextChoices):
    AND = "and", "AND"
    OR = "or", "OR"


class WorkflowActionType(models.TextChoices):
    CREATE_TASK = "create_task", "Görev oluştur"
    ASSIGN_USER = "assign_user", "Kullanıcıya ata"
    NOTIFY = "notify", "Bildirim gönder"
    PREPARE_EMAIL = "prepare_email", "E-posta hazırla"
    SEND_EMAIL = "send_email", "E-posta gönder"
    RECALCULATE_RISK = "recalculate_risk", "Risk hesapla"
    ADD_TAG = "add_tag", "Etiket ekle"
    CHANGE_ASSIGNEE = "change_assignee", "Müşteri sorumlusunu değiştir"
    TRIGGER_WEBHOOK = "trigger_webhook", "Webhook tetikle"
    REQUEST_APPROVAL = "request_approval", "Yönetici onayı iste"


class WorkflowExecutionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    WAITING = "waiting", "Waiting"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class WorkflowApprovalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class WorkflowLogEvent(models.TextChoices):
    STARTED = "started", "Started"
    CONDITION_MATCH = "condition_match", "Condition matched"
    CONDITION_MISS = "condition_miss", "Condition not matched"
    ACTION_OK = "action_ok", "Action succeeded"
    ACTION_FAIL = "action_fail", "Action failed"
    STEP_SKIPPED = "step_skipped", "Step skipped"
    DELAY_SCHEDULED = "delay_scheduled", "Delay scheduled"
    DELAY_RESUMED = "delay_resumed", "Delay resumed"
    APPROVAL_REQUESTED = "approval_requested", "Approval requested"
    APPROVAL_DECIDED = "approval_decided", "Approval decided"
    BRANCH_TAKEN = "branch_taken", "Branch taken"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
