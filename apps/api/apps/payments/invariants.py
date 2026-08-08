"""NP-520 — Financial invariants (service + model enforcement).

Rules:
1. Invoice remaining (total − active allocations) must never be < 0.
2. Allocations onto an invoice must not exceed invoice.total_amount.
3. Sum of PaymentAllocation amounts must not exceed Payment.amount.
4. PAID invoices must have remaining_amount == 0.
5. OVERDUE invoices must have remaining_amount > 0.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.invoices.models import Invoice, InvoiceStatus
from apps.payments.models import ZERO, Payment, PaymentAllocation

Q = Decimal("0.01")


class FinancialInvariantError(Exception):
    """Raised when a money invariant would be violated."""

    def __init__(self, message: str, code: str = "financial_invariant"):
        super().__init__(message)
        self.message = message
        self.code = code


def _quantize(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Q)


def invoice_remaining_raw(invoice: Invoice) -> Decimal:
    """Unclamped remaining: total − active allocations (may be negative if corrupt)."""
    return _quantize(invoice.total_amount - invoice.allocated_amount())


def assert_invoice_remaining_non_negative(invoice: Invoice) -> None:
    raw = invoice_remaining_raw(invoice)
    if raw < ZERO:
        raise FinancialInvariantError(
            f"Fatura {getattr(invoice, 'number', invoice.pk)} kalan tutarı negatif olamaz "
            f"(kalan={raw}, toplam={invoice.total_amount}).",
            "invoice_remaining_negative",
        )


def assert_invoice_allocations_within_total(invoice: Invoice) -> None:
    allocated = _quantize(invoice.allocated_amount())
    total = _quantize(invoice.total_amount)
    if allocated > total:
        raise FinancialInvariantError(
            f"Faturaya dağıtılan ödeme ({allocated}) fatura toplamını ({total}) aşamaz "
            f"(fatura={getattr(invoice, 'number', invoice.pk)}).",
            "allocation_exceeds_invoice_total",
        )


def assert_payment_allocations_within_amount(payment: Payment) -> None:
    if payment.is_cancelled:
        return
    allocated = _quantize(payment.allocated_total())
    amount = _quantize(payment.amount)
    if allocated > amount:
        raise FinancialInvariantError(
            f"PaymentAllocation toplamı ({allocated}) Payment amount ({amount}) değerini aşamaz "
            f"(payment_id={payment.pk}).",
            "allocation_exceeds_payment",
        )


def assert_paid_invoice_remaining_zero(invoice: Invoice) -> None:
    if invoice.status != InvoiceStatus.PAID:
        return
    remaining = invoice.remaining_amount()
    if remaining != ZERO:
        raise FinancialInvariantError(
            f"PAID faturanın remaining_amount değeri 0 olmalı "
            f"(fatura={getattr(invoice, 'number', invoice.pk)}, kalan={remaining}).",
            "paid_invoice_nonzero_remaining",
        )
    # Also catch over-allocation masked by clamp.
    assert_invoice_remaining_non_negative(invoice)


def assert_overdue_invoice_remaining_positive(invoice: Invoice) -> None:
    if invoice.status != InvoiceStatus.OVERDUE:
        return
    remaining = invoice.remaining_amount()
    if remaining <= ZERO:
        raise FinancialInvariantError(
            f"OVERDUE faturanın remaining_amount değeri > 0 olmalı "
            f"(fatura={getattr(invoice, 'number', invoice.pk)}, kalan={remaining}).",
            "overdue_invoice_zero_remaining",
        )


def assert_invoice_status_invariants(invoice: Invoice) -> None:
    """PAID / OVERDUE status ↔ remaining amount consistency."""
    if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}:
        return
    assert_invoice_remaining_non_negative(invoice)
    assert_paid_invoice_remaining_zero(invoice)
    assert_overdue_invoice_remaining_positive(invoice)


def assert_allocation_would_be_valid(allocation: PaymentAllocation) -> None:
    """
    Pre-save guard for PaymentAllocation rows (NP-520 DB-level).

    Validates the would-be sums including this row so a failed write never inserts.
    """
    payment = allocation.payment
    invoice = allocation.invoice
    amount = _quantize(allocation.amount)
    if amount <= ZERO:
        raise FinancialInvariantError(
            "Dağıtım tutarı pozitif olmalı.",
            "invalid_allocation",
        )

    if not payment.is_cancelled:
        pay_qs = payment.allocations.all()
        if allocation.pk:
            pay_qs = pay_qs.exclude(pk=allocation.pk)
        other_pay = pay_qs.aggregate(total=Sum("amount"))["total"] or ZERO
        if _quantize(Decimal(str(other_pay)) + amount) > _quantize(payment.amount):
            raise FinancialInvariantError(
                f"PaymentAllocation toplamı ({_quantize(Decimal(str(other_pay)) + amount)}) "
                f"Payment amount ({payment.amount}) değerini aşamaz "
                f"(payment_id={payment.pk}).",
                "allocation_exceeds_payment",
            )

    inv_qs = invoice.allocations.filter(payment__cancelled_at__isnull=True)
    if allocation.pk:
        inv_qs = inv_qs.exclude(pk=allocation.pk)
    # If this payment is already cancelled, its new/updated row should not count —
    # but cancelled payments should not gain allocations in normal flows.
    if not payment.is_cancelled:
        other_inv = inv_qs.aggregate(total=Sum("amount"))["total"] or ZERO
        projected = _quantize(Decimal(str(other_inv)) + amount)
        total = _quantize(invoice.total_amount)
        if projected > total:
            raise FinancialInvariantError(
                f"Faturaya dağıtılan ödeme ({projected}) fatura toplamını ({total}) aşamaz "
                f"(fatura={getattr(invoice, 'number', invoice.pk)}).",
                "allocation_exceeds_invoice_total",
            )


def enforce_after_allocation_write(allocation: PaymentAllocation) -> None:
    """
    Post-save guard: call after PaymentAllocation.save().

    Ensures payment sum and invoice total cannot be breached by raw ORM writes.
    """
    payment = allocation.payment
    invoice = allocation.invoice

    assert_payment_allocations_within_amount(payment)
    assert_invoice_allocations_within_total(invoice)
    assert_invoice_remaining_non_negative(invoice)


def enforce_payment_financial_invariants(
    payment: Payment,
    *,
    invoice_ids: list[int] | None = None,
) -> None:
    """Full check after payment create / allocate / cancel side-effects."""
    assert_payment_allocations_within_amount(payment)

    ids = invoice_ids
    if ids is None:
        ids = list(payment.allocations.values_list("invoice_id", flat=True))

    if not ids:
        return

    invoices = Invoice.objects.filter(id__in=ids)
    for invoice in invoices:
        assert_invoice_allocations_within_total(invoice)
        assert_invoice_remaining_non_negative(invoice)
        assert_invoice_status_invariants(invoice)


def enforce_invoice_financial_invariants(invoice: Invoice) -> None:
    """Service-level check after invoice status recalculation."""
    assert_invoice_allocations_within_total(invoice)
    assert_invoice_remaining_non_negative(invoice)
    assert_invoice_status_invariants(invoice)


def audit_organization_financial_invariants(organization) -> list[dict]:
    """
    Scan org for invariant breaches (ops / tests). Returns list of violation dicts.
    Does not raise — used for reporting.
    """
    violations: list[dict] = []

    payments = Payment.objects.for_organization(organization).filter(cancelled_at__isnull=True)
    for payment in payments.iterator(chunk_size=200):
        try:
            assert_payment_allocations_within_amount(payment)
        except FinancialInvariantError as exc:
            violations.append(
                {
                    "entity": "Payment",
                    "entity_id": payment.id,
                    "code": exc.code,
                    "message": exc.message,
                }
            )

    # Invoices whose active allocations exceed total (or status mismatch).
    invoices = Invoice.objects.for_organization(organization).exclude(
        status__in=[InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]
    )
    for invoice in invoices.iterator(chunk_size=200):
        for checker in (
            assert_invoice_allocations_within_total,
            assert_invoice_remaining_non_negative,
            assert_invoice_status_invariants,
        ):
            try:
                checker(invoice)
            except FinancialInvariantError as exc:
                violations.append(
                    {
                        "entity": "Invoice",
                        "entity_id": invoice.id,
                        "code": exc.code,
                        "message": exc.message,
                    }
                )
                break

    return violations


def active_allocation_sum_for_invoice(invoice_id: int) -> Decimal:
    total = (
        PaymentAllocation.objects.filter(
            invoice_id=invoice_id,
            payment__cancelled_at__isnull=True,
        ).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )
    return _quantize(Decimal(str(total)))
