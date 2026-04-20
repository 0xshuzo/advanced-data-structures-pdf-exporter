"""PDF output validation."""

from __future__ import annotations

from pathlib import Path

from pdf_exporter.export.errors import PDFExportError


def validate_pdf(path: Path) -> None:
    """Validate output file is a non-empty PDF and not HTML."""
    if not path.exists():
        raise PDFExportError(f"Validation failed: file does not exist: {path}")

    if path.stat().st_size <= 0:
        path.unlink(missing_ok=True)
        raise PDFExportError(f"Validation failed: empty file: {path}")

    with path.open("rb") as handle:
        head = handle.read(1024)

    if head.startswith(b"%PDF"):
        return

    text_head = head.lower()
    path.unlink(missing_ok=True)
    if b"<html" in text_head or b"<!doctype html" in text_head:
        raise PDFExportError(f"Validation failed: HTML saved instead of PDF: {path}")
    raise PDFExportError(f"Validation failed: missing %PDF header: {path}")
