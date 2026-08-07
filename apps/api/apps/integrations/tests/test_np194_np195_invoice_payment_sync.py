"""NP-194 / NP-195 — KolayBi invoice + payment sync."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.customers.models import Customer, CustomerSource
from apps.invoices.models import Invoice, InvoiceSource, InvoiceStatus
from apps.payments.models import Payment, PaymentAllocation, PaymentSource
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
    org = Organization.objects.create(name="NP194 Org", slug="np194-org")
    owner = User.objects.create_user(email="np194-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


def _ready_and_sync(client) -> dict:
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
            {"credentials": {"api_key": "mock-np194-key", "channel_id": "ch-np194"}},
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
        {"job_type": "initial"},
        format="json",
    )
    assert sync.status_code == status.HTTP_201_CREATED
    return {"connection_id": cid, "sync": sync.data}


@pytest.mark.django_db
def test_invoice_sync_paginated_unique_and_cancelled(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    result = _ready_and_sync(client)

    inv_stats = result["sync"]["job"]["stats_json"]["invoices"]
    assert inv_stats["pages"] >= 2
    assert inv_stats["fetched"] == 4
    assert inv_stats["created"] == 4
    assert inv_stats["cancelled"] >= 1

    invoices = Invoice.objects.filter(organization=org, source=InvoiceSource.KOLAYBI)
    assert invoices.count() == 4
    cancelled = invoices.get(external_id="kb-inv-3")
    assert cancelled.status == InvoiceStatus.CANCELLED
    assert cancelled.cancelled_at is not None

    # money quantized
    inv1 = invoices.get(external_id="kb-inv-1")
    assert inv1.total_amount == Decimal("1000.00")
    assert inv1.currency == "TRY"

    # second sync — no duplicates
    again = client.post(
        f"/api/integrations/connections/{result['connection_id']}/sync/",
        {"job_type": "manual"},
        format="json",
    )
    assert again.status_code == 201
    assert again.data["job"]["stats_json"]["invoices"]["created"] == 0
    assert Invoice.objects.filter(organization=org, source=InvoiceSource.KOLAYBI).count() == 4


@pytest.mark.django_db
def test_invoice_local_payment_conflict_blocks_total_reduction(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    result = _ready_and_sync(client)
    invoice = Invoice.objects.get(organization=org, external_id="kb-inv-2")
    customer = invoice.customer

    # Local (MANUAL) payment allocated against synced invoice
    from apps.payments.models import Payment, PaymentAllocation

    payment = Payment.objects.create(
        organization=org,
        customer=customer,
        payment_date="2026-02-01",
        amount=Decimal("200.00"),
        currency="TRY",
        unallocated_amount=Decimal("0.00"),
        source=PaymentSource.MANUAL,
    )
    PaymentAllocation.objects.create(
        organization=org,
        payment=payment,
        invoice=invoice,
        amount=Decimal("200.00"),
    )

    # Force a re-sync after mutating mock would require client change; instead call upsert
    # with a reduced total via service directly.
    from apps.integrations.connection_actions import _bound_connector
    from apps.integrations.connectors.types import NormalizedInvoice
    from apps.integrations.models import IntegrationConnection, SyncJob
    from apps.integrations.sync_invoices import _upsert_invoice
    from datetime import date

    connection = IntegrationConnection.objects.get(pk=result["connection_id"])
    job = SyncJob.objects.create(
        organization=org,
        connection=connection,
        job_type="manual",
        status="running",
    )
    item = NormalizedInvoice(
        external_id="kb-inv-2",
        external_customer_id=customer.external_id,
        number=invoice.number,
        invoice_date=date(2026, 1, 15),
        due_date=date(2026, 2, 15),
        currency="TRY",
        total_amount=Decimal("50.00"),  # below local allocation 200
        status="open",
    )
    _upsert_invoice(connection, InvoiceSource.KOLAYBI, item, job)
    invoice.refresh_from_db()
    assert invoice.total_amount == Decimal("250.50")  # unchanged
    assert job.errors.filter(code="invoice_local_payment_conflict").exists()


@pytest.mark.django_db
def test_payment_sync_match_allocate_unallocated_no_dup_cancel(api_client, setup_org):
    org, owner = setup_org
    client = _auth(api_client, owner, org)
    result = _ready_and_sync(client)

    pay_stats = result["sync"]["job"]["stats_json"]["payments"]
    assert pay_stats["fetched"] == 4
    assert pay_stats["created"] == 4
    assert pay_stats["cancelled"] >= 1
    assert pay_stats["allocated"] >= 1
    assert pay_stats["unallocated"] >= 1

    payments = Payment.objects.filter(organization=org, source=PaymentSource.KOLAYBI)
    assert payments.count() == 4

    allocated = payments.get(external_id="kb-pay-1")
    assert allocated.customer.external_id == "kb-cust-1"
    assert allocated.allocations.count() == 1
    assert allocated.allocations.first().invoice.external_id == "kb-inv-1"
    assert allocated.unallocated_amount == Decimal("0.00")

    unallocated = payments.get(external_id="kb-pay-2")
    assert unallocated.allocations.count() == 0
    assert unallocated.unallocated_amount == Decimal("100.00")

    cancelled = payments.get(external_id="kb-pay-3")
    assert cancelled.cancelled_at is not None
    assert cancelled.allocations.count() == 0

    # no duplicates on re-sync
    again = client.post(
        f"/api/integrations/connections/{result['connection_id']}/sync/",
        {"job_type": "manual"},
        format="json",
    )
    assert again.status_code == 201
    assert again.data["job"]["stats_json"]["payments"]["created"] == 0
    assert Payment.objects.filter(organization=org, source=PaymentSource.KOLAYBI).count() == 4
    assert PaymentAllocation.objects.filter(organization=org).count() >= 2
