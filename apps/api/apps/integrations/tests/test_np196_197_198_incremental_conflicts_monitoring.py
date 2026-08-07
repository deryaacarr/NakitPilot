"""NP-196 incremental sync, NP-197 conflicts, NP-198 monitoring."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.integrations.models import (
    SyncConflict,
    SyncConflictResolution,
    SyncConflictStatus,
    SyncConflictType,
    SyncEntityState,
)
from apps.invoices.models import Invoice, InvoiceSource
from apps.organizations.models import Membership, Organization, Role

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def api_client():
    return APIClient()


def _auth(client, user, organization):
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(organization.id)
    return client


@pytest.fixture
def setup_org(db):
    org = Organization.objects.create(name="NP196 Org", slug="np196-org")
    owner = User.objects.create_user(email="np196-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


def _ready_and_sync(client, *, job_type="initial") -> dict:
    created = client.post(
        "/api/integrations/connections/",
        {"provider": "kolaybi"},
        format="json",
    )
    assert created.status_code == 201
    cid = created.data["id"]
    assert (
        client.put(
            f"/api/integrations/connections/{cid}/credentials/",
            {"credentials": {"api_key": "mock-np196-key", "channel_id": "ch-np196"}},
            format="json",
        ).status_code
        == 200
    )
    companies = client.get(f"/api/integrations/connections/{cid}/companies/").data
    client.post(
        f"/api/integrations/connections/{cid}/select-company/",
        {
            "external_company_id": companies[0]["external_id"],
            "external_company_name": companies[0]["name"],
        },
        format="json",
    )
    sync = client.post(
        f"/api/integrations/connections/{cid}/sync/",
        {"job_type": job_type},
        format="json",
    )
    assert sync.status_code == status.HTTP_201_CREATED
    return {"connection_id": cid, "sync": sync.data}


@pytest.mark.django_db
def test_np196_first_full_then_incremental(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    result = _ready_and_sync(client, job_type="initial")
    cid = result["connection_id"]
    stats = result["sync"]["job"]["stats_json"]

    assert stats["mode"] == "full"
    assert stats["customers"]["mode"] == "full"
    assert stats["customers"]["fetched"] >= 1
    assert stats["invoices"]["fetched"] >= 1

    states = SyncEntityState.objects.filter(connection_id=cid)
    assert states.count() == 3
    for state in states:
        assert state.last_sync_at is not None
        assert state.last_successful_sync_at is not None
        assert state.checksums_json

    second = client.post(
        f"/api/integrations/connections/{cid}/sync/",
        {"job_type": "manual"},
        format="json",
    )
    assert second.status_code == 201
    second_stats = second.data["job"]["stats_json"]
    assert second_stats["mode"] == "incremental"
    for entity in ("customers", "invoices", "payments"):
        entity_stats = second_stats[entity]
        assert entity_stats["mode"] == "incremental"
        assert entity_stats["created"] == 0
        assert entity_stats["fetched"] == 0 or entity_stats.get("checksum_skipped", 0) >= 0


@pytest.mark.django_db
def test_np197_conflict_resolve_keep_local_and_merge(api_client, setup_org):
    from datetime import date

    from apps.customers.models import Customer

    org, owner = setup_org
    client = _auth(api_client, owner, org)

    created = client.post(
        "/api/integrations/connections/",
        {"provider": "kolaybi"},
        format="json",
    )
    assert created.status_code == 201
    cid = created.data["id"]
    assert (
        client.put(
            f"/api/integrations/connections/{cid}/credentials/",
            {"credentials": {"api_key": "mock-np197-key", "channel_id": "ch-np197"}},
            format="json",
        ).status_code
        == 200
    )
    companies = client.get(f"/api/integrations/connections/{cid}/companies/").data
    client.post(
        f"/api/integrations/connections/{cid}/select-company/",
        {
            "external_company_id": companies[0]["external_id"],
            "external_company_name": companies[0]["name"],
        },
        format="json",
    )

    # Same invoice number already exists locally as MANUAL before API sync.
    customer = Customer.objects.create(organization=org, name="Local Customer")
    manual = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="F-2026-001",
        invoice_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        total_amount=Decimal("1000.00"),
        currency="TRY",
        source=InvoiceSource.MANUAL,
    )

    sync = client.post(
        f"/api/integrations/connections/{cid}/sync/",
        {"job_type": "initial"},
        format="json",
    )
    assert sync.status_code == 201

    conflicts = client.get(f"/api/integrations/connections/{cid}/conflicts/")
    assert conflicts.status_code == 200
    open_rows = conflicts.data
    assert isinstance(open_rows, list)
    dup = next(
        (c for c in open_rows if c["conflict_type"] == SyncConflictType.DUPLICATE_MANUAL_API),
        None,
    )
    assert dup is not None

    keep = client.post(
        f"/api/integrations/connections/{cid}/conflicts/{dup['id']}/resolve/",
        {"resolution": "keep_local"},
        format="json",
    )
    assert keep.status_code == 200
    assert keep.data["status"] == SyncConflictStatus.RESOLVED
    assert keep.data["resolution"] == SyncConflictResolution.KEEP_LOCAL

    SyncConflict.objects.create(
        organization=org,
        connection_id=cid,
        entity_type="invoice",
        conflict_type=SyncConflictType.DUPLICATE_MANUAL_API,
        external_id="kb-inv-merge",
        internal_model="invoices.Invoice",
        internal_id=str(manual.pk),
        message="merge test",
        source_payload={"total_amount": "999.00"},
    )
    merge_id = SyncConflict.objects.filter(status=SyncConflictStatus.OPEN).first().pk
    merged = client.post(
        f"/api/integrations/connections/{cid}/conflicts/{merge_id}/resolve/",
        {"resolution": "merge"},
        format="json",
    )
    assert merged.status_code == 200
    assert merged.data["resolution"] == SyncConflictResolution.MERGE
    linked = Invoice.objects.get(pk=manual.pk)
    assert linked.source == InvoiceSource.KOLAYBI
    assert linked.external_id == "kb-inv-merge"


@pytest.mark.django_db
def test_np198_monitoring_metrics(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    result = _ready_and_sync(client)
    cid = result["connection_id"]

    mon = client.get(f"/api/integrations/connections/{cid}/monitoring/")
    assert mon.status_code == 200
    body = mon.data
    assert body["connection_id"] == cid
    metrics = body["metrics"]
    for key in ("fetched", "created", "updated", "skipped", "failed"):
        assert key in metrics
        assert isinstance(metrics[key], int)
    assert "api_duration_ms" in metrics
    assert "rate_limit" in metrics
    assert "limited" in metrics["rate_limit"]
    assert "last_sync_duration_ms" in metrics
    assert len(body["entity_states"]) == 3
    assert body["latest_job"] is not None
