"""NP-233 — tone-based message assistant (DB-filled placeholders only)."""

from __future__ import annotations

from typing import Any

from django.db import models

from apps.customers.models import Customer
from apps.invoices.models import Invoice
from apps.messaging.rendering import build_template_context, render_template_text


class MessageTone(models.TextChoices):
    NAZIK = "NAZIK", "Nazik"
    PROFESYONEL = "PROFESYONEL", "Profesyonel"
    NET = "NET", "Net"
    SON_HATIRLATMA = "SON_HATIRLATMA", "Son hatırlatma"
    YONETICI = "YONETICI", "Yönetici dili"


# Fixed copy only — amounts/dates come exclusively from {{variables}} filled by DB.
TONE_TEMPLATES: dict[str, dict[str, str]] = {
    MessageTone.NAZIK: {
        "subject": "{{invoice_number}} numaralı faturanız için nazik hatırlatma",
        "body": (
            "Merhaba {{customer_name}},\n\n"
            "{{due_date}} vadeli {{invoice_number}} numaralı faturanızın "
            "kalan tutarı {{remaining_amount}} olup gecikme {{overdue_days}} gündür.\n\n"
            "Uygun olduğunuzda ödemeyi planlamanızı rica ederiz.\n\n"
            "Saygılarımızla,\n{{company_name}}"
        ),
    },
    MessageTone.PROFESYONEL: {
        "subject": "{{invoice_number}} — ödeme hatırlatması",
        "body": (
            "Sayın {{customer_name}},\n\n"
            "Fatura no: {{invoice_number}}\n"
            "Fatura tutarı: {{invoice_amount}}\n"
            "Kalan tutar: {{remaining_amount}}\n"
            "Vade: {{due_date}}\n"
            "Gecikme: {{overdue_days}} gün\n\n"
            "Ödemenin en kısa sürede tamamlanmasını rica ederiz.\n\n"
            "Saygılarımızla,\n{{company_name}}"
        ),
    },
    MessageTone.NET: {
        "subject": "{{invoice_number}} ödeme bekleniyor",
        "body": (
            "{{customer_name}},\n\n"
            "{{invoice_number}} numaralı fatura: {{remaining_amount}} "
            "(vade {{due_date}}, {{overdue_days}} gün gecikme).\n"
            "Ödeme planınızı bugün teyit edin.\n\n"
            "{{company_name}}"
        ),
    },
    MessageTone.SON_HATIRLATMA: {
        "subject": "Son hatırlatma — {{invoice_number}}",
        "body": (
            "Sayın {{customer_name}},\n\n"
            "Bu, {{invoice_number}} numaralı faturanız "
            "({{remaining_amount}}, vade {{due_date}}, {{overdue_days}} gün gecikme) "
            "için son yazılı hatırlatmadır.\n\n"
            "Ödeme yapılmaması halinde tahsilat süreci ilerletilecektir.\n\n"
            "{{company_name}}"
        ),
    },
    MessageTone.YONETICI: {
        "subject": "Yönetim takibi — {{invoice_number}}",
        "body": (
            "Sayın {{customer_name}},\n\n"
            "Yönetimimiz, {{invoice_number}} numaralı faturanızdaki "
            "{{remaining_amount}} açık bakiyeyi (vade {{due_date}}, "
            "{{overdue_days}} gün gecikme) öncelikli dosya olarak izlemektedir.\n\n"
            "Ödeme taahhüdünüzü yazılı olarak iletmenizi bekliyoruz.\n\n"
            "Saygılarımızla,\n{{company_name}} Yönetimi"
        ),
    },
}


def generate_message(
    *,
    organization,
    customer: Customer,
    tone: str,
    invoice: Invoice | None = None,
    payment_link: str = "",
) -> dict[str, Any]:
    """
    Produce subject/body for a tone. Numeric and date fields are filled only
    via ``build_template_context`` from the database.
    """
    if tone not in MessageTone.values:
        raise ValueError(f"Geçersiz ton: {tone}")
    templates = TONE_TEMPLATES[tone]
    ctx = build_template_context(
        organization=organization,
        customer=customer,
        invoice=invoice,
        payment_link=payment_link,
    )
    return {
        "tone": tone,
        "tone_label": dict(MessageTone.choices).get(tone, tone),
        "subject": render_template_text(templates["subject"], ctx),
        "body": render_template_text(templates["body"], ctx),
        "variables": {
            "invoice_number": ctx["invoice_number"],
            "invoice_amount": ctx["invoice_amount"],
            "remaining_amount": ctx["remaining_amount"],
            "due_date": ctx["due_date"],
            "overdue_days": ctx["overdue_days"],
            "customer_name": ctx["customer_name"],
            "company_name": ctx["company_name"],
        },
        "source_fields": {
            "amount": ctx["remaining_amount"] or ctx["invoice_amount"],
            "invoice_number": ctx["invoice_number"],
            "due_date": ctx["due_date"],
            "overdue_days": ctx["overdue_days"],
        },
    }


def list_tones() -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in MessageTone.choices]
