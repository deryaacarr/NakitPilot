"""NP-131/132: template variable context and rendering."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_overdue_days
from apps.payments.models import ZERO

TEMPLATE_VARIABLES = (
    "customer_name",
    "invoice_number",
    "invoice_amount",
    "remaining_amount",
    "due_date",
    "overdue_days",
    "company_name",
    "payment_link",
)

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _fmt_money(amount: Decimal) -> str:
    q = Decimal(str(amount)).quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    q = abs(q)
    whole, frac = f"{q:.2f}".split(".")
    groups: list[str] = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    whole_fmt = ".".join(reversed(groups))
    if frac == "00":
        return f"{sign}{whole_fmt} TL"
    return f"{sign}{whole_fmt},{frac} TL"


def _fmt_date(value: date | None) -> str:
    if value is None:
        return ""
    # 18 Temmuz 2026
    months = (
        "",
        "Ocak",
        "Şubat",
        "Mart",
        "Nisan",
        "Mayıs",
        "Haziran",
        "Temmuz",
        "Ağustos",
        "Eylül",
        "Ekim",
        "Kasım",
        "Aralık",
    )
    return f"{value.day} {months[value.month]} {value.year}"


def build_template_context(
    *,
    organization,
    customer: Customer,
    invoice: Invoice | None = None,
    as_of: date | None = None,
    payment_link: str = "",
) -> dict[str, str]:
    """Resolve NP-131 variables for a customer (+ optional invoice)."""
    today = as_of or timezone.localdate()
    ctx: dict[str, str] = {
        "customer_name": customer.name or "",
        "company_name": getattr(organization, "name", "") or "",
        "payment_link": payment_link or "",
        "invoice_number": "",
        "invoice_amount": "",
        "remaining_amount": "",
        "due_date": "",
        "overdue_days": "0",
    }

    inv = invoice
    if inv is None:
        inv = (
            Invoice.objects.filter(customer=customer)
            .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED, InvoiceStatus.PAID])
            .order_by("due_date", "id")
            .first()
        )

    if inv is not None:
        remaining = inv.remaining_amount()
        ctx.update(
            {
                "invoice_number": inv.number or "",
                "invoice_amount": _fmt_money(inv.total_amount or ZERO),
                "remaining_amount": _fmt_money(remaining),
                "due_date": _fmt_date(inv.due_date),
                "overdue_days": str(invoice_overdue_days(inv, as_of=today)),
            }
        )

    return ctx


def render_template_text(text: str, context: dict[str, str]) -> str:
    """Replace ``{{var}}`` placeholders; unknown vars left empty."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return context.get(key, "")

    return _VAR_RE.sub(repl, text or "")


def render_message_template(
    template,
    *,
    customer: Customer,
    invoice: Invoice | None = None,
    as_of: date | None = None,
    payment_link: str = "",
) -> dict[str, Any]:
    ctx = build_template_context(
        organization=template.organization,
        customer=customer,
        invoice=invoice,
        as_of=as_of,
        payment_link=payment_link,
    )
    return {
        "template_id": template.id,
        "channel": template.channel,
        "subject": render_template_text(template.subject, ctx),
        "body": render_template_text(template.body, ctx),
        "variables": ctx,
    }
