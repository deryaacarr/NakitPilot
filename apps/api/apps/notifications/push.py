"""NP-344 — web push helpers (VAPID optional)."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

from apps.notifications.models import PushSubscription

logger = logging.getLogger(__name__)


def vapid_public_key() -> str:
    return getattr(settings, "VAPID_PUBLIC_KEY", "") or ""


def enqueue_web_push(
    *,
    organization,
    user=None,
    title: str,
    body: str = "",
    href: str = "",
    tag: str = "",
    data: dict[str, Any] | None = None,
) -> int:
    """
    Attempt to deliver web push to active subscriptions.

    Without `pywebpush` / VAPID keys this is a no-op that still records intent
    in logs so the subscription pipeline can be tested end-to-end.
    """
    qs = PushSubscription.objects.filter(organization=organization, is_active=True)
    if user is not None:
        qs = qs.filter(user=user)
    payload = {
        "title": title,
        "body": body,
        "href": href,
        "tag": tag or "nakitpilot",
        "data": data or {},
    }
    count = 0
    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "") or ""
    public_key = vapid_public_key()
    mailto = getattr(settings, "VAPID_MAILTO", "mailto:ops@nakitpilot.local")

    for sub in qs:
        count += 1
        if not private_key or not public_key:
            logger.info(
                "web_push_queued_no_vapid user=%s endpoint=%s payload=%s",
                sub.user_id,
                sub.endpoint[:48],
                json.dumps(payload, ensure_ascii=False)[:200],
            )
            continue
        try:
            from pywebpush import webpush  # type: ignore

            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=private_key,
                vapid_claims={"sub": mailto},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("web_push_failed sub=%s err=%s", sub.id, exc)
            if "410" in str(exc) or "404" in str(exc):
                sub.is_active = False
                sub.save(update_fields=["is_active", "updated_at"])
    return count
