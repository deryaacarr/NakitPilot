"""NP-352 — legal preparation package (ZIP with summary PDF text + JSON)."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.utils import timezone

from apps.collections.models import (
    CollectionActivity,
    Dispute,
    PaymentPromise,
)
from apps.customers.metrics import OPEN_STATUSES, customer_financial_metrics
from apps.imports.services_io import private_upload_root
from apps.invoices.models import Invoice
from apps.legal.models import LegalCase
from apps.messaging.models import OutboundEmail
from apps.payments.models import Payment


def _money(value) -> str:
    return f"{Decimal(str(value or 0)).quantize(Decimal('0.01'))}"


def build_package_payload(case: LegalCase) -> dict[str, Any]:
    org = case.organization
    customer = case.customer
    metrics = customer_financial_metrics(customer)

    open_invoices = []
    for inv in Invoice.objects.filter(
        organization=org, customer=customer, status__in=list(OPEN_STATUSES)
    ).order_by("due_date"):
        open_invoices.append(
            {
                "id": inv.id,
                "number": inv.number,
                "issue_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "total": _money(inv.total_amount),
                "remaining": _money(inv.remaining_amount()),
                "status": inv.status,
            }
        )

    payments = [
        {
            "id": p.id,
            "amount": _money(p.amount),
            "paid_at": p.payment_date.isoformat() if p.payment_date else None,
            "method": getattr(p, "method", "") or "",
            "reference": p.reference or "",
        }
        for p in Payment.objects.filter(organization=org, customer=customer)
        .filter(cancelled_at__isnull=True)
        .order_by("-payment_date")[:100]
    ]

    activities = [
        {
            "id": a.id,
            "type": a.activity_type,
            "summary": a.summary,
            "notes": a.notes,
            "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None,
        }
        for a in CollectionActivity.objects.filter(
            organization=org, customer=customer
        ).order_by("-occurred_at")[:200]
    ]

    promises = [
        {
            "id": p.id,
            "amount": _money(p.amount),
            "promised_date": p.promised_date.isoformat() if p.promised_date else None,
            "status": p.status,
            "notes": p.notes or "",
        }
        for p in PaymentPromise.objects.filter(
            organization=org, customer=customer
        ).order_by("-promised_date")[:100]
    ]

    emails = [
        {
            "id": m.id,
            "channel": "EMAIL",
            "subject": getattr(m, "subject", "") or "",
            "status": getattr(m, "status", ""),
            "created_at": m.created_at.isoformat() if getattr(m, "created_at", None) else None,
        }
        for m in OutboundEmail.objects.filter(
            organization=org, customer=customer
        ).order_by("-id")[:100]
    ]

    disputes = [
        {
            "id": d.id,
            "category": d.category,
            "status": d.status,
            "amount": _money(d.amount) if d.amount is not None else None,
            "opened_at": d.opened_at.isoformat() if d.opened_at else None,
        }
        for d in Dispute.objects.filter(organization=org, customer=customer).order_by(
            "-opened_at"
        )[:50]
    ]

    extra_docs = [
        {
            "id": d.id,
            "filename": d.original_filename,
            "notes": d.notes,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in case.documents.all()
    ]

    return {
        "generated_at": timezone.now().isoformat(),
        "disclaimer": (
            "Bu paket dosya hazırlığı içindir; hukuki tavsiye veya otomatik karar içermez."
        ),
        "case": {
            "id": case.id,
            "title": case.title,
            "status": case.status,
            "opened_at": case.opened_at.isoformat() if case.opened_at else None,
            "criteria_snapshot": case.criteria_snapshot,
            "manager_approved": case.manager_approved,
        },
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "code": customer.code,
            "tax_number": customer.tax_number,
            "email": customer.email,
            "phone": customer.phone,
            "city": customer.city or "",
        },
        "financial_summary": {
            "open_balance": _money(metrics.get("open_balance")),
            "overdue_balance": _money(metrics.get("overdue_balance")),
            "oldest_overdue_days": metrics.get("oldest_overdue_days"),
            "balance_at_open": _money(case.balance_at_open),
        },
        "open_invoices": open_invoices,
        "payment_history": payments,
        "call_notes": activities,
        "payment_promises": promises,
        "email_records": emails,
        "disputes": disputes,
        "extra_documents": extra_docs,
    }


def _summary_text(payload: dict[str, Any]) -> str:
    c = payload["customer"]
    f = payload["financial_summary"]
    lines = [
        "NakitPilot — Hukuki dosya hazırlık özeti",
        "=" * 48,
        payload["disclaimer"],
        "",
        f"Dosya #{payload['case']['id']}: {payload['case']['title']}",
        f"Durum: {payload['case']['status']}",
        f"Müşteri: {c['name']} ({c.get('code') or '-'})",
        f"Vergi no: {c.get('tax_number') or '-'}",
        f"Telefon: {c.get('phone') or '-'}",
        f"E-posta: {c.get('email') or '-'}",
        "",
        f"Açık bakiye: {f['open_balance']} TL",
        f"Gecikmiş bakiye: {f['overdue_balance']} TL",
        f"En eski gecikme (gün): {f.get('oldest_overdue_days')}",
        "",
        f"Açık fatura sayısı: {len(payload['open_invoices'])}",
        f"Ödeme kaydı: {len(payload['payment_history'])}",
        f"Görüşme/aktivite: {len(payload['call_notes'])}",
        f"Ödeme sözü: {len(payload['payment_promises'])}",
        f"E-posta kaydı: {len(payload['email_records'])}",
        f"İtiraz: {len(payload['disputes'])}",
        f"Ek belge: {len(payload['extra_documents'])}",
        "",
        f"Oluşturulma: {payload['generated_at']}",
    ]
    return "\n".join(lines)


def generate_legal_package(case: LegalCase) -> Path:
    """
    Build a ZIP containing:
    - ozet.txt (human-readable summary; PDF-like pack companion)
    - paket.json (structured data)
    - belgeler/ copies of attached case documents when readable
    """
    payload = build_package_payload(case)
    root = (
        private_upload_root()
        / "org"
        / str(case.organization_id)
        / "legal"
        / str(case.id)
        / "packages"
    )
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    zip_path = root / f"legal_case_{case.id}_{stamp}.zip"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ozet.txt", _summary_text(payload))
        zf.writestr(
            "paket.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        for doc in case.documents.all():
            src = Path(doc.stored_path)
            if src.is_file():
                zf.write(src, arcname=f"belgeler/{doc.original_filename}")

    zip_path.write_bytes(buf.getvalue())
    case.package_path = str(zip_path)
    case.package_generated_at = timezone.now()
    case.save(update_fields=["package_path", "package_generated_at", "updated_at"])
    return zip_path
