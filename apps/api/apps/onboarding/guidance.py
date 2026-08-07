"""NP-293 — empty states, tooltips, checklist, help, announcements."""

from __future__ import annotations

from typing import Any

from apps.onboarding.models import FeatureAnnouncement
from apps.onboarding.progress import compute_score, ensure_state


DEFAULT_ANNOUNCEMENTS = [
    {
        "key": "whatsapp_templates",
        "title": "Onaylı WhatsApp şablonları",
        "body": "Tahsilat mesajlarınızı onaylı şablonlarla gönderin.",
        "help_url": "/dashboard/settings",
    },
    {
        "key": "forecast_scenarios",
        "title": "Nakit senaryoları",
        "body": "Baz / iyimser / kötümser senaryolarla nakit açığını önceden görün.",
        "help_url": "/forecast",
    },
]


def ensure_announcements() -> None:
    for row in DEFAULT_ANNOUNCEMENTS:
        FeatureAnnouncement.objects.get_or_create(
            key=row["key"],
            defaults={
                "title": row["title"],
                "body": row["body"],
                "help_url": row["help_url"],
                "is_active": True,
            },
        )


def guidance_payload(organization) -> dict[str, Any]:
    ensure_announcements()
    state = ensure_state(organization)
    score = compute_score(organization)
    org_id = organization.pk if hasattr(organization, "pk") else organization

    from apps.customers.models import Customer
    from apps.invoices.models import Invoice

    has_customers = Customer.objects.filter(organization_id=org_id, is_sample=False).exists()
    has_invoices = Invoice.objects.filter(organization_id=org_id, is_sample=False).exists()

    empty_states = []
    if not has_customers:
        empty_states.append(
            {
                "surface": "customers",
                "title": "Henüz müşteri yok",
                "action_label": "İlk müşteriyi ekle",
                "action_href": "/customers/new",
                "secondary_label": "Örnek veriyi aç",
                "secondary_action": "enable_sample_data",
            }
        )
    if not has_invoices:
        empty_states.append(
            {
                "surface": "invoices",
                "title": "Henüz fatura yok",
                "action_label": "Fatura içe aktar",
                "action_href": "/imports",
            }
        )

    tooltips = [
        {
            "key": "first_customer",
            "target": "customers.create",
            "text": "Gerçek cari ekleyerek tahsilat riskini ölçmeye başlayın.",
            "show": not score["items"][1]["done"] if len(score["items"]) > 1 else True,
        },
        {
            "key": "first_workflow",
            "target": "workflows.create",
            "text": "İlk tahsilat workflow’unu yayınlayarak otomasyonu başlatın.",
            "show": not any(
                i["key"] == "first_workflow_published" and i["done"] for i in score["items"]
            ),
        },
    ]

    sample_report = {
        "title": "Örnek tahsilat özeti",
        "metrics": [
            {"label": "Gecikmiş fatura", "value": "12"},
            {"label": "Beklenen tahsilat (30g)", "value": "₺185.000"},
            {"label": "Riskli müşteri", "value": "4"},
        ],
        "note": "Bu örnek rapordur; gerçek verilerinizi yansıtmaz.",
    }

    announcements = [
        {
            "key": a.key,
            "title": a.title,
            "body": a.body,
            "help_url": a.help_url,
        }
        for a in FeatureAnnouncement.objects.filter(is_active=True)[:10]
    ]

    return {
        "empty_states": empty_states,
        "tooltips": [t for t in tooltips if t["show"]],
        "checklist": score["items"],
        "score": score["score"],
        "sample_report": sample_report,
        "help_links": [
            {"label": "Yardım merkezi", "href": "https://docs.nakitpilot.local/help"},
            {"label": "Onboarding sihirbazı", "href": "/onboarding"},
            {"label": "Abonelik ve kullanım", "href": "/dashboard/settings#billing"},
        ],
        "announcements": announcements,
        "wizard_completed": state.wizard_completed,
        "sample_data_enabled": state.sample_data_enabled,
    }
