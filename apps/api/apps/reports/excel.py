"""Excel workbook builders for reports (NP-160–163)."""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook

from apps.reports.models import ReportType

HEADERS = {
    ReportType.OVERDUE_RECEIVABLES: [
        "Müşteri",
        "Fatura",
        "Açık bakiye",
        "Vade",
        "Gecikme günü",
        "Risk",
        "Son iletişim",
        "Ödeme sözü",
    ],
    ReportType.COLLECTION_ACTIVITY: [
        "Kullanıcı",
        "E-posta",
        "Tamamlanan görev",
        "Yapılan görüşme",
        "Alınan ödeme sözü",
        "Tutulan söz",
        "Bozulan söz",
        "Tahsil edilen tutar",
    ],
    ReportType.CUSTOMER_RISK: [
        "Müşteri",
        "Kod",
        "Risk skoru",
        "Risk seviyesi",
        "Risk nedenleri",
        "Gecikmiş bakiye",
        "Ortalama gecikme",
        "Bozulan söz sayısı",
        "Son ödeme tarihi",
    ],
    ReportType.DISPUTE_RESOLUTION: [
        "Metrik",
        "Değer",
        "Kategori",
        "Müşteri",
    ],
}

SHEET_TITLES = {
    ReportType.OVERDUE_RECEIVABLES: "Gecikmiş alacak",
    ReportType.COLLECTION_ACTIVITY: "Tahsilat aktivite",
    ReportType.CUSTOMER_RISK: "Müşteri risk",
    ReportType.DISPUTE_RESOLUTION: "İtiraz çözüm",
}


def rows_to_workbook(report_type: str, rows: list[dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_TITLES.get(report_type, "Rapor")[:31]
    headers = HEADERS.get(report_type, [])
    ws.append(headers)

    if report_type == ReportType.OVERDUE_RECEIVABLES:
        for r in rows:
            ws.append(
                [
                    r.get("customer_name", ""),
                    r.get("invoice_number", ""),
                    r.get("open_balance", ""),
                    r.get("due_date", ""),
                    r.get("overdue_days", ""),
                    f"{r.get('risk_status', '')} ({r.get('risk_score', '')})",
                    r.get("last_contact_at", ""),
                    r.get("payment_promise", ""),
                ]
            )
    elif report_type == ReportType.COLLECTION_ACTIVITY:
        for r in rows:
            ws.append(
                [
                    r.get("user_name", ""),
                    r.get("user_email", ""),
                    r.get("tasks_completed", 0),
                    r.get("contacts_made", 0),
                    r.get("promises_taken", 0),
                    r.get("promises_kept", 0),
                    r.get("promises_broken", 0),
                    r.get("collected_amount", ""),
                ]
            )
    elif report_type == ReportType.CUSTOMER_RISK:
        for r in rows:
            ws.append(
                [
                    r.get("customer_name", ""),
                    r.get("customer_code", ""),
                    r.get("risk_score", 0),
                    r.get("risk_status", ""),
                    r.get("risk_reasons", ""),
                    r.get("overdue_balance", ""),
                    r.get("avg_delay_days") if r.get("avg_delay_days") is not None else "",
                    r.get("broken_promise_count", 0),
                    r.get("last_payment_date", ""),
                ]
            )
    elif report_type == ReportType.DISPUTE_RESOLUTION:
        for r in rows:
            ws.append(
                [
                    r.get("metric", ""),
                    r.get("value", ""),
                    r.get("category", ""),
                    r.get("customer", ""),
                ]
            )

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
