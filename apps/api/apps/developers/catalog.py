"""Static catalog for developer portal docs (NP-206)."""

from __future__ import annotations

from apps.webhooks.events import WebhookEventType

ENDPOINT_DOCS = [
    {
        "method": "GET",
        "path": "/api/v1/customers",
        "summary": "Müşteri listesi",
        "scope": "customers:read",
        "request_example": None,
        "response_example": {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 1,
                    "code": "C-100",
                    "name": "Örnek A.Ş.",
                    "email": "info@ornek.com",
                    "risk_status": "LOW",
                    "risk_score": 12,
                }
            ],
        },
    },
    {
        "method": "POST",
        "path": "/api/v1/customers",
        "summary": "Müşteri oluştur",
        "scope": "customers:write",
        "headers": {"Idempotency-Key": "external-system-customer-1"},
        "request_example": {
            "code": "C-100",
            "name": "Örnek A.Ş.",
            "email": "info@ornek.com",
            "payment_term_days": 30,
        },
        "response_example": {
            "id": 1,
            "code": "C-100",
            "name": "Örnek A.Ş.",
            "is_active": True,
        },
    },
    {
        "method": "POST",
        "path": "/api/v1/invoices",
        "summary": "Fatura oluştur",
        "scope": "invoices:write",
        "headers": {"Idempotency-Key": "external-system-invoice-1"},
        "request_example": {
            "customer": 1,
            "number": "F-2026-001",
            "invoice_date": "2026-08-01",
            "due_date": "2026-08-31",
            "currency": "TRY",
            "subtotal_amount": "1000.00",
            "tax_amount": "180.00",
            "total_amount": "1180.00",
        },
        "response_example": {"id": 10, "number": "F-2026-001", "status": "OPEN"},
    },
    {
        "method": "POST",
        "path": "/api/v1/payments",
        "summary": "Ödeme oluştur",
        "scope": "payments:write",
        "headers": {"Idempotency-Key": "external-system-payment-1842"},
        "request_example": {
            "customer": 1,
            "payment_date": "2026-08-02",
            "amount": "500.00",
            "currency": "TRY",
            "auto_allocate": True,
        },
        "response_example": {"id": 20, "amount": "500.00", "unallocated_amount": "0.00"},
    },
    {
        "method": "GET",
        "path": "/api/v1/customers/{id}/risk",
        "summary": "Müşteri risk skoru",
        "scope": "risk:read",
        "request_example": None,
        "response_example": {
            "customer_id": 1,
            "score": 72,
            "level": "HIGH",
            "reasons": [{"code": "OVERDUE", "label": "Gecikmiş fatura", "points": 20}],
        },
    },
    {
        "method": "GET",
        "path": "/api/v1/forecast/cash-flow",
        "summary": "Nakit akışı tahmini",
        "scope": "forecast:read",
        "request_example": None,
        "response_example": {"weeks": 13, "currency": "TRY"},
    },
]


def webhook_event_catalog() -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in WebhookEventType.choices]


def portal_docs_payload() -> dict:
    return {
        "openapi_schema_url": "/api/v1/schema",
        "openapi_docs_url": "/api/v1/docs",
        "auth": {
            "header": "Authorization: Bearer npk_…",
            "alternate_header": "X-Api-Key: npk_…",
            "idempotency_header": "Idempotency-Key",
        },
        "endpoints": ENDPOINT_DOCS,
        "webhook_events": webhook_event_catalog(),
        "webhook_headers": [
            "X-NakitPilot-Event",
            "X-NakitPilot-Timestamp",
            "X-NakitPilot-Signature",
            "X-NakitPilot-Delivery-Id",
        ],
    }
