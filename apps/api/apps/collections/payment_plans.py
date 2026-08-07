"""NP-234 — payment plan suggestions (non-binding; approval required to persist)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.collections.models import CollectionActivity, CollectionActivityType, PaymentPromise
from apps.collections.promises import create_promise
from apps.customers.metrics import OPEN_STATUSES, customer_financial_metrics
from apps.customers.models import Customer
from apps.invoices.models import Invoice, InvoiceStatus
from apps.payments.models import ZERO, Payment

DISCLAIMER = (
    "Bu öneriler bağlayıcı finansal karar değildir; yalnızca tahsilat görüşmesi "
    "için yardımcı seçeneklerdir. Uygulamak için kullanıcı onayı gerekir."
)

OPTION_UPFRONT = "UPFRONT_PLUS_INSTALLMENTS"
OPTION_WEEKLY = "WEEKLY"
OPTION_OLDEST = "OLDEST_INVOICES_FIRST"

# Reference shapes from NP-234 (scaled to actual open balance).
_REF_UPFRONT = Decimal("150000.00")
_REF_WEEKLY = Decimal("75000.00")


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


def _q(amount: Decimal) -> Decimal:
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _open_invoices(customer: Customer, organization) -> list[tuple[Invoice, Decimal]]:
    rows: list[tuple[Invoice, Decimal]] = []
    qs = (
        Invoice.objects.filter(customer=customer, organization=organization)
        .exclude(status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED, InvoiceStatus.PAID])
        .order_by("due_date", "id")
    )
    for inv in qs:
        remaining = inv.remaining_amount()
        if remaining <= ZERO or inv.status not in OPEN_STATUSES:
            continue
        rows.append((inv, remaining))
    return rows


def _payment_history_signals(customer: Customer) -> dict[str, Any]:
    """Lightweight history signals used to adjust weekly/upfront sizing."""
    from django.db.models import Avg, Count

    payments = Payment.objects.filter(customer=customer, cancelled_at__isnull=True)
    stats = payments.aggregate(
        total=Sum("amount"),
        count=Count("id"),
        avg_amount=Avg("amount"),
    )
    last = payments.order_by("-payment_date", "-id").first()
    return {
        "payment_count": int(stats["count"] or 0),
        "payment_total": _q(Decimal(str(stats["total"] or ZERO))),
        "avg_payment": _q(Decimal(str(stats["avg_amount"] or ZERO))),
        "last_payment_date": last.payment_date.isoformat() if last else None,
        "last_payment_amount": str(_q(last.amount)) if last else None,
    }


def _split_remainder(total: Decimal, parts: int) -> list[Decimal]:
    if parts <= 0:
        return []
    if total <= ZERO:
        return [ZERO] * parts
    base = (total / parts).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    amounts = [base] * parts
    amounts[-1] = _q(total - base * (parts - 1))
    return amounts


def _option_upfront(open_balance: Decimal, *, as_of: date, history: dict[str, Any]) -> dict[str, Any]:
    """Seçenek 1: peşin + kalan iki taksit (DB bakiyesine göre)."""
    avg = history.get("avg_payment") or ZERO
    # Prefer ~150k peşin when balance allows; otherwise ~40% or avg payment capacity.
    if open_balance > _REF_UPFRONT:
        upfront = _REF_UPFRONT
        if avg > ZERO and avg < upfront:
            # Soften peşin toward demonstrated payment capacity (still from DB).
            upfront = _q(max(avg, min(upfront, open_balance * Decimal("0.45"))))
    else:
        upfront = _q(open_balance * Decimal("0.40"))
        if avg > ZERO:
            upfront = _q(min(max(upfront, avg), open_balance * Decimal("0.60")))

    if upfront >= open_balance:
        upfront = _q(open_balance * Decimal("0.50"))
    remainder = _q(open_balance - upfront)
    part_a, part_b = _split_remainder(remainder, 2)

    d1 = as_of + timedelta(days=3)
    d2 = as_of + timedelta(days=17)
    d3 = as_of + timedelta(days=31)
    steps = [
        {
            "amount": str(upfront),
            "due_date": d1.isoformat(),
            "label": f"Peşin {_fmt_money(upfront)}",
            "invoice_id": None,
            "invoice_number": None,
        },
        {
            "amount": str(part_a),
            "due_date": d2.isoformat(),
            "label": f"1. taksit {_fmt_money(part_a)}",
            "invoice_id": None,
            "invoice_number": None,
        },
        {
            "amount": str(part_b),
            "due_date": d3.isoformat(),
            "label": f"2. taksit {_fmt_money(part_b)}",
            "invoice_id": None,
            "invoice_number": None,
        },
    ]
    return {
        "id": OPTION_UPFRONT,
        "title": "Peşin + iki taksit",
        "summary": (
            f"{_fmt_money(upfront)} peşin, kalan {_fmt_money(remainder)} iki taksit"
        ),
        "steps": steps,
        "total_amount": str(open_balance),
        "is_binding": False,
        "requires_approval": True,
    }


def _option_weekly(open_balance: Decimal, *, as_of: date, history: dict[str, Any]) -> dict[str, Any]:
    """Seçenek 2: haftalık ödeme (DB bakiyesine göre)."""
    avg = history.get("avg_payment") or ZERO
    weekly = _REF_WEEKLY
    if open_balance <= weekly:
        # Smaller balance → fewer weeks at ~25% chunks
        weekly = _q(max(open_balance / Decimal("4"), Decimal("0.01")))
    elif avg > ZERO and avg < weekly:
        weekly = _q(max(avg, _REF_WEEKLY * Decimal("0.5")))

    if weekly > open_balance:
        weekly = open_balance

    n = int((open_balance / weekly).to_integral_value(rounding=ROUND_DOWN))
    n = max(n, 1)
    # Cap schedule length for UX
    n = min(n, 12)
    amounts = _split_remainder(open_balance, n)
    steps = []
    for i, amt in enumerate(amounts):
        due = as_of + timedelta(days=7 * (i + 1))
        steps.append(
            {
                "amount": str(amt),
                "due_date": due.isoformat(),
                "label": f"Hafta {i + 1}: {_fmt_money(amt)}",
                "invoice_id": None,
                "invoice_number": None,
            }
        )
    return {
        "id": OPTION_WEEKLY,
        "title": "Haftalık ödeme",
        "summary": f"Haftalık yaklaşık {_fmt_money(amounts[0])} ödeme ({n} hafta)",
        "steps": steps,
        "total_amount": str(open_balance),
        "is_binding": False,
        "requires_approval": True,
    }


def _option_oldest_first(
    open_balance: Decimal,
    invoices: list[tuple[Invoice, Decimal]],
    *,
    as_of: date,
) -> dict[str, Any]:
    """Seçenek 3: en eski faturaların öncelikli kapatılması."""
    steps = []
    for i, (inv, remaining) in enumerate(invoices):
        due = as_of + timedelta(days=7 * i)
        steps.append(
            {
                "amount": str(_q(remaining)),
                "due_date": due.isoformat(),
                "label": f"Fatura {inv.number}: {_fmt_money(remaining)}",
                "invoice_id": inv.id,
                "invoice_number": inv.number,
            }
        )
    if not steps and open_balance > ZERO:
        steps.append(
            {
                "amount": str(open_balance),
                "due_date": (as_of + timedelta(days=7)).isoformat(),
                "label": f"Açık bakiye {_fmt_money(open_balance)}",
                "invoice_id": None,
                "invoice_number": None,
            }
        )
    return {
        "id": OPTION_OLDEST,
        "title": "En eski faturalar önce",
        "summary": "Açık faturalar vade sırasıyla öncelikli kapatılır",
        "steps": steps,
        "total_amount": str(open_balance),
        "is_binding": False,
        "requires_approval": True,
    }


def suggest_payment_plans(
    customer: Customer,
    *,
    organization=None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    Return non-binding plan options from open balance + payment history.

    Does not write to the database.
    """
    org = organization or customer.organization
    if customer.organization_id != org.id:
        raise PermissionError("Customer is outside the request organization.")

    today = as_of or timezone.localdate()
    metrics = customer_financial_metrics(customer)
    open_balance = _q(Decimal(str(metrics["open_balance"] or ZERO)))
    history = _payment_history_signals(customer)
    invoices = _open_invoices(customer, org)

    options: list[dict[str, Any]] = []
    if open_balance > ZERO:
        options = [
            _option_upfront(open_balance, as_of=today, history=history),
            _option_weekly(open_balance, as_of=today, history=history),
            _option_oldest_first(open_balance, invoices, as_of=today),
        ]

    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "as_of": today.isoformat(),
        "open_balance": str(open_balance),
        "payment_history": {
            "payment_count": history["payment_count"],
            "avg_payment": str(history["avg_payment"]),
            "last_payment_date": history["last_payment_date"],
            "last_payment_amount": history["last_payment_amount"],
        },
        "options": options,
        "is_binding": False,
        "requires_approval": True,
        "disclaimer": DISCLAIMER,
    }


