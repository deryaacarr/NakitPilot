"""NP-230 customer summary — DB-sourced facts only (no invented numbers)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.collections.models import (
    CallOutcome,
    CollectionTask,
    CollectionTaskStatus,
    PaymentPromise,
    PaymentPromiseStatus,
)
from apps.customers.metrics import OPEN_STATUSES, customer_financial_metrics
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.overdue import invoice_actual_delay_days, invoice_overdue_days
from apps.payments.models import ZERO

_MONTHS_TR = (
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

_COUNT_TR = {0: "hiçbiri", 1: "biri", 2: "ikisi", 3: "üçü"}


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
    return f"{value.day} {_MONTHS_TR[value.month]}"


def _source(
    *,
    type: str,
    id: int | None,
    label: str,
    field: str,
    value: Any,
    url_hint: str | None = None,
) -> dict[str, Any]:
    return {
        "type": type,
        "id": id,
        "label": label,
        "field": field,
        "value": value if not isinstance(value, Decimal) else str(value),
        "url_hint": url_hint,
    }


def build_customer_summary(
    customer: Customer,
    *,
    organization=None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    Build a finance-user facing summary from org-scoped DB records only.

    Acceptance:
    - Numbers come from the database (never invented)
    - Sources are returned for UI disclosure
    - Organization scoping enforced
    """
    org = organization or customer.organization
    if customer.organization_id != org.id:
        raise PermissionError("Customer is outside the request organization.")

    from apps.ai_usage.prompt_security import (
        CUSTOMER_SUMMARY_SCHEMA,
        secure_ai_produce,
    )

    def _build() -> dict[str, Any]:
        return _build_customer_summary_body(customer, organization=org, as_of=as_of)

    return secure_ai_produce(
        organization=org,
        scoped_objects=[customer],
        output_schema=CUSTOMER_SUMMARY_SCHEMA,
        producer=_build,
    )


