"""NP-152 upload storage tests."""

from pathlib import Path

import pytest
from django.conf import settings

from apps.imports.services_io import (
    UploadValidationError,
    store_upload,
    validate_upload_file,
)
from apps.imports.services import build_invoice_template_bytes


def test_store_upload_uses_opaque_name_under_private_root(tmp_path, settings):
    settings.PRIVATE_UPLOAD_ROOT = tmp_path / "private"
    content = build_invoice_template_bytes()
    path = store_upload(organization_id=42, filename="Musteri Raporu.xlsx", content=content)
    stored = Path(path)
    assert stored.parent == (tmp_path / "private" / "org" / "42" / "imports").resolve()
    assert stored.name.endswith(".xlsx")
    assert "Musteri" not in stored.name
    assert len(stored.stem) == 32  # uuid4 hex


def test_validate_rejects_extension_mime_mismatch():
    content = build_invoice_template_bytes()
    with pytest.raises(UploadValidationError) as exc:
        validate_upload_file(
            filename="rows.csv",
            size=len(content),
            content_type="text/csv",
            content=content,
        )
    assert exc.value.code == "invalid_file_type"


def test_validate_accepts_xlsx_with_matching_mime():
    content = build_invoice_template_bytes()
    name = validate_upload_file(
        filename="ok.xlsx",
        size=len(content),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=content,
    )
    assert name == "ok.xlsx"