class PaymentPlanError(Exception):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


@transaction.atomic
def accept_payment_plan(
    customer: Customer,
    *,
    organization,
    option_id: str,
    confirmed: bool,
    actor=None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    Persist approved plan as payment promises.

    Requires ``confirmed=True``. Suggestions alone never create commitments.
    """
    if not confirmed:
        raise PaymentPlanError(
            "Onay olmadan ödeme planı kaydedilemez.",
            "confirmation_required",
        )

    payload = suggest_payment_plans(customer, organization=organization, as_of=as_of)
    option = next((o for o in payload["options"] if o["id"] == option_id), None)
    if option is None:
        raise PaymentPlanError("Geçersiz plan seçeneği.", "invalid_option")

    promises: list[PaymentPromise] = []
    invoice_map = {
        inv.id: inv for inv, _ in _open_invoices(customer, organization)
    }
    for step in option["steps"]:
        invoice = None
        inv_id = step.get("invoice_id")
        if inv_id is not None:
            invoice = invoice_map.get(inv_id)
        promise, _warnings = create_promise(
            organization=organization,
            customer=customer,
            promised_date=date.fromisoformat(step["due_date"]),
            amount=Decimal(step["amount"]),
            notes=(
                f"NP-234 onaylı plan ({option_id}): {step.get('label') or ''}. "
                "Öneri bağlayıcı değildi; kullanıcı onayı ile kaydedildi."
            ),
            invoice=invoice,
            created_by=actor,
        )
        promises.append(promise)

    CollectionActivity.objects.create(
        organization=organization,
        customer=customer,
        activity_type=CollectionActivityType.NOTE,
        summary=f"Ödeme planı onaylandı: {option['title']}",
        notes=option["summary"],
        created_by=actor,
        metadata={
            "payment_plan_option": option_id,
            "promise_ids": [p.id for p in promises],
            "was_binding_suggestion": False,
        },
    )

    return {
        "accepted": True,
        "option_id": option_id,
        "option_title": option["title"],
        "promise_ids": [p.id for p in promises],
        "disclaimer": DISCLAIMER,
        "message": "Plan kullanıcı onayı ile ödeme sözlerine dönüştürüldü.",
    }