def _build_customer_summary_body(
    customer: Customer,
    *,
    organization,
    as_of: date | None = None,
) -> dict[str, Any]:
    org = organization
    today = as_of or timezone.localdate()
    metrics = customer_financial_metrics(customer)
    open_balance = Decimal(str(metrics["open_balance"] or ZERO))
    oldest_days = metrics.get("oldest_overdue_days")

    paragraphs: list[str] = []
    sources: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []

    name = customer.name or f"Müşteri #{customer.id}"
    balance_text = _fmt_money(open_balance)
    paragraphs.append(f"{name}'in toplam {balance_text} açık bakiyesi bulunuyor.")
    facts.append(
        {
            "key": "open_balance",
            "value": str(open_balance),
            "display": balance_text,
        }
    )
    sources.append(
        _source(
            type="customer",
            id=customer.id,
            label=name,
            field="open_balance",
            value=str(open_balance),
            url_hint=f"/customers/{customer.id}",
        )
    )

    open_invoices = list(
        Invoice.objects.filter(customer=customer, organization=org)
        .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED])
        .order_by("due_date", "id")
    )
    oldest_inv = None
    oldest_overdue = -1
    for inv in open_invoices:
        if inv.status not in OPEN_STATUSES:
            continue
        if inv.remaining_amount() <= ZERO:
            continue
        days = invoice_overdue_days(inv, as_of=today)
        if days > oldest_overdue:
            oldest_overdue = days
            oldest_inv = inv

    if oldest_inv is not None and oldest_overdue > 0:
        paragraphs.append(f"En eski fatura {oldest_overdue} gün gecikmiş durumda.")
        facts.append(
            {
                "key": "oldest_overdue_days",
                "value": oldest_overdue,
                "display": f"{oldest_overdue} gün",
            }
        )
        sources.append(
            _source(
                type="invoice",
                id=oldest_inv.id,
                label=f"Fatura {oldest_inv.number}",
                field="overdue_days",
                value=oldest_overdue,
                url_hint=f"/invoices/{oldest_inv.id}",
            )
        )
    elif oldest_days and int(oldest_days) > 0:
        paragraphs.append(f"En eski fatura {int(oldest_days)} gün gecikmiş durumda.")
        facts.append(
            {
                "key": "oldest_overdue_days",
                "value": int(oldest_days),
                "display": f"{int(oldest_days)} gün",
            }
        )

    paid = list(
        Invoice.objects.filter(
            customer=customer,
            organization=org,
            status=InvoiceStatus.PAID,
        ).order_by("-payment_completion_date", "-id")[:3]
    )
    late_count = 0
    late_sources: list[Invoice] = []
    for inv in paid:
        delay = invoice_actual_delay_days(inv)
        if delay is not None and delay > 0:
            late_count += 1
            late_sources.append(inv)
    if len(paid) >= 2:
        late_word = _COUNT_TR.get(late_count, str(late_count))
        if len(paid) == 3:
            paragraphs.append(f"Son üç faturanın {late_word} geç ödendi.")
        else:
            paragraphs.append(f"Son {len(paid)} faturanın {late_count}'si geç ödendi.")
        facts.append(
            {
                "key": "last_paid_late_count",
                "value": late_count,
                "display": f"{late_count}/{len(paid)}",
            }
        )
        for inv in late_sources:
            sources.append(
                _source(
                    type="invoice",
                    id=inv.id,
                    label=f"Fatura {inv.number}",
                    field="actual_delay_days",
                    value=invoice_actual_delay_days(inv),
                    url_hint=f"/invoices/{inv.id}",
                )
            )

    broken = (
        PaymentPromise.objects.filter(
            customer=customer,
            organization=org,
            status=PaymentPromiseStatus.BROKEN,
        )
        .order_by("-promised_date", "-id")
        .first()
    )
    if broken is not None:
        when = _fmt_date(broken.promised_date)
        paragraphs.append(
            f"Müşteri {when}'da verdiği ödeme sözünü yerine getirmedi."
        )
        facts.append(
            {
                "key": "broken_promise_date",
                "value": broken.promised_date.isoformat(),
                "display": when,
            }
        )
        sources.append(
            _source(
                type="payment_promise",
                id=broken.id,
                label=f"Ödeme sözü #{broken.id}",
                field="promised_date",
                value=broken.promised_date.isoformat(),
                url_hint="/promises",
            )
        )

    last_reached = (
        CollectionTask.objects.filter(
            customer=customer,
            organization=org,
            status=CollectionTaskStatus.COMPLETED,
            outcome=CallOutcome.REACHED,
        )
        .order_by("-completed_at", "-id")
        .first()
    )
    contact_at = None
    contact_source = None
    if last_reached is not None and last_reached.completed_at is not None:
        contact_at = timezone.localtime(last_reached.completed_at).date()
        contact_source = last_reached
    elif customer.last_contact_at is not None:
        contact_at = timezone.localtime(customer.last_contact_at).date()

    if contact_at is not None:
        days_ago = (today - contact_at).days
        paragraphs.append(f"Son başarılı görüşme {days_ago} gün önce yapıldı.")
        facts.append(
            {
                "key": "last_successful_contact_days_ago",
                "value": days_ago,
                "display": f"{days_ago} gün önce",
            }
        )
        if contact_source is not None:
            sources.append(
                _source(
                    type="collection_task",
                    id=contact_source.id,
                    label=f"Görev #{contact_source.id}",
                    field="completed_at",
                    value=contact_source.completed_at.isoformat()
                    if contact_source.completed_at
                    else None,
                    url_hint="/collections",
                )
            )
        else:
            sources.append(
                _source(
                    type="customer",
                    id=customer.id,
                    label=name,
                    field="last_contact_at",
                    value=customer.last_contact_at.isoformat()
                    if customer.last_contact_at
                    else None,
                    url_hint=f"/customers/{customer.id}",
                )
            )

    return {
        "customer_id": customer.id,
        "organization_id": org.id,
        "as_of": today.isoformat(),
        "summary": "\n".join(paragraphs),
        "paragraphs": paragraphs,
        "facts": facts,
        "sources": sources,
    }


def summarize_customer_id(
    customer_id: int,
    *,
    organization,
    as_of: date | None = None,
) -> dict[str, Any]:
    customer = Customer.objects.select_related("organization").get(
        pk=customer_id,
        organization=organization,
    )
    return build_customer_summary(customer, organization=organization, as_of=as_of)
