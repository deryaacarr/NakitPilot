"""NP-242 WhatsApp + NP-243 prefs + NP-244 frequency + NP-245 classification."""

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.collections.models import Dispute, DisputeCategory, DisputeStatus
from apps.customers.models import Customer
from apps.messaging.frequency import check_frequency
from apps.messaging.models import (
    OutboundWhatsApp,
    ResponseClassification,
    WhatsAppMessageStatus,
    WhatsAppTemplateStatus,
)
from apps.messaging.preferences import assert_channel_allowed, get_or_create_preference
from apps.messaging.services import MessagingError
from apps.messaging.whatsapp_service import (
    bulk_send_whatsapp,
    confirm_classification,
    create_and_send_whatsapp,
    ingest_inbound_whatsapp,
)
from apps.messaging.models import WhatsAppApprovedTemplate
from apps.organizations.models import Organization

User = get_user_model()


@pytest.fixture
def wa_ctx(db):
    org = Organization.objects.create(name="WA Co", slug="wa-co-np242")
    user = User.objects.create_user(email="wa@example.com", password="x")
    customer = Customer.objects.create(
        organization=org,
        name="Müşteri WA",
        code="WA-1",
        phone="05551234567",
    )
    customer2 = Customer.objects.create(
        organization=org,
        name="Müşteri WA 2",
        code="WA-2",
        phone="05559876543",
    )
    tpl = WhatsAppApprovedTemplate.objects.create(
        organization=org,
        name="odeme_hatirlatma",
        language_code="tr",
        body="Sayın {{customer_name}}, ödemenizi bekliyoruz.",
        status=WhatsAppTemplateStatus.APPROVED,
    )
    return org, user, customer, customer2, tpl


@pytest.mark.django_db
def test_single_send_and_status(wa_ctx):
    org, user, customer, _, tpl = wa_ctx
    msg = create_and_send_whatsapp(
        organization=org,
        customer_id=customer.id,
        template_id=tpl.id,
        actor=user,
        is_automatic=False,
    )
    assert msg.status == WhatsAppMessageStatus.SENT
    assert msg.to_phone.startswith("90")
    assert customer.name in msg.body
    assert msg.provider_message_id.startswith("mock-wa-")


@pytest.mark.django_db
def test_unapproved_template_blocked(wa_ctx):
    org, user, customer, _, tpl = wa_ctx
    tpl.status = WhatsAppTemplateStatus.PENDING
    tpl.save()
    with pytest.raises(MessagingError) as exc:
        create_and_send_whatsapp(
            organization=org,
            customer_id=customer.id,
            template_id=tpl.id,
            actor=user,
        )
    assert exc.value.code == "template_not_approved"


@pytest.mark.django_db
def test_opt_out_and_inbound_match(wa_ctx):
    org, user, customer, _, tpl = wa_ctx
    inbound = ingest_inbound_whatsapp(
        organization=org,
        from_phone="05551234567",
        body="STOP mesaj istemiyorum",
    )
    assert inbound.customer_id == customer.id
    assert inbound.opt_out_detected is True
    with pytest.raises(MessagingError) as exc:
        create_and_send_whatsapp(
            organization=org,
            customer_id=customer.id,
            template_id=tpl.id,
            actor=user,
        )
    assert exc.value.code == "opted_out"


@pytest.mark.django_db
def test_bulk_constraints_and_skips(wa_ctx):
    org, user, customer, customer2, tpl = wa_ctx
    pref = get_or_create_preference(customer2)
    pref.whatsapp_ok = False
    pref.save()
    result = bulk_send_whatsapp(
        organization=org,
        customer_ids=[customer.id, customer2.id],
        template_id=tpl.id,
        actor=user,
        is_automatic=False,
    )
    assert result["sent_count"] == 1
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["customer_id"] == customer2.id


@pytest.mark.django_db
def test_frequency_24h_and_dispute(wa_ctx):
    org, user, customer, _, tpl = wa_ctx
    create_and_send_whatsapp(
        organization=org,
        customer_id=customer.id,
        template_id=tpl.id,
        actor=user,
        is_automatic=True,
    )
    result = check_frequency(customer, is_automatic=True)
    assert result.allowed is False
    assert result.code == "auto_24h_limit"

    # Resolve frequency by marking old; open dispute blocks automation
    OutboundWhatsApp.objects.filter(customer=customer).update(
        sent_at=timezone.now() - timedelta(days=2)
    )
    Dispute.objects.create(
        organization=org,
        customer=customer,
        category=DisputeCategory.INVOICE_ERROR,
        status=DisputeStatus.UNDER_REVIEW,
        amount=Decimal("100.00"),
        description="Yanlış fatura",
    )
    result = check_frequency(customer, is_automatic=True)
    assert result.allowed is False
    assert result.code == "open_dispute"


@pytest.mark.django_db
def test_preferences_no_contact_and_hours(wa_ctx):
    org, _, customer, _, _ = wa_ctx
    pref = get_or_create_preference(customer)
    pref.no_contact_permission = True
    pref.save()
    with pytest.raises(MessagingError) as exc:
        assert_channel_allowed(customer, "EMAIL")
    assert exc.value.code == "no_contact_permission"

    pref.no_contact_permission = False
    pref.email_ok = False
    pref.contact_hours_start = time(9, 0)
    pref.contact_hours_end = time(18, 0)
    pref.save()
    with pytest.raises(MessagingError) as exc:
        assert_channel_allowed(customer, "EMAIL")
    assert exc.value.code == "channel_not_allowed"


@pytest.mark.django_db
def test_classification_requires_user_confirm(wa_ctx):
    org, user, customer, _, _ = wa_ctx
    inbound = ingest_inbound_whatsapp(
        organization=org,
        from_phone=customer.phone,
        body="Yarın ödeyeceğim söz veriyorum",
    )
    assert inbound.suggested_classification == ResponseClassification.PROMISE
    assert inbound.classification_confirmed is False
    with pytest.raises(MessagingError):
        confirm_classification(inbound, classification="INVALID", actor=user)
    confirmed = confirm_classification(
        inbound,
        classification=ResponseClassification.PROMISE,
        actor=user,
    )
    assert confirmed.classification_confirmed is True
    assert confirmed.classification == ResponseClassification.PROMISE
