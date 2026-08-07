"""NP-203 — Webhook subscription models."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.organizations.models import Membership, Organization, Role
from apps.webhooks.events import ALL_EVENT_TYPES, WebhookEventType
from apps.webhooks.models import (
    WebhookAttempt,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookSubscription,
)
from apps.webhooks.secrets import decrypt_webhook_secret
from apps.webhooks.services import WebhookServiceError, create_endpoint, list_event_types

User = get_user_model()


@pytest.fixture
def org_owner(db):
    org = Organization.objects.create(name="NP203 Org", slug="np203-org")
    owner = User.objects.create_user(email="np203-owner@example.com", password="SecretPass123!")
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    return org, owner


@pytest.mark.django_db
def test_event_registry_covers_required_types():
    required = {
        "invoice.created",
        "invoice.overdue",
        "invoice.paid",
        "payment.created",
        "payment.cancelled",
        "payment_promise.created",
        "payment_promise.broken",
        "customer.risk_changed",
        "collection_task.created",
        "forecast.updated",
    }
    assert required <= set(ALL_EVENT_TYPES)
    assert len(list_event_types()) == len(WebhookEventType)


@pytest.mark.django_db
def test_create_endpoint_with_subscriptions_and_secret_once(org_owner):
    org, owner = org_owner
    endpoint, raw_secret, subs = create_endpoint(
        organization=org,
        name="ERP Hook",
        url="https://example.com/hooks/nakitpilot",
        event_types=["invoice.created", "payment.created", "invoice.created"],
        created_by=owner,
    )
    assert raw_secret.startswith("whsec_")
    assert endpoint.secret_hint
    assert decrypt_webhook_secret(endpoint.secret_encrypted) == raw_secret
    assert endpoint.is_active is True
    assert len(subs) == 2
    assert WebhookSubscription.objects.filter(endpoint=endpoint).count() == 2


@pytest.mark.django_db
def test_invalid_event_type_rejected(org_owner):
    org, owner = org_owner
    with pytest.raises(WebhookServiceError):
        create_endpoint(
            organization=org,
            name="Bad",
            url="https://example.com/hook",
            event_types=["not.a.real.event"],
            created_by=owner,
        )


@pytest.mark.django_db
def test_subscription_unique_per_endpoint_event(org_owner):
    org, owner = org_owner
    endpoint, _secret, _subs = create_endpoint(
        organization=org,
        name="Unique",
        url="https://example.com/hook",
        event_types=["invoice.paid"],
        created_by=owner,
    )
    with pytest.raises(IntegrityError):
        WebhookSubscription.objects.create(
            organization=org,
            endpoint=endpoint,
            event_type=WebhookEventType.INVOICE_PAID,
        )


@pytest.mark.django_db
def test_delivery_and_attempt_models(org_owner):
    org, owner = org_owner
    endpoint, _secret, subs = create_endpoint(
        organization=org,
        name="Delivery",
        url="https://example.com/hook",
        event_types=["customer.risk_changed"],
        created_by=owner,
    )
    subscription = subs[0]
    delivery = WebhookDelivery.objects.create(
        organization=org,
        endpoint=endpoint,
        subscription=subscription,
        event_type=WebhookEventType.CUSTOMER_RISK_CHANGED,
        event_id="risk-42-2026",
        payload={"customer_id": 42, "score": 80},
        status=WebhookDeliveryStatus.PENDING,
    )
    attempt = WebhookAttempt.objects.create(
        organization=org,
        delivery=delivery,
        attempt_number=1,
        request_url=endpoint.url,
        response_status=500,
        response_body="upstream error",
        error_message="HTTP 500",
        duration_ms=120,
        success=False,
    )
    assert delivery.attempts.count() == 1
    assert attempt.delivery_id == delivery.id

    with pytest.raises(IntegrityError):
        WebhookDelivery.objects.create(
            organization=org,
            endpoint=endpoint,
            event_type=WebhookEventType.CUSTOMER_RISK_CHANGED,
            event_id="risk-42-2026",
            payload={},
        )
