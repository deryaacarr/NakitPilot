"""KolayBi HTTP client (NP-192).

Auth: API key + channel → access token.
Companies: GET /companies (list authorized companies).

When ``KOLAYBI_MOCK`` is true or ``api_key`` starts with ``mock-``, returns
deterministic sandbox data so the connection UI works without live credentials.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings


class KolayBiClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _use_mock(credentials: dict[str, Any]) -> bool:
    if getattr(settings, "KOLAYBI_MOCK", False):
        return True
    api_key = str(credentials.get("api_key") or "")
    return api_key.startswith("mock-")


def _base_url(credentials: dict[str, Any]) -> str:
    override = (credentials.get("base_url") or getattr(settings, "KOLAYBI_BASE_URL", "") or "").strip()
    if override:
        return override.rstrip("/")
    sandbox = bool(credentials.get("sandbox", getattr(settings, "KOLAYBI_SANDBOX", True)))
    if sandbox:
        return "https://ofis-sandbox-api.kolaybi.com/kolaybi/v1"
    return "https://ofis-api.kolaybi.com/kolaybi/v1"


@dataclass(frozen=True)
class KolayBiCompany:
    id: str
    name: str
    tax_number: str = ""


@dataclass(frozen=True)
class KolayBiCustomerPage:
    items: list[dict[str, Any]]
    next_cursor: str | None = None


MOCK_CUSTOMERS: list[dict[str, Any]] = [
    {
        "id": "kb-cust-1",
        "name": "Alpha Market A.Ş.",
        "code": "ALP-1",
        "tax_number": "1111111111",
        "email": "alpha@example.com",
        "phone": "+905551111111",
        "is_active": True,
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-cust-2",
        "name": "Beta Lojistik Ltd.",
        "code": "BET-2",
        "tax_number": "2222222222",
        "email": "beta@example.com",
        "phone": "+905552222222",
        "is_active": True,
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-cust-3",
        "name": "Pasif Cari Eski",
        "code": "PAS-3",
        "tax_number": "3333333333",
        "email": "pasif@example.com",
        "phone": "+905553333333",
        "is_active": False,
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-cust-4",
        "name": "Delta Yazılım",
        "code": "DEL-4",
        "tax_number": "4444444444",
        "email": "delta@example.com",
        "phone": "+905554444444",
        "is_active": True,
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
]

MOCK_PAGE_SIZE = 2

MOCK_INVOICES: list[dict[str, Any]] = [
    {
        "id": "kb-inv-1",
        "customer_id": "kb-cust-1",
        "number": "F-2026-001",
        "invoice_date": "2026-01-10",
        "due_date": "2026-02-10",
        "currency": "TRY",
        "total_amount": "1000.00",
        "subtotal_amount": "847.46",
        "tax_amount": "152.54",
        "status": "open",
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-inv-2",
        "customer_id": "kb-cust-1",
        "number": "F-2026-002",
        "invoice_date": "2026-01-15",
        "due_date": "2026-02-15",
        "currency": "TRY",
        "total_amount": "250.50",
        "subtotal_amount": "212.29",
        "tax_amount": "38.21",
        "status": "open",
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-inv-3",
        "customer_id": "kb-cust-2",
        "number": "F-2026-003",
        "invoice_date": "2026-01-20",
        "due_date": "2026-02-20",
        "currency": "TRY",
        "total_amount": "500.00",
        "status": "cancelled",
        "is_cancelled": True,
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-inv-4",
        "customer_id": "kb-cust-2",
        "number": "F-2026-004",
        "invoice_date": "2026-01-25",
        "due_date": "2026-02-25",
        "currency": "TRY",
        "total_amount": "750.00",
        "status": "open",
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
]

MOCK_PAYMENTS: list[dict[str, Any]] = [
    {
        "id": "kb-pay-1",
        "customer_id": "kb-cust-1",
        "payment_date": "2026-02-01",
        "amount": "400.00",
        "currency": "TRY",
        "method": "havale",
        "invoice_ids": ["kb-inv-1"],
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-pay-2",
        "customer_id": "kb-cust-1",
        "payment_date": "2026-02-05",
        "amount": "100.00",
        "currency": "TRY",
        "method": "cash",
        "invoice_ids": [],
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-pay-3",
        "customer_id": "kb-cust-2",
        "payment_date": "2026-02-06",
        "amount": "200.00",
        "currency": "TRY",
        "method": "eft",
        "invoice_ids": ["kb-inv-4"],
        "is_cancelled": True,
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "id": "kb-pay-4",
        "customer_id": "kb-cust-2",
        "payment_date": "2026-02-07",
        "amount": "50.00",
        "currency": "TRY",
        "method": "bank_transfer",
        "invoice_ids": ["kb-inv-4"],
        "updated_at": "2026-01-01T00:00:00+00:00",
    },
]


def _filter_mock_since(rows: list[dict[str, Any]], updated_since) -> list[dict[str, Any]]:
    if updated_since is None:
        return rows
    from django.utils.dateparse import parse_datetime

    since = updated_since
    if hasattr(since, "tzinfo") and since.tzinfo is None:
        from django.utils import timezone as dj_tz

        since = dj_tz.make_aware(since, dj_tz.utc)
    filtered = []
    for row in rows:
        raw = row.get("updated_at")
        if not raw:
            continue
        ts = parse_datetime(str(raw).replace("Z", "+00:00"))
        if ts is not None and ts > since:
            filtered.append(row)
    return filtered


def _paginate_mock(rows: list[dict[str, Any]], cursor: str | None, page_size: int) -> KolayBiCustomerPage:
    offset = int(cursor or "0")
    chunk = rows[offset : offset + page_size]
    next_offset = offset + page_size
    next_cursor = str(next_offset) if next_offset < len(rows) else None
    return KolayBiCustomerPage(items=list(chunk), next_cursor=next_cursor)


class KolayBiClient:
    def __init__(self, credentials: dict[str, Any]) -> None:
        self.credentials = credentials
        self.api_key = str(credentials.get("api_key") or "").strip()
        self.channel = str(credentials.get("channel_id") or credentials.get("channel") or "").strip()
        self._token: str | None = None
        self.company_id = str(credentials.get("company_id") or "").strip()

    def test_connection(self) -> dict[str, Any]:
        if _use_mock(self.credentials):
            if not self.api_key or not self.channel:
                raise KolayBiClientError("API anahtarı ve channel_id gerekli.")
            return {"ok": True, "mode": "mock", "message": "Mock bağlantı başarılı."}
        token = self._get_access_token()
        return {"ok": True, "mode": "live", "message": "KolayBi bağlantısı doğrulandı.", "token_acquired": bool(token)}

    def list_companies(self) -> list[KolayBiCompany]:
        if _use_mock(self.credentials):
            return [
                KolayBiCompany(id="mock-co-1", name="Demo Ticaret A.Ş.", tax_number="1111111111"),
                KolayBiCompany(id="mock-co-2", name="Örnek Yazılım Ltd.", tax_number="2222222222"),
                KolayBiCompany(id="mock-co-3", name="NakitPilot Sandbox", tax_number="3333333333"),
            ]
        payload = self._request_json("GET", "/companies")
        rows = payload.get("data") if isinstance(payload, dict) else payload
        if isinstance(payload, dict) and rows is None:
            rows = payload.get("companies") or payload.get("results") or []
        if not isinstance(rows, list):
            raise KolayBiClientError("Unexpected companies response shape.")
        companies: list[KolayBiCompany] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("id") or row.get("company_id") or "").strip()
            name = str(row.get("name") or row.get("title") or row.get("company_name") or "").strip()
            if not cid or not name:
                continue
            companies.append(
                KolayBiCompany(
                    id=cid,
                    name=name,
                    tax_number=str(row.get("tax_number") or row.get("vkn") or "").strip(),
                )
            )
        return companies

    def list_customers(
        self,
        *,
        cursor: str | None = None,
        company_id: str | None = None,
        page_size: int = MOCK_PAGE_SIZE,
        updated_since=None,
    ) -> KolayBiCustomerPage:
        if _use_mock(self.credentials):
            rows = _filter_mock_since(MOCK_CUSTOMERS, updated_since)
            return _paginate_mock(rows, cursor, page_size)

        params: dict[str, str] = {"limit": str(page_size)}
        if cursor:
            params["cursor"] = cursor
        cid = (company_id or self.company_id or "").strip()
        if cid:
            params["company_id"] = cid
        if updated_since is not None:
            params["updated_since"] = updated_since.isoformat()
        payload = self._request_json("GET", "/associates", params=params)
        return self._parse_list_page(payload, keys=("data", "results", "associates"))

    def list_invoices(
        self,
        *,
        cursor: str | None = None,
        company_id: str | None = None,
        page_size: int = MOCK_PAGE_SIZE,
        updated_since=None,
    ) -> KolayBiCustomerPage:
        if _use_mock(self.credentials):
            rows = _filter_mock_since(MOCK_INVOICES, updated_since)
            return _paginate_mock(rows, cursor, page_size)

        params: dict[str, str] = {"limit": str(page_size), "type": "sales"}
        if cursor:
            params["cursor"] = cursor
        cid = (company_id or self.company_id or "").strip()
        if cid:
            params["company_id"] = cid
        if updated_since is not None:
            params["updated_since"] = updated_since.isoformat()
        payload = self._request_json("GET", "/invoices", params=params)
        return self._parse_list_page(payload, keys=("data", "results", "invoices"))

    def list_payments(
        self,
        *,
        cursor: str | None = None,
        company_id: str | None = None,
        page_size: int = MOCK_PAGE_SIZE,
        updated_since=None,
    ) -> KolayBiCustomerPage:
        if _use_mock(self.credentials):
            rows = _filter_mock_since(MOCK_PAYMENTS, updated_since)
            return _paginate_mock(rows, cursor, page_size)

        params: dict[str, str] = {"limit": str(page_size)}
        if cursor:
            params["cursor"] = cursor
        cid = (company_id or self.company_id or "").strip()
        if cid:
            params["company_id"] = cid
        if updated_since is not None:
            params["updated_since"] = updated_since.isoformat()
        payload = self._request_json("GET", "/payments", params=params)
        return self._parse_list_page(payload, keys=("data", "results", "payments"))

    def _parse_list_page(self, payload: Any, *, keys: tuple[str, ...]) -> KolayBiCustomerPage:
        rows: list = []
        next_cursor = None
        if isinstance(payload, dict):
            for key in keys:
                if payload.get(key) is not None:
                    rows = payload.get(key) or []
                    break
            next_cursor = (
                payload.get("next_cursor")
                or payload.get("next")
                or (payload.get("meta") or {}).get("next_cursor")
            )
        elif isinstance(payload, list):
            rows = payload
        if not isinstance(rows, list):
            raise KolayBiClientError("Unexpected list response shape.")
        return KolayBiCustomerPage(items=[r for r in rows if isinstance(r, dict)], next_cursor=next_cursor)

    def _get_access_token(self) -> str:
        if self._token:
            return self._token
        body = {"api_key": self.api_key, "channel": self.channel}
        payload = self._request_json(
            "POST",
            "/authenticate",
            body=body,
            auth=False,
        )
        token = (
            (payload.get("access_token") if isinstance(payload, dict) else None)
            or (payload.get("token") if isinstance(payload, dict) else None)
            or (payload.get("data", {}).get("access_token") if isinstance(payload, dict) else None)
        )
        if not token:
            raise KolayBiClientError("KolayBi access token alınamadı.")
        self._token = str(token)
        return self._token

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        auth: bool = True,
    ) -> Any:
        url = f"{_base_url(self.credentials)}{path}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if auth:
            headers["Authorization"] = f"Bearer {self._get_access_token()}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise KolayBiClientError(
                f"KolayBi HTTP {exc.code}: {detail or exc.reason}",
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise KolayBiClientError(f"KolayBi bağlantı hatası: {exc.reason}") from exc
