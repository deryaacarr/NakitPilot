"""NP-210/211 — Collection workflow models and seed graph."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.customers.models import Customer
from apps.organizations.models import Membership, Organization, Role
from apps.workflows.condition_engine import evaluate_expression, evaluate_step_conditions
from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowExecutionStatus,
    WorkflowLogEvent,
    WorkflowStepType,
    WorkflowTriggerType,
)
from apps.workflows.models import (
    CollectionWorkflow,
    WorkflowExecution,
    WorkflowExecutionLog,
)
from apps.workflows.seed import seed_default_collection_workflows

User = get_user_model()


@pytest.fixture
def org_owner(db):
    org = Organization.objects.create(name="NP210 Org", slug="np210-org")
    owner = User.objects.create_user(email="np210-owner@example.com", password="SecretPass123!")
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.mark.django_db
def test_seed_default_workflows_structure(org_owner):
    org, owner = org_owner
    created = seed_default_collection_workflows(organization=org, created_by=owner)
    assert len(created) == 2

    overdue = CollectionWorkflow.objects.get(organization=org, trigger_type=WorkflowTriggerType.INVOICE_OVERDUE)
    assert overdue.steps.filter(step_type=WorkflowStepType.TRIGGER).count() == 1
    assert overdue.steps.filter(step_type=WorkflowStepType.BRANCH).count() == 3
    assert overdue.edges.count() >= 8
    email_action = overdue.steps.get(client_key="action-email")
    assert email_action.config["action_type"] == WorkflowActionType.CREATE_TASK
    assert email_action.config["params"]["task_type"] == "EMAIL"

    promise_wf = CollectionWorkflow.objects.get(
        organization=org, trigger_type=WorkflowTriggerType.PROMISE_BROKEN
    )
    action_types = {
        s.config.get("action_type")
        for s in promise_wf.steps.filter(step_type=WorkflowStepType.ACTION)
    }
    assert WorkflowActionType.CREATE_TASK in action_types
    assert WorkflowActionType.RECALCULATE_RISK in action_types
    assert WorkflowActionType.NOTIFY in action_types

    again = seed_default_collection_workflows(organization=org, created_by=owner)
    assert again == []
    assert CollectionWorkflow.objects.filter(organization=org).count() == 2


@pytest.mark.django_db
def test_overdue_step_conditions_match_tiers(org_owner):
    org, owner = org_owner
    seed_default_collection_workflows(organization=org, created_by=owner)
    overdue = CollectionWorkflow.objects.get(trigger_type=WorkflowTriggerType.INVOICE_OVERDUE)
    b7 = overdue.steps.get(client_key="branch-7")
    b14 = overdue.steps.get(client_key="branch-14")
    b30 = overdue.steps.get(client_key="branch-30")

    assert evaluate_step_conditions(b7, {"invoice": {"overdue_days": 7}}) is True
    assert evaluate_step_conditions(b7, {"invoice": {"overdue_days": 10}}) is True
    assert evaluate_step_conditions(b7, {"invoice": {"overdue_days": 14}}) is False

    assert evaluate_step_conditions(b14, {"invoice": {"overdue_days": 14}}) is True
    assert evaluate_step_conditions(b14, {"invoice": {"overdue_days": 29}}) is True
    assert evaluate_step_conditions(b14, {"invoice": {"overdue_days": 30}}) is False

    assert evaluate_step_conditions(b30, {"invoice": {"overdue_days": 30}}) is True
    assert evaluate_step_conditions(b30, {"invoice": {"overdue_days": 90}}) is True
    assert evaluate_step_conditions(b30, {"invoice": {"overdue_days": 5}}) is False


@pytest.mark.django_db
def test_nested_expression_operators():
    ctx = {
        "invoice": {"overdue_days": 35},
        "customer": {"risk_status": "HIGH", "tags": ["vip"], "risk_level": "HIGH"},
    }
    expr = {
        "all": [
            {"field": "invoice.overdue_days", "operator": "greater_than", "value": 30},
            {"field": "customer.risk_level", "operator": "in", "value": ["HIGH", "CRITICAL"]},
        ]
    }
    assert evaluate_expression(expr, ctx) is True
    assert evaluate_expression(
        {"any": [{"field": "customer.tags", "operator": "contains", "value": "vip"}]},
        ctx,
    )
    assert evaluate_expression(
        {"all": [{"field": "customer.notes", "operator": "is_empty", "value": None}]},
        {"customer": {"notes": ""}},
    )


@pytest.mark.django_db
def test_execution_and_log_models(org_owner):
    org, owner = org_owner
    seed_default_collection_workflows(organization=org, created_by=owner)
    workflow = CollectionWorkflow.objects.get(trigger_type=WorkflowTriggerType.PROMISE_BROKEN)
    customer = Customer.objects.create(organization=org, name="WF Customer")

    execution = WorkflowExecution.objects.create(
        organization=org,
        workflow=workflow,
        trigger_type=WorkflowTriggerType.PROMISE_BROKEN,
        trigger_entity_type="collections.PaymentPromise",
        trigger_entity_id="99",
        customer=customer,
        status=WorkflowExecutionStatus.SUCCEEDED,
        idempotency_key="promise:99:broken",
        context={"promise": {"status": "BROKEN"}},
    )
    WorkflowExecutionLog.objects.create(
        organization=org,
        execution=execution,
        event=WorkflowLogEvent.STARTED,
        message="started",
    )
    WorkflowExecutionLog.objects.create(
        organization=org,
        execution=execution,
        step=workflow.steps.first(),
        event=WorkflowLogEvent.ACTION_OK,
        message="critical task created",
        payload={"task_id": 1},
    )
    assert execution.logs.count() == 2

    with pytest.raises(IntegrityError):
        WorkflowExecution.objects.create(
            organization=org,
            workflow=workflow,
            trigger_type=WorkflowTriggerType.PROMISE_BROKEN,
            trigger_entity_type="collections.PaymentPromise",
            trigger_entity_id="99",
            customer=customer,
            idempotency_key="promise:99:broken",
        )
