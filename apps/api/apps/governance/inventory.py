"""NP-315 — processing inventory seed + CRUD helpers."""

from __future__ import annotations

from typing import Any

from apps.governance.models import ProcessingInventoryItem

DEFAULT_INVENTORY = [
    {
        "field_key": "customer.email",
        "data_type": "personal",
        "purpose": "İletişim ve tahsilat bildirimleri",
        "source": "manual / KolayBi",
        "retention_days": 365 * 5,
        "roles_allowed": ["OWNER", "ADMIN", "FINANCE_MANAGER", "COLLECTION_AGENT"],
        "transferred_systems": ["email_provider", "whatsapp"],
        "deletion_method": "anonymize_on_org_delete",
    },
    {
        "field_key": "customer.phone",
        "data_type": "personal",
        "purpose": "Telefon / WhatsApp tahsilat",
        "source": "manual / KolayBi",
        "retention_days": 365 * 5,
        "roles_allowed": ["OWNER", "ADMIN", "COLLECTION_AGENT"],
        "transferred_systems": ["whatsapp"],
        "deletion_method": "anonymize_on_org_delete",
    },
    {
        "field_key": "customer.tax_number",
        "data_type": "personal",
        "purpose": "Vergi kimliği / cari eşleştirme",
        "source": "manual / KolayBi",
        "retention_days": 365 * 10,
        "roles_allowed": ["OWNER", "ADMIN", "FINANCE_MANAGER"],
        "transferred_systems": ["kolaybi"],
        "deletion_method": "hard_delete_after_retention",
    },
    {
        "field_key": "invoice.total_amount",
        "data_type": "financial",
        "purpose": "Alacak takibi",
        "source": "manual / KolayBi",
        "retention_days": 365 * 10,
        "roles_allowed": ["OWNER", "ADMIN", "FINANCE_MANAGER", "COLLECTION_AGENT", "VIEWER"],
        "transferred_systems": ["kolaybi", "reports"],
        "deletion_method": "archive_then_purge",
    },
    {
        "field_key": "payment.amount",
        "data_type": "financial",
        "purpose": "Ödeme mutabakatı",
        "source": "manual / bank sync",
        "retention_days": 365 * 10,
        "roles_allowed": ["OWNER", "ADMIN", "FINANCE_MANAGER"],
        "transferred_systems": ["reports"],
        "deletion_method": "archive_then_purge",
    },
    {
        "field_key": "audit_log",
        "data_type": "technical",
        "purpose": "Güvenlik ve uyum denetimi",
        "source": "system",
        "retention_days": 365 * 10,
        "roles_allowed": ["OWNER", "ADMIN"],
        "transferred_systems": [],
        "deletion_method": "purge_by_retention_policy",
    },
]


def ensure_inventory(organization) -> list[ProcessingInventoryItem]:
    org_id = organization.pk if hasattr(organization, "pk") else organization
    created = []
    for row in DEFAULT_INVENTORY:
        obj, was = ProcessingInventoryItem.objects.get_or_create(
            organization_id=org_id,
            field_key=row["field_key"],
            defaults=row,
        )
        if was:
            created.append(obj)
    return list(ProcessingInventoryItem.objects.filter(organization_id=org_id))


def inventory_as_list(organization) -> list[dict[str, Any]]:
    items = ensure_inventory(organization)
    return [
        {
            "id": i.id,
            "field_key": i.field_key,
            "data_type": i.data_type,
            "purpose": i.purpose,
            "source": i.source,
            "retention_days": i.retention_days,
            "roles_allowed": i.roles_allowed,
            "transferred_systems": i.transferred_systems,
            "deletion_method": i.deletion_method,
        }
        for i in items
    ]
