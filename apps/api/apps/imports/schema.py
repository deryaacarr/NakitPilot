"""Canonical invoice import columns and Turkish header aliases (NP-060/062)."""

from __future__ import annotations

# Exact template headers (NP-060)
CANONICAL_COLUMNS: tuple[str, ...] = (
    "müşteri_kodu",
    "müşteri_adı",
    "vergi_numarası",
    "fatura_numarası",
    "fatura_tarihi",
    "vade_tarihi",
    "para_birimi",
    "fatura_tutarı",
    "ödenen_tutar",
    "telefon",
    "email",
)

# Required for a valid data row (preview / later commit)
REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "müşteri_adı",
        "fatura_numarası",
        "fatura_tarihi",
        "vade_tarihi",
        "fatura_tutarı",
    }
)

# Source header (normalized) → canonical field
HEADER_ALIASES: dict[str, str] = {
    # müşteri_kodu
    "musteri_kodu": "müşteri_kodu",
    "müşteri_kodu": "müşteri_kodu",
    "musteri kodu": "müşteri_kodu",
    "cari kod": "müşteri_kodu",
    "cari_kodu": "müşteri_kodu",
    "customer_code": "müşteri_kodu",
    "code": "müşteri_kodu",
    # müşteri_adı
    "musteri_adi": "müşteri_adı",
    "müşteri_adı": "müşteri_adı",
    "musteri adi": "müşteri_adı",
    "cari unvani": "müşteri_adı",
    "cari ünvanı": "müşteri_adı",
    "cari_unvan": "müşteri_adı",
    "unvan": "müşteri_adı",
    "müşteri": "müşteri_adı",
    "musteri": "müşteri_adı",
    "customer_name": "müşteri_adı",
    "customer": "müşteri_adı",
    "name": "müşteri_adı",
    # vergi
    "vergi_numarasi": "vergi_numarası",
    "vergi_numarası": "vergi_numarası",
    "vergi no": "vergi_numarası",
    "vkn": "vergi_numarası",
    "tckn": "vergi_numarası",
    "tax_number": "vergi_numarası",
    # fatura_numarası
    "fatura_numarasi": "fatura_numarası",
    "fatura_numarası": "fatura_numarası",
    "fatura no": "fatura_numarası",
    "belge no": "fatura_numarası",
    "belge_no": "fatura_numarası",
    "invoice_number": "fatura_numarası",
    "invoice_no": "fatura_numarası",
    # fatura_tarihi
    "fatura_tarihi": "fatura_tarihi",
    "belge tarihi": "fatura_tarihi",
    "invoice_date": "fatura_tarihi",
    # vade_tarihi
    "vade_tarihi": "vade_tarihi",
    "vade": "vade_tarihi",
    "due_date": "vade_tarihi",
    # para_birimi
    "para_birimi": "para_birimi",
    "currency": "para_birimi",
    "doviz": "para_birimi",
    "döviz": "para_birimi",
    # fatura_tutarı
    "fatura_tutari": "fatura_tutarı",
    "fatura_tutarı": "fatura_tutarı",
    "tutar": "fatura_tutarı",
    "borc": "fatura_tutarı",
    "borç": "fatura_tutarı",
    "amount": "fatura_tutarı",
    "total": "fatura_tutarı",
    # ödenen_tutar
    "odenen_tutar": "ödenen_tutar",
    "ödenen_tutar": "ödenen_tutar",
    "odenen": "ödenen_tutar",
    "paid_amount": "ödenen_tutar",
    # telefon / email
    "telefon": "telefon",
    "tel": "telefon",
    "phone": "telefon",
    "email": "email",
    "e-posta": "email",
    "e_posta": "email",
    "mail": "email",
}

FIELD_LABELS: dict[str, str] = {
    "müşteri_kodu": "Müşteri kodu",
    "müşteri_adı": "Müşteri adı",
    "vergi_numarası": "Vergi numarası",
    "fatura_numarası": "Fatura numarası",
    "fatura_tarihi": "Fatura tarihi",
    "vade_tarihi": "Vade tarihi",
    "para_birimi": "Para birimi",
    "fatura_tutarı": "Fatura tutarı",
    "ödenen_tutar": "Ödenen tutar",
    "telefon": "Telefon",
    "email": "E-posta",
}


def normalize_header(value: str) -> str:
    text = (value or "").strip().lower()
    # unify turkish chars for alias lookup where needed
    replacements = {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
    }
    folded = "".join(replacements.get(ch, ch) for ch in text)
    folded = folded.replace("-", " ").replace("_", " ")
    folded = " ".join(folded.split())
    return folded


def suggest_mapping(headers: list[str]) -> dict[str, str | None]:
    """
    Return mapping canonical_field → source header (or None).
    """
    mapping: dict[str, str | None] = {field: None for field in CANONICAL_COLUMNS}
    used_headers: set[str] = set()

    for header in headers:
        raw = (header or "").strip()
        if not raw or raw in used_headers:
            continue
        key = normalize_header(raw)
        # try folded and original underscore form
        candidates = [
            key,
            key.replace(" ", "_"),
            raw.strip().lower().replace(" ", "_"),
        ]
        canonical = None
        for candidate in candidates:
            canonical = HEADER_ALIASES.get(candidate)
            if canonical:
                break
        if canonical and mapping.get(canonical) is None:
            mapping[canonical] = raw
            used_headers.add(raw)

    return mapping
