from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.collections.models import CollectionActivity
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.messaging.models import MessageChannel, MessageTemplate
from apps.messaging.rendering import render_template_text
from apps.messaging.services import ensure_default_templates, preview_template
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
def org_setup(db):
    org = Organization.objects.create(name="Demo Ticaret A.Ş.", slug="msg-co")
    user = User.objects.create_user(email="msg@test.local", password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=Role.OWNER, is_active=True)
    customer = Customer.objects.create(
        organization=org,
        name="ABC Elektrik",
        code="ABC",
    )
    invoice = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="F-100",
        invoice_date=date(2026, 6, 18),
        due_date=date(2026, 7, 18),
        total_amount=Decimal("64000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    return org, user, customer, invoice


def test_render_variables():
    text = "Merhaba {{ customer_name }}, tutar {{invoice_amount}}."
    out = render_template_text(
        text,
        {"customer_name": "ABC Elektrik", "invoice_amount": "64.000 TL"},
    )
    assert out == "Merhaba ABC Elektrik, tutar 64.000 TL."


@pytest.mark.django_db
def test_preview_fills_real_data(org_setup):
    org, _user, customer, invoice = org_setup
    template = MessageTemplate.objects.create(
        organization=org,
        name="Hatırlatma",
        channel=MessageChannel.EMAIL,
        subject="{{invoice_number}}",
        body=(
            "Merhaba {{customer_name}} yetkilisi,\n\n"
            "{{due_date}} vadeli {{invoice_amount}} tutarındaki faturanızın\n"
            "ödemesi henüz hesabımıza ulaşmamıştır."
        ),
    )
    result = preview_template(template, customer_id=customer.id, invoice_id=invoice.id)
    assert "ABC Elektrik" in result["body"]
    assert "64.000 TL" in result["body"]
    assert "18 Temmuz 2026" in result["body"]
    assert result["subject"] == "F-100"
    assert result["variables"]["company_name"] == "Demo Ticaret A.Ş."


@pytest.mark.django_db
def test_copy_creates_optional_activity_not_auto_sent(api_client, org_setup):
    org, user, customer, invoice = org_setup
    client = _auth(api_client, user, org)
    template = MessageTemplate.objects.create(
        organization=org,
        name="WA",
        channel=MessageChannel.WHATSAPP,
        body="Merhaba {{customer_name}}",
    )
    response = client.post(
        f"/api/message-templates/{template.id}/copy/",
        {
            "customer_id": customer.id,
            "invoice_id": invoice.id,
            "create_activity": True,
        },
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["copied"] is True
    assert body["auto_sent"] is False
    assert body["message"] == "Mesaj kopyalandı"
    assert body["activity_id"] is not None
    activity = CollectionActivity.objects.get(pk=body["activity_id"])
    assert activity.metadata.get("auto_sent") is False
    assert "gönderildi" not in activity.summary.lower()


@pytest.mark.django_db
def test_list_seeds_defaults(api_client, org_setup):
    org, user, *_rest = org_setup
    client = _auth(api_client, user, org)
    assert MessageTemplate.objects.filter(organization=org).count() == 0
    response = client.get("/api/message-templates/")
    assert response.status_code == 200
    data = response.json()
    results = data["results"] if isinstance(data, dict) and "results" in data else data
    assert len(results) >= 3
    assert ensure_default_templates(org) == 0
