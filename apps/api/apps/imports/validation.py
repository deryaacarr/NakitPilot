"""NP-064 row validation + NP-065 duplicate key helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from apps.customers.models import Customer
from apps.imports.services_io import _cell_to_str, mapped_row, parse_date, parse_money
from apps.invoices.models import Invoice

ZERO = Decimal("0.00")


@dataclass
class RowIssue:
    row_number: int
    field_name: str
    raw_value: str
    error_message: str
    kind: str = "VALIDATION"  # VALIDATION | DUPLICATE


@dataclass
class ValidatedRow:
    row_number: int
    customer_code: str
    customer_name: str
    tax_number: str
    phone: str
    email: str
    invoice_number: str
    invoice_date: date | None
    due_date: date | None
    currency: str
    total_amount: Decimal | None
    paid_amount: Decimal
    existing_customer: Customer | None = None
    existing_invoice: Invoice | None = None
    is_duplicate: bool = False
    issues: list[RowIssue] = field(default_factory=list)

    @property
    def has_validation_errors(self) -> bool:
        return any(i.kind == "VALIDATION" for i in self.issues)


def find_existing_invoice(
    *,
    organization,
    customer: Customer | None,
    invoice_number: str,
    invoice_date: date,
    total_amount: Decimal,
) -> Invoice | None:
    qs = Invoice.objects.filter(
        organization=organization,
        number=invoice_number,
        invoice_date=invoice_date,
        total_amount=total_amount,
    ).select_related("customer")
    if customer is not None:
        qs = qs.filter(customer=customer)
    return qs.first()


def resolve_customer(
    *,
    organization,
    customer_code: str,
    customer_name: str,
) -> tuple[Customer | None, RowIssue | None]:
    if customer_code:
        found = Customer.objects.filter(organization=organization, code=customer_code).first()
        if found:
            return found, None
        if not customer_name:
            return None, RowIssue(
                row_number=0,
                field_name="müşteri_kodu",
                raw_value=customer_code,
                error_message="Müşteri bulunamadı",
                kind="VALIDATION",
            )
        return None, None

    if customer_name:
        found = Customer.objects.filter(
            organization=organization,
            name__iexact=customer_name,
        ).first()
        return found, None

    return None, RowIssue(
        row_number=0,
        field_name="müşteri_adı",
        raw_value="",
        error_message="Müşteri adı veya kodu gerekli.",
        kind="VALIDATION",
    )


def validate_mapped_row(
    *,
    row_number: int,
    mapped: dict[str, Any],
    organization,
) -> ValidatedRow:
    """NP-064 validations for a single mapped row."""
    issues: list[RowIssue] = []

    customer_code = _cell_to_str(mapped.get("müşteri_kodu"))
    customer_name = _cell_to_str(mapped.get("müşteri_adı"))
    tax_number = _cell_to_str(mapped.get("vergi_numarası"))
    phone = _cell_to_str(mapped.get("telefon"))
    email = _cell_to_str(mapped.get("email"))
    invoice_number = _cell_to_str(mapped.get("fatura_numarası"))
    raw_invoice_date = mapped.get("fatura_tarihi")
    raw_due_date = mapped.get("vade_tarihi")
    raw_amount = mapped.get("fatura_tutarı")
    raw_paid = mapped.get("ödenen_tutar")
    currency = (_cell_to_str(mapped.get("para_birimi")) or "TRY").upper()

    invoice_date = parse_date(raw_invoice_date)
    due_date = parse_date(raw_due_date)
    amount = parse_money(raw_amount)
    paid = parse_money(raw_paid)

    if not invoice_number:
        issues.append(
            RowIssue(
                row_number=row_number,
                field_name="fatura_numarası",
                raw_value="",
                error_message="Boş fatura numarası",
            )
        )

    if invoice_date is None:
        issues.append(
            RowIssue(
                row_number=row_number,
                field_name="fatura_tarihi",
                raw_value=_cell_to_str(raw_invoice_date),
                error_message="Geçersiz tarih",
            )
        )

    if due_date is None:
        issues.append(
            RowIssue(
                row_number=row_number,
                field_name="vade_tarihi",
                raw_value=_cell_to_str(raw_due_date),
                error_message="Geçersiz tarih",
            )
        )

    if amount is None:
        issues.append(
            RowIssue(
                row_number=row_number,
                field_name="fatura_tutarı",
                raw_value=_cell_to_str(raw_amount),
                error_message="Tutar sayısal değil",
            )
        )
    elif amount < ZERO:
        issues.append(
            RowIssue(
                row_number=row_number,
                field_name="fatura_tutarı",
                raw_value=_cell_to_str(raw_amount),
                error_message="Negatif tutar",
            )
        )

    if invoice_date and due_date and due_date < invoice_date:
        issues.append(
            RowIssue(
                row_number=row_number,
                field_name="vade_tarihi",
                raw_value=due_date.isoformat(),
                error_message="Vade tarihi fatura tarihinden önce",
            )
        )

    customer, customer_issue = resolve_customer(
        organization=organization,
        customer_code=customer_code,
        customer_name=customer_name,
    )
    if customer_issue:
        customer_issue.row_number = row_number
        issues.append(customer_issue)

    existing_invoice = None
    is_duplicate = False
    if invoice_number and invoice_date is not None and amount is not None and amount >= ZERO:
        existing_invoice = find_existing_invoice(
            organization=organization,
            customer=customer,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            total_amount=amount,
        )
        if existing_invoice is not None:
            is_duplicate = True
            issues.append(
                RowIssue(
                    row_number=row_number,
                    field_name="fatura_numarası",
                    raw_value=invoice_number,
                    error_message="Aynı fatura daha önce eklenmiş",
                    kind="DUPLICATE",
                )
            )

    return ValidatedRow(
        row_number=row_number,
        customer_code=customer_code,
        customer_name=customer_name or (customer.name if customer else ""),
        tax_number=tax_number,
        phone=phone,
        email=email,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        currency=currency if len(currency) == 3 else "TRY",
        total_amount=amount,
        paid_amount=paid if paid is not None else ZERO,
        existing_customer=customer,
        existing_invoice=existing_invoice,
        is_duplicate=is_duplicate,
        issues=issues,
    )


def validate_all_rows(
    *,
    rows: list[dict[str, Any]],
    mapping: dict[str, str | None],
    organization,
) -> list[ValidatedRow]:
    """Validate rows; mark NP-065 duplicates against DB and within the file."""
    results: list[ValidatedRow] = []
    seen_keys: set[tuple[str, str, date, Decimal]] = set()

    for index, row in enumerate(rows, start=2):
        validated = validate_mapped_row(
            row_number=index,
            mapped=mapped_row(row, mapping),
            organization=organization,
        )
        if (
            not validated.has_validation_errors
            and validated.invoice_number
            and validated.invoice_date is not None
            and validated.total_amount is not None
        ):
            customer_key = validated.customer_code or validated.customer_name.casefold()
            key = (
                customer_key,
                validated.invoice_number,
                validated.invoice_date,
                validated.total_amount,
            )
            if key in seen_keys and not validated.is_duplicate:
                validated.is_duplicate = True
                validated.issues.append(
                    RowIssue(
                        row_number=index,
                        field_name="fatura_numarası",
                        raw_value=validated.invoice_number,
                        error_message="Aynı fatura daha önce eklenmiş",
                        kind="DUPLICATE",
                    )
                )
            else:
                seen_keys.add(key)
        results.append(validated)
    return results
