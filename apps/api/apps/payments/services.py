"""Payment create / allocate / cancel orchestration (NP-070–074)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import write_audit_log
from apps.collections.services import evaluate_promises_after_payment
from apps.customers.metrics import customer_financial_metrics
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.services import recalculate_invoices_after_payment
from apps.payments.invariants import (
    FinancialInvariantError,
    assert_payment_allocations_within_amount,
    enforce_payment_financial_invariants,
)
from apps.payments.models import ZERO, Payment, PaymentAllocation
from apps.risk.triggers import bump_customer_risk

OPEN_STATUSES = {
    InvoiceStatus.OPEN,
    InvoiceStatus.OVERDUE,
    InvoiceStatus.PARTIALLY_PAID,
}


class PaymentValidationError(FinancialInvariantError):
    def __init__(self, message: str, code: str = "invalid_payment"):
        super().__init__(message, code=code)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def auto_allocate_oldest_first(
    *,
    organization,
    customer,
    payment_amount: Decimal,
    currency: str,
) -> list[dict[str, Any]]:
    """
    NP-072: open invoices for customer, oldest due_date first, until money runs out.
    Returns allocation dicts {invoice_id, amount}.
    """
    remaining = _quantize(payment_amount)
    if remaining <= ZERO:
        return []

    invoices = (
        Invoice.objects.for_organization(organization)
        .filter(customer=customer, currency=currency, status__in=OPEN_STATUSES)
        .order_by("due_date", "invoice_date", "id")
    )

    plan: list[dict[str, Any]] = []
    for invoice in invoices:
        if remaining <= ZERO:
            break
        due = _quantize(invoice.remaining_amount())
        if due <= ZERO:
            continue
        take = due if due <= remaining else remaining
        plan.append({"invoice_id": invoice.id, "amount": take})
        remaining -= take

    return plan


def validate_allocation_plan(
    *,
    organization,
    customer,
    payment_amount: Decimal,
    currency: str,
    allocations: list[dict[str, Any]],
    exclude_payment_id: int | None = None,
) -> list[tuple[Invoice, Decimal]]:
    """Validate manual/auto plan; return (invoice, amount) pairs."""
    if not allocations:
        return []

    seen: set[int] = set()
    total = ZERO
    resolved: list[tuple[Invoice, Decimal]] = []

    for row in allocations:
        invoice_id = int(row["invoice_id"])
        amount = _quantize(Decimal(str(row["amount"])))
        if amount <= ZERO:
            raise PaymentValidationError("Dağıtım tutarı pozitif olmalı.", "invalid_allocation")
        if invoice_id in seen:
            raise PaymentValidationError(
                "Aynı fatura birden fazla dağıtılamaz.",
                "duplicate_invoice_allocation",
            )
        seen.add(invoice_id)

        try:
            invoice = Invoice.objects.for_organization(organization).get(pk=invoice_id)
        except Invoice.DoesNotExist as exc:
            raise PaymentValidationError(
                f"Fatura bulunamadı: {invoice_id}",
                "invoice_not_found",
            ) from exc

        if invoice.customer_id != customer.id:
            raise PaymentValidationError(
                "Fatura bu müşteriye ait değil.",
                "invoice_customer_mismatch",
            )
        if invoice.currency != currency:
            raise PaymentValidationError(
                "Fatura para birimi ödeme ile uyuşmuyor.",
                "currency_mismatch",
            )
        if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}:
            raise PaymentValidationError(
                "Taslak/iptal faturalara dağıtım yapılamaz.",
                "invoice_not_allocatable",
            )

        remaining = invoice.remaining_amount()
        if exclude_payment_id is not None:
            current = (
                PaymentAllocation.objects.filter(
                    payment_id=exclude_payment_id,
                    invoice_id=invoice.id,
                ).aggregate(total=Sum("amount"))["total"]
                or ZERO
            )
            remaining = _quantize(remaining + Decimal(str(current)))

        if amount > remaining:
            raise PaymentValidationError(
                f"Fatura {invoice.number} için kalan tutarı aşıyor "
                f"(kalan={remaining}, dağıtılan={amount}).",
                "allocation_exceeds_remaining",
            )

        total += amount
        resolved.append((invoice, amount))

    if total > payment_amount:
        raise PaymentValidationError(
            f"Dağıtım toplamı ({total}) ödeme tutarını ({payment_amount}) aşıyor.",
            "allocation_exceeds_payment",
        )

    return resolved


def _persist_allocations(payment: Payment, resolved: list[tuple[Invoice, Decimal]]) -> list[int]:
    old_invoice_ids = list(payment.allocations.values_list("invoice_id", flat=True))
    payment.allocations.all().delete()
    for invoice, amount in resolved:
        PaymentAllocation.objects.create(
            organization=payment.organization,
            payment=payment,
            invoice=invoice,
            amount=amount,
        )
    payment.refresh_unallocated(save=True)
    # Amount invariants only here — status (PAID/OVERDUE) is checked after recalculate.
    assert_payment_allocations_within_amount(payment)
    return list({*old_invoice_ids, *[inv.id for inv, _ in resolved]})


def _after_payment_side_effects(
    payment: Payment,
    *,
    invoice_ids: list[int],
    actor=None,
    action: str,
) -> None:
    """NP-073: status, balance, promises, risk, audit."""
    if invoice_ids:
        recalculate_invoices_after_payment(invoice_ids)

    # NP-520: re-check after status recalculation (PAID/OVERDUE ↔ remaining)
    enforce_payment_financial_invariants(payment, invoice_ids=invoice_ids)

    customer = payment.customer
    customer.updated_at = timezone.now()
    customer.save(update_fields=["updated_at"])
    _ = customer_financial_metrics(customer)

    evaluate_promises_after_payment(customer, payment=payment)
    # NP-103: yeni ödeme / dağıtım → risk
    bump_customer_risk(customer)

    write_audit_log(
        organization=payment.organization,
        actor=actor,
        action=action,
        entity_type="Payment",
        entity_id=payment.id,
        summary=f"Ödeme {payment.amount} {payment.currency}",
        changes={
            "amount": str(payment.amount),
            "unallocated_amount": str(payment.unallocated_amount),
            "invoice_ids": invoice_ids,
            "customer_id": customer.id,
        },
    )


@transaction.atomic
def replace_allocations(
    payment: Payment,
    allocations: list[dict[str, Any]],
    *,
    actor=None,
) -> Payment:
    if payment.is_cancelled:
        raise PaymentValidationError("İptal edilmiş ödemeye dağıtım yapılamaz.", "payment_cancelled")

    resolved = validate_allocation_plan(
        organization=payment.organization,
        customer=payment.customer,
        payment_amount=payment.amount,
        currency=payment.currency,
        allocations=allocations,
        exclude_payment_id=payment.id,
    )
    invoice_ids = _persist_allocations(payment, resolved)
    _after_payment_side_effects(
        payment,
        invoice_ids=invoice_ids,
        actor=actor,
        action="payment.allocate",
    )
    return payment


@transaction.atomic
def create_payment(
    *,
    organization,
    customer,
    payment_date,
    amount: Decimal,
    currency: str = "TRY",
    method: str = "BANK_TRANSFER",
    reference: str = "",
    notes: str = "",
    recorded_by=None,
    allocations: list[dict[str, Any]] | None = None,
    auto_allocate: bool = False,
) -> Payment:
    amount = _quantize(amount)
    if amount <= ZERO:
        raise PaymentValidationError("Ödeme tutarı pozitif olmalı.", "invalid_amount")
    currency = (currency or "TRY").upper()
    if len(currency) != 3:
        raise PaymentValidationError("Geçersiz para birimi.", "invalid_currency")

    if customer.organization_id != organization.id:
        raise PaymentValidationError("Müşteri bu organizasyona ait değil.", "customer_mismatch")

    from apps.ops.locks import LockError, distributed_lock

    try:
        with distributed_lock("payment_allocate", organization.id, customer.id, timeout=120):
            return _create_payment_locked(
                organization=organization,
                customer=customer,
                payment_date=payment_date,
                amount=amount,
                currency=currency,
                method=method,
                reference=reference,
                notes=notes,
                recorded_by=recorded_by,
                allocations=allocations,
                auto_allocate=auto_allocate,
            )
    except LockError as exc:
        raise PaymentValidationError(
            "Bu müşteri için ödeme dağıtımı zaten çalışıyor.",
            "lock_held",
        ) from exc


def _create_payment_locked(
    *,
    organization,
    customer,
    payment_date,
    amount: Decimal,
    currency: str,
    method: str,
    reference: str,
    notes: str,
    recorded_by,
    allocations: list[dict[str, Any]] | None,
    auto_allocate: bool,
) -> Payment:
    plan = list(allocations or [])
    if auto_allocate:
        plan = auto_allocate_oldest_first(
            organization=organization,
            customer=customer,
            payment_amount=amount,
            currency=currency,
        )

    # Validate before insert when plan provided
    resolved: list[tuple[Invoice, Decimal]] = []
    if plan:
        resolved = validate_allocation_plan(
            organization=organization,
            customer=customer,
            payment_amount=amount,
            currency=currency,
            allocations=plan,
        )

    payment = Payment.objects.create(
        organization=organization,
        customer=customer,
        payment_date=payment_date,
        amount=amount,
        currency=currency,
        method=method,
        reference=reference or "",
        notes=notes or "",
        recorded_by=recorded_by,
        unallocated_amount=amount,
    )

    invoice_ids: list[int] = []
    if resolved:
        invoice_ids = _persist_allocations(payment, resolved)
    else:
        payment.refresh_unallocated(save=True)

    _after_payment_side_effects(
        payment,
        invoice_ids=invoice_ids,
        actor=recorded_by,
        action="payment.create",
    )
    return payment


@transaction.atomic
def cancel_payment(
    payment: Payment,
    *,
    user=None,
    reason: str = "",
) -> Payment:
    """NP-074: soft cancel; recalculate affected invoices."""
    if payment.is_cancelled:
        raise PaymentValidationError("Ödeme zaten iptal.", "already_cancelled")

    invoice_ids = list(payment.allocations.values_list("invoice_id", flat=True))
    payment.cancel(user=user, reason=reason)
    payment.unallocated_amount = ZERO
    payment.save(update_fields=["unallocated_amount", "updated_at"])

    if invoice_ids:
        recalculate_invoices_after_payment(invoice_ids)
        # Cancelled payment allocations are ignored; re-check invoice status invariants.
        enforce_payment_financial_invariants(payment, invoice_ids=invoice_ids)

    evaluate_promises_after_payment(payment.customer)
    # NP-103: ödeme iptali → risk
    bump_customer_risk(payment.customer)
    write_audit_log(
        organization=payment.organization,
        actor=user,
        action="payment.cancel",
        entity_type="Payment",
        entity_id=payment.id,
        summary=f"Ödeme iptal edildi ({payment.amount} {payment.currency})",
        changes={"reason": reason, "invoice_ids": invoice_ids},
    )
    return payment
