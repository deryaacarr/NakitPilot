"""NP-240 outbound email tests."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.messaging.email_service import (
    approve_outbound_email,
    create_email_draft,
    record_bounce,
    record_click,
    record_open,
)
from apps.messaging.models import (
    MessageChannel,
    MessageTemplate,
    OutboundEmailStatus,
)
from apps.messaging.services import MessagingError
from apps.organizations.models import Organization

User = get_user_model()


@pytest.fixture
def email_ctx(db):
    org = Organization.objects.create(name="Mail Co", slug="mail-co-np240")
    user = User.objects.create_user(email="mailer@example.com", password="x")
    customer = Customer.objects.create(
        organization=org,
        name="Alıcı AŞ",
        code="EM-1",
        email="musteri@example.com",
        last_contact_at=timezone.now(),
    )
    today = date.today()
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        number="INV-MAIL-1",
        invoice_date=today - timedelta(days=10),
        due_date=today - timedelta(days=2),
        total_amount=Decimal("5000.00"),
        status=InvoiceStatus.OVERDUE,
    )
    tpl = MessageTemplate.objects.create(
        organization=org,
        name="Hatırlatma",
        channel=MessageChannel.EMAIL,
        subject="Fatura {{invoice_number}}",
        body="Sayın {{customer_name}}, kalan {{remaining_amount}}.",
        is_default=True,
    )
    return org, user, customer, inv, tpl


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
)
def test_preview_approve_send_and_tracking(email_ctx):
    org, user, customer, inv, tpl = email_ctx
    draft = create_email_draft(
        organization=org,
        customer_id=customer.id,
        template_id=tpl.id,
        invoice_id=inv.id,
        actor=user,
    )
    assert draft.status == OutboundEmailStatus.PENDING_APPROVAL
    assert "INV-MAIL-1" in draft.subject
    assert customer.name in draft.body_text

    with pytest.raises(MessagingError):
        approve_outbound_email(draft, actor=user, confirmed=False)

    approved = approve_outbound_email(
        draft, actor=user, confirmed=True, queue_send=True
    )
    approved.refresh_from_db()
    assert approved.status == OutboundEmailStatus.SENT
    assert approved.sent_at is not None
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["musteri@example.com"]

    record_open(approved.tracking_token)
    approved.refresh_from_db()
    assert approved.open_count == 1
    assert approved.status == OutboundEmailStatus.OPENED

    record_click(approved.tracking_token, "https://example.com/pay")
    approved.refresh_from_db()
    assert approved.click_count == 1
    assert approved.status == OutboundEmailStatus.CLICKED

    record_bounce(token=approved.tracking_token, bounce_type="hard", detail="550")
    approved.refresh_from_db()
    assert approved.status == OutboundEmailStatus.BOUNCED
    assert approved.bounce_type == "hard"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_template_required_fields_from_db(email_ctx):
    org, user, customer, inv, tpl = email_ctx
    draft = create_email_draft(
        organization=org,
        customer_id=customer.id,
        template_id=tpl.id,
        invoice_id=inv.id,
        actor=user,
    )
    assert "5.000 TL" in draft.body_text or "5000" in draft.body_text.replace(".", "")
