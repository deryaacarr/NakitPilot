"""NP-212–214 engine, business days, actions, API."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.collections.models import CollectionTask
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, OrganizationHoliday, Role
from apps.workflows.business_days import add_business_days, compute_resume_at
from apps.workflows.engine import (
    dispatch_trigger,
    org_has_active_workflow,
    process_due_resumes,
    resume_execution,
    run_workflow,
)
from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowEdgeHandle,
    WorkflowExecutionStatus,
    WorkflowStepType,
    WorkflowTriggerType,
)
from apps.workflows.models import CollectionWorkflow, WorkflowEdge, WorkflowStep
from apps.workflows.seed import seed_default_collection_workflows
from apps.workflows.services import replace_workflow_graph

User = get_user_model()


@pytest.fixture
def org_owner(db):
    org = Organization.objects.create(name="NP214 Org", slug="np214-org", working_days=[1, 2, 3, 4, 5])
    owner = User.objects.create_user(email="np214-owner@example.com", password="SecretPass123!")
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.fixture
def auth_client(org_owner):
    org, owner = org_owner
    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": owner.email, "password": "SecretPass123!"},
        format="json",
    )
    assert login.status_code == 200, login.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return client, org, owner


def test_add_business_days_skips_weekend_and_holiday():
    # Friday 2026-07-31 → +1 business day = Monday 2026-08-03
    assert add_business_days(date(2026, 7, 31), 1) == date(2026, 8, 3)
    # With Monday holiday → Tuesday
    assert add_business_days(
        date(2026, 7, 31), 1, holidays=[date(2026, 8, 3)]
    ) == date(2026, 8, 4)


@pytest.mark.django_db
def test_compute_resume_uses_org_holidays(org_owner):
    org, _ = org_owner
    OrganizationHoliday.objects.create(organization=org, date=date(2026, 8, 3), name="Bayram")
    start = timezone.make_aware(datetime(2026, 7, 31, 10, 0, 0))
    resume = compute_resume_at(amount=1, unit="business_days", organization=org, from_dt=start)
    assert resume.date() == date(2026, 8, 4)


@pytest.mark.django_db
def test_engine_runs_promise_seed(org_owner):
    org, owner = org_owner
    seed_default_collection_workflows(organization=org, created_by=owner)
    customer = Customer.objects.create(organization=org, name="C1", assigned_user=owner)
    wf = CollectionWorkflow.objects.get(trigger_type=WorkflowTriggerType.PROMISE_BROKEN)
    execution = run_workflow(
        wf,
        customer=customer,
        context={"promise": {"status": "BROKEN"}, "customer": {"risk_level": "LOW"}},
        idempotency_key="t1",
    )
    assert execution.status == WorkflowExecutionStatus.SUCCEEDED
    assert CollectionTask.objects.filter(customer=customer).exists()
    customer.refresh_from_db()
    # risk may update
    assert execution.logs.filter(event="action_ok").count() >= 1


@pytest.mark.django_db
def test_delay_then_resume(org_owner):
    org, owner = org_owner
    customer = Customer.objects.create(organization=org, name="Delay Cust")
    wf = CollectionWorkflow.objects.create(
        organization=org,
        name="Delay demo",
        trigger_type=WorkflowTriggerType.MANUAL,
        is_active=True,
    )
    t = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="T", step_type=WorkflowStepType.TRIGGER,
        order=0, client_key="t",
    )
    d = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="Wait", step_type=WorkflowStepType.DELAY,
        order=1, client_key="d",
        config={"amount": 1, "unit": "hours"},
    )
    a = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="Tag", step_type=WorkflowStepType.ACTION,
        order=2, client_key="a",
        config={"action_type": WorkflowActionType.ADD_TAG, "params": {"tag": "waited"}},
    )
    s = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="Stop", step_type=WorkflowStepType.STOP,
        order=3, client_key="s",
    )
    for frm, to in ((t, d), (d, a), (a, s)):
        WorkflowEdge.objects.create(
            organization=org, workflow=wf, from_step=frm, to_step=to,
            source_handle=WorkflowEdgeHandle.NEXT,
        )

    execution = run_workflow(wf, customer=customer, context={}, idempotency_key="delay-1")
    assert execution.status == WorkflowExecutionStatus.WAITING
    assert execution.resume_at is not None

    execution.resume_at = timezone.now() - timedelta(minutes=1)
    execution.save(update_fields=["resume_at"])
    process_due_resumes()
    execution.refresh_from_db()
    assert execution.status == WorkflowExecutionStatus.SUCCEEDED
    customer.refresh_from_db()
    assert "waited" in (customer.tags or [])


@pytest.mark.django_db
def test_overdue_gate_uses_workflow(org_owner):
    from apps.collections.services import generate_overdue_invoice_collection_tasks

    org, owner = org_owner
    seed_default_collection_workflows(organization=org, created_by=owner)
    assert org_has_active_workflow(org, WorkflowTriggerType.INVOICE_OVERDUE)
    customer = Customer.objects.create(organization=org, name="Inv Cust")
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-WF-1",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 1),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.OVERDUE,
    )
    result = generate_overdue_invoice_collection_tasks(organization=org, as_of=date(2026, 7, 1))
    assert result["workflows_dispatched"] >= 1
    # Seed creates task via workflow for 30+ days
    assert CollectionTask.objects.filter(organization=org, customer=customer).exists()


@pytest.mark.django_db
def test_graph_api_roundtrip(auth_client):
    client, org, owner = auth_client
    create = client.post(
        "/api/workflows/",
        {"name": "API WF", "trigger_type": "manual", "description": "x"},
        format="json",
    )
    assert create.status_code == 201, create.content
    wf_id = create.data["id"]

    graph = {
        "steps": [
            {
                "client_key": "trigger",
                "name": "Start",
                "step_type": "trigger",
                "position_x": 0,
                "position_y": 0,
                "config": {},
            },
            {
                "client_key": "act",
                "name": "Tag",
                "step_type": "action",
                "position_x": 200,
                "position_y": 0,
                "config": {"action_type": "add_tag", "params": {"tag": "api"}},
            },
            {
                "client_key": "stop",
                "name": "End",
                "step_type": "stop",
                "position_x": 400,
                "position_y": 0,
                "config": {},
            },
        ],
        "edges": [
            {"source": "trigger", "target": "act", "source_handle": "next"},
            {"source": "act", "target": "stop", "source_handle": "next"},
        ],
    }
    put = client.put(f"/api/workflows/{wf_id}/graph/", graph, format="json")
    assert put.status_code == 200, put.content
    assert len(put.data["graph"]["steps"]) == 3
    assert len(put.data["graph"]["edges"]) == 2

    customer = Customer.objects.create(organization=org, name="API Cust")
    run = client.post(
        f"/api/workflows/{wf_id}/test-run/",
        {"customer_id": customer.id, "context": {}},
        format="json",
    )
    assert run.status_code == 200, run.content
    assert run.data["status"] == "succeeded"
    customer.refresh_from_db()
    assert "api" in customer.tags


@pytest.mark.django_db
def test_replace_graph_rejects_self_loop(org_owner):
    org, _ = org_owner
    wf = CollectionWorkflow.objects.create(
        organization=org, name="Bad", trigger_type=WorkflowTriggerType.MANUAL
    )
    with pytest.raises(Exception):
        replace_workflow_graph(
            wf,
            steps=[{"client_key": "a", "step_type": "action", "name": "A"}],
            edges=[{"source": "a", "target": "a", "source_handle": "next"}],
        )
