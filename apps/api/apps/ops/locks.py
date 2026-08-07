"""NP-325 — distributed locks (Redis/cache-backed)."""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Iterator

from django.core.cache import cache


class LockError(Exception):
    def __init__(self, message: str, code: str = "lock_held"):
        super().__init__(message)
        self.message = message
        self.code = code


def lock_key(namespace: str, *parts) -> str:
    joined = ":".join(str(p) for p in parts)
    return f"np:lock:{namespace}:{joined}"


@contextmanager
def distributed_lock(
    namespace: str,
    *parts,
    timeout: int = 300,
    blocking: bool = False,
    wait_seconds: float = 0,
) -> Iterator[str]:
    """
    Acquire an exclusive lock. Raises LockError if held and not blocking.
    token is returned so callers can verify ownership if needed.
    """
    key = lock_key(namespace, *parts)
    token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        acquired = cache.add(key, token, timeout=timeout)
        if acquired:
            try:
                yield token
            finally:
                # Only delete if we still own it
                if cache.get(key) == token:
                    cache.delete(key)
            return
        if not blocking or time.monotonic() >= deadline:
            raise LockError(
                f"Kilit alınamadı: {namespace} ({':'.join(map(str, parts))})",
                code="lock_held",
            )
        time.sleep(0.05)


def with_org_lock(namespace: str, organization_id: int, *, timeout: int = 300):
    return distributed_lock(namespace, organization_id, timeout=timeout)
