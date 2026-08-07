"""NP-205 — Webhook retry system."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization, Role
from apps.webhooks.delivery import enqueue_event, manual_resend, process_delivery
from apps.webhooks.models import WebhookAttempt, WebhookDelivery, WebhookDeliveryStatus
from apps.webhooks.retry import RETRY_DELAYS, next_retry_at
from apps.webhooks.services import create_endpoint
from apps.webhooks.signing import HEADER_DELIVERY_ID

User = get_user_model()
PASSWORD = "SecretPass123!"


@pytest.fixture
def org_setup(db):
    org = Organization.objects.create(name="NP205 Org", slug="np205-org")
    owner = User.objects.create_user(email="np205-owner@example.com", password=PASSWORD)
    Membership.objects.create(organization=org, user=owner, role=Role.OWNER, is_active=True)
    endpoint, secret, _subs = create_endpoint(
        organization=org,
        name="Retry Hook",
        url="https://example.com/hooks",
        event_types=["payment.created"],
        created_by=owner,
    )
    return org, owner, endpoint, secret


def _auth(client, user, org):
    login = client.post(
        "/api/auth/login",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return client


def test_retry_schedule_matches_spec():
    assert len(RETRY_DELAYS) == 6
    assert RETRY_DELAYS[0] == timedelta(minutes=1)
    assert RETRY_DELAYS[1] == timedelta(minutes=5)
    assert RETRY_DELAYS[2] == timedelta(minutes=15)
    assert RETRY_DELAYS[3] == timedelta(hours=1)
    assert RETRY_DELAYS[4] == timedelta(hours=6)
    assert RETRY_DELAYS[5] == timedelta(hours=24)
    base = timezone.now()
    assert next_retry_at(1, from_time=base) == base + timedelta(minutes=1)
    assert next_retry_at(6, from_time=base) == base + timedelta(hours=24)
    assert next_retry_at(7, from_time=base) is None


@pytest.mark.django_db
def test_failed_delivery_retries_and_logs_attempts(org_setup):
    org, _owner, endpoint, _secret = org_setup
    deliveries = enqueue_event(
        organization=org,
        event_type="payment.created",
        event_id="pay-1",
        payload={"id": 1},
        process_async=False,
    )
    assert len(deliveries) == 1
    delivery = deliveries[0]
    public_id = str(delivery.public_id)

    with patch("apps.webhooks.delivery.urllib.request.urlopen") as urlopen:
        urlopen.side_effect = TimeoutError("timed out")
        process_delivery(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == WebhookDeliveryStatus.FAILED
    assert delivery.attempt_count == 1
    assert delivery.next_attempt_at is not None
    assert WebhookAttempt.objects.filter(delivery=delivery).count() == 1

    # Same delivery id on every attempt (unique across retries).
    with patch("apps.webhooks.delivery.urllib.request.urlopen") as urlopen:
        urlopen.side_effect = TimeoutError("timed out")
        # Force ignore next_attempt_at for test speed
        delivery.next_attempt_at = timezone.now() - timedelta(seconds=1)
        delivery.save(update_fields=["next_attempt_at"])
        process_delivery(delivery.id)

    delivery.refresh_from_db()
    assert delivery.attempt_count == 2
    assert WebhookAttempt.objects.filter(delivery=delivery).count() == 2
    assert str(delivery.public_id) == public_id

    # Capture signed header uses same public_id
    with patch("apps.webhooks.delivery.urllib.request.urlopen") as urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        urlopen.return_value = mock_resp
        delivery.next_attempt_at = timezone.now() - timedelta(seconds=1)
        delivery.save(update_fields=["next_attempt_at"])
        process_delivery(delivery.id)
        req = urlopen.call_args[0][0]
        header_items = {k.lower(): v for k, v in req.header_items()}
        assert header_items.get(HEADER_DELIVERY_ID.lower()) == public_id

    delivery.refresh_from_db()
    assert delivery.status == WebhookDeliveryStatus.SUCCEEDED


@pytest.mark.django_db
def test_enqueue_dedupes_same_event_id(org_setup):
    org, *_ = org_setup
    first = enqueue_event(
        organization=org,
        event_type="payment.created",
        event_id="dup-1",
        payload={},
        process_async=False,
    )
    second = enqueue_event(
        organization=org,
        event_type="payment.created",
        event_id="dup-1",
        payload={},
        process_async=False,
    )
    assert len(first) == 1
    assert second == []
    assert WebhookDelivery.objects.filter(event_id="dup-1").count() == 1


@pytest.mark.django_db
def test_list_failed_and_manual_resend(org_setup):
    org, owner, _endpoint, _secret = org_setup
    deliveries = enqueue_event(
        organization=org,
        event_type="payment.created",
        event_id="pay-resend",
        payload={"x": 1},
        process_async=False,
    )
    delivery = deliveries[0]
    with patch("apps.webhooks.delivery.urllib.request.urlopen") as urlopen:
        urlopen.side_effect = TimeoutError("down")
        process_delivery(delivery.id)

    client = _auth(APIClient(), owner, org)
    listed = client.get("/api/webhooks/deliveries/?status=failed")
    assert listed.status_code == 200
    rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
    assert any(r["id"] == delivery.id for r in rows)
    assert rows[0]["public_id"]
    assert rows[0]["attempts"]

    with patch("apps.webhooks.delivery.urllib.request.urlopen") as urlopen, patch(
        "apps.webhooks.tasks.process_webhook_delivery.delay"
    ) as delay:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        urlopen.return_value = mock_resp

        resend = client.post(f"/api/webhooks/deliveries/{delivery.id}/resend/")
        assert resend.status_code == status.HTTP_200_OK
        delay.assert_called()

        # Process manually (task was mocked)
        process_delivery(delivery.id, force=True)

    delivery.refresh_from_db()
    assert delivery.status == WebhookDeliveryStatus.SUCCEEDED
    assert WebhookAttempt.objects.filter(delivery=delivery).count() >= 2
