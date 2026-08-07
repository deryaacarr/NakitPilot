"""Field ownership for integration customer sync (NP-193)."""

from __future__ import annotations

# Updated from KolayBi on sync (unless locally overridden).
KOLAYBI_MANAGED_CUSTOMER_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "tax_number",
        "email",
        "phone",
    }
)

# Never written by integration sync — NakitPilot owns these.
NAKITPILOT_MANAGED_CUSTOMER_FIELDS: frozenset[str] = frozenset(
    {
        "risk_status",
        "risk_score",
        "assigned_user_id",
        "notes",
        "collection_strategy",
    }
)

# Synced operational flags / identity (always applied from source when present).
SYNC_ALWAYS_CUSTOMER_FIELDS: frozenset[str] = frozenset(
    {
        "is_active",
        "code",
    }
)
