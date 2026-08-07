"""NP-243 — customer communication preferences helpers."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from django.utils import timezone

from apps.customers.models import Customer, CustomerCommunicationPreference
from apps.messaging.services import MessagingError

CHANNEL_FLAGS = {
    "EMAIL": "email_ok",
    "WHATSAPP": "whatsapp_ok",
    "SMS": "sms_ok",
    "PHONE": "phone_ok",
    "CALL": "phone_ok",
}


def get_or_create_preference(customer: Customer) -> CustomerCommunicationPreference:
    pref, _ = CustomerCommunicationPreference.objects.get_or_create(
        organization_id=customer.organization_id,
        customer=customer,
        defaults={
            "email_ok": True,
            "whatsapp_ok": True,
            "sms_ok": True,
            "phone_ok": True,
            "no_contact_permission": False,
        },
    )
    return pref


def serialize_preference(pref: CustomerCommunicationPreference) -> dict[str, Any]:
    return {
        "id": pref.id,
        "customer_id": pref.customer_id,
        "organization": pref.organization_id,
        "email_ok": pref.email_ok,
        "whatsapp_ok": pref.whatsapp_ok,
        "sms_ok": pref.sms_ok,
        "phone_ok": pref.phone_ok,
        "no_contact_permission": pref.no_contact_permission,
        "contact_hours_start": (
            pref.contact_hours_start.isoformat() if pref.contact_hours_start else None
        ),
        "contact_hours_end": (
            pref.contact_hours_end.isoformat() if pref.contact_hours_end else None
        ),
        "notes": pref.notes,
        "updated_at": pref.updated_at.isoformat() if pref.updated_at else None,
    }


def _in_contact_window(pref: CustomerCommunicationPreference, when: datetime | None = None) -> bool:
    start = pref.contact_hours_start
    end = pref.contact_hours_end
    if start is None and end is None:
        return True
    now = when or timezone.localtime()
    current: time = now.timetz().replace(tzinfo=None) if hasattr(now, "timetz") else now.time()
    # Normalize to time without tz for comparison
    if hasattr(current, "tzinfo") and current.tzinfo is not None:
        current = current.replace(tzinfo=None)
    start = start or time(0, 0)
    end = end or time(23, 59, 59)
    if start <= end:
        return start <= current <= end
    # Overnight window (e.g. 22:00–06:00)
    return current >= start or current <= end


def assert_channel_allowed(
    customer: Customer,
    channel: str,
    *,
    when: datetime | None = None,
    respect_hours: bool = True,
) -> CustomerCommunicationPreference:
    """Raise MessagingError if channel outreach is not allowed (NP-243)."""
    pref = get_or_create_preference(customer)
    if pref.no_contact_permission:
        raise MessagingError("Müşterinin iletişim izni yok.", "no_contact_permission")
    flag = CHANNEL_FLAGS.get((channel or "").strip().upper())
    if flag and not getattr(pref, flag, True):
        raise MessagingError(
            f"{channel} kanalı bu müşteri için kapalı.",
            "channel_not_allowed",
        )
    if respect_hours and not _in_contact_window(pref, when=when):
        raise MessagingError(
            "Müşteri yalnızca belirlenen saatlerde aranabilir/mesajlanabilir.",
            "outside_contact_hours",
        )
    return pref
