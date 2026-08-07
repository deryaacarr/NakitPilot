"""Webhook retry schedule (NP-205)."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone

# Delays after consecutive failed attempts (attempt 1→2, 2→3, …).
RETRY_DELAYS: tuple[timedelta, ...] = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
    timedelta(hours=24),
)

# Initial send + one attempt after each delay.
DEFAULT_MAX_ATTEMPTS = len(RETRY_DELAYS) + 1  # 7


def next_retry_at(failed_attempt_number: int, *, from_time: datetime | None = None) -> datetime | None:
    """
    Return when to retry after `failed_attempt_number` failed (1-based).

    After attempt 1 fails → +1 minute; after attempt 6 fails → +24 hours;
    after attempt 7+ → None (exhausted).
    """
    idx = failed_attempt_number - 1
    if idx < 0 or idx >= len(RETRY_DELAYS):
        return None
    base = from_time or timezone.now()
    return base + RETRY_DELAYS[idx]
