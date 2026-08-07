"""NP-215/216 simulation + versioning tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.customers.features import FEATURE_NAMES, extract_customer_features
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.organizations.models import Membership, Organization, Role
from apps.workflows.enums import (
    WorkflowActionType,
    WorkflowEdgeHandle,
    WorkflowLifecycleStatus,
    WorkflowStepType,
    WorkflowTriggerType,
)
from apps.workflows.models import CollectionWorkflow, WorkflowEdge, WorkflowStep
from apps.workflows.seed import seed_default_collection_workflows
from apps.workflows.simulate import dry_run_workflow, simulate_workflow
from apps.workflows.versioning import publish_workflow
from apps.workflows.services import WorkflowServiceError, replace_workflow_graph

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def org_owner(db):
    org = Organization.objects.create(name="NP216 Org", slug="np216-org")
    owner = User.objects.create_user(email="np216@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.fixture
def auth_client(org_owner):
    org, owner = org_owner
    client = APIClient()
    login = client.post("/api/auth/login", {"email": owner.email, "password": PASSWORD}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return client, org, owner


def _simple_draft(org, owner):
    wf = CollectionWorkflow.objects.create(
        organization=org,
        name="Draft Sim",
        trigger_type=WorkflowTriggerType.INVOICE_OVERDUE,
        status=WorkflowLifecycleStatus.DRAFT,
        workflow_key="family-1",
        version=1,
        is_active=False,
        created_by=owner,
    )
    t = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="T", step_type=WorkflowStepType.TRIGGER,
        order=0, client_key="t",
    )
    a = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="Task", step_type=WorkflowStepType.ACTION,
        order=1, client_key="a",
        config={"action_type": WorkflowActionType.CREATE_TASK, "params": {"title": "X"}},
    )
    n = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="Notify", step_type=WorkflowStepType.ACTION,
        order=2, client_key="n",
        config={
            "action_type": WorkflowActionType.NOTIFY,
            "params": {"severity": "critical", "title": "Crit"},
        },
    )
    s = WorkflowStep.objects.create(
        organization=org, workflow=wf, name="Stop", step_type=WorkflowStepType.STOP,
        order=3, client_key="s",
    )
    for frm, to in ((t, a), (a, n), (n, s)):
        WorkflowEdge.objects.create(
            organization=org, workflow=wf, from_step=frm, to_step=to,
            source_handle=WorkflowEdgeHandle.NEXT,
        )
    return wf


@pytest.mark.django_db
def test_publish_creates_new_draft_and_archives_previous(org_owner):
    org, owner = org_owner
    draft = _simple_draft(org, owner)
    result = publish_workflow(draft, actor=owner)
    published = result["published"]
    new_draft = result["draft"]
    assert published.status == WorkflowLifecycleStatus.PUBLISHED
    assert published.is_active is True
    assert new_draft.status == WorkflowLifecycleStatus.DRAFT
    assert new_draft.version == published.version + 1
    assert new_draft.workflow_key == published.workflow_key
    assert new_draft.steps.count() == published.steps.count()

    # Second publish of new draft archives first published
    result2 = publish_workflow(new_draft, actor=owner)
    published.refresh_from_db()
    assert published.status == WorkflowLifecycleStatus.ARCHIVED
    assert published.is_active is False
    assert result2["published"].status == WorkflowLifecycleStatus.PUBLISHED


@pytest.mark.django_db
def test_published_graph_not_editable(org_owner):
    org, owner = org_owner
    draft = _simple_draft(org, owner)
    published = publish_workflow(draft, actor=owner)["published"]
    with pytest.raises(WorkflowServiceError):
        replace_workflow_graph(
            published,
            steps=[{"client_key": "t", "step_type": "trigger", "name": "T"}],
            edges=[],
        )


@pytest.mark.django_db
def test_dry_run_counts_actions(org_owner):
    org, owner = org_owner
    wf = _simple_draft(org, owner)
    counters = dry_run_workflow(wf, {"invoice": {"overdue_days": 10}}, customer_id=1)
    assert counters.tasks_created == 1
    assert counters.critical_notifications == 1


@pytest.mark.django_db
def test_simulate_overdue_history(org_owner):
    org, owner = org_owner
    seed_default_collection_workflows(organization=org, created_by=owner)
    wf = CollectionWorkflow.objects.get(trigger_type=WorkflowTriggerType.INVOICE_OVERDUE)
    customer = Customer.objects.create(organization=org, name="Sim Cust")
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="SIM-1",
        invoice_date=date(2026, 5, 1),
        due_date=timezone.localdate() - timedelta(days=40),
        total_amount=Decimal("500.00"),
        status=InvoiceStatus.OVERDUE,
    )
    result = simulate_workflow(wf, days=30)
    assert result["events_evaluated"] >= 1
    assert result["tasks_created"] >= 1
    assert "headline" in result


@pytest.mark.django_db
def test_simulate_api(auth_client):
    client, org, owner = auth_client
    seed_default_collection_workflows(organization=org, created_by=owner)
    wf = CollectionWorkflow.objects.get(trigger_type=WorkflowTriggerType.PROMISE_BROKEN)
    res = client.post(f"/api/workflows/{wf.id}/simulate/", {"days": 30}, format="json")
    assert res.status_code == 200, res.content
    assert "tasks_created" in res.data
    assert "headline" in res.data


@pytest.mark.django_db
def test_feature_extraction(org_owner):
    org, owner = org_owner
    customer = Customer.objects.create(
        organization=org, name="Feat Cust", credit_limit=Decimal("1000.00")
    )
    Invoice.objects.create(
        organization=org,
        customer=customer,
        number="F-1",
        invoice_date=date(2026, 1, 1),
        due_date=date(2026, 1, 10),
        total_amount=Decimal("100.00"),
        status=InvoiceStatus.PAID,
        payment_completion_date=date(2026, 1, 20),
    )
    payload = extract_customer_features(customer)
    feats = payload["features"]
    for name in FEATURE_NAMES:
        assert name in feats
    assert feats["average_payment_delay"] == 10
    assert feats["median_payment_delay"] == 10
    assert feats["on_time_payment_ratio"] == 0.0


@pytest.mark.django_db
def test_customer_features_api(auth_client):
    client, org, owner = auth_client
    customer = Customer.objects.create(organization=org, name="API Feat")
    res = client.get(f"/api/customers/{customer.id}/features/")
    assert res.status_code == 200, res.content
    assert set(FEATURE_NAMES).issubset(set(res.data["features"].keys()))
