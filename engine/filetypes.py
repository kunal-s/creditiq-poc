"""True file type from content, and pre-flight checks (F-05.3).

The extension is never trusted. Standard library for the magic bytes and
the ZIP-based Office formats; pypdfium2 and Pillow (both permissive) to
confirm that a PDF or an image actually opens.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

# Supported formats (F-05.1) and their media types.
PDF = "application/pdf"
PNG = "image/png"
JPEG = "image/jpeg"
TIFF = "image/tiff"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CSV = "text/csv"
ZIP = "application/zip"
TEXT = "text/plain"
OCTET = "application/octet-stream"

SUPPORTED = {PDF, PNG, JPEG, TIFF, XLSX, DOCX, CSV}
IMAGES = {PNG, JPEG, TIFF}

_CFB = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ENCRYPTED_PACKAGE = "EncryptedPackage".encode("utf-16-le")


@dataclass
class Sniffed:
    content_type: str
    """The true media type, or OCTET when unknown."""
    outcome: str = "ok"
    """ok | rejected | exception"""
    reason_code: str | None = None
    """For exceptions: a config/quality.yaml reason code."""
    reason: str | None = None

    @property
    def is_archive(self) -> bool:
        return self.content_type == ZIP and self.outcome == "ok"


def looks_like_zip(head: bytes) -> bool:
    return head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))


def _zip_kind(data: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
    except (zipfile.BadZipFile, OSError, ValueError):
        return None
    if "xl/workbook.xml" in names:
        return XLSX
    if "word/document.xml" in names:
        return DOCX
    return ZIP


def _is_text(data: bytes) -> str | None:
    sample = data[:65536]
    if b"\x00" in sample:
        return None
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = sample.decode("cp1252")
        except UnicodeDecodeError:
            return None
    printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
    if not text or printable / len(text) < 0.95:
        return None
    lines = [line for line in text.splitlines() if line.strip()][:50]
    for delimiter in (",", ";", "\t", "|"):
        counts = [line.count(delimiter) for line in lines]
        if lines and counts[0] > 0 and sum(c == counts[0] for c in counts) >= 0.8 * len(counts):
            return CSV
    return TEXT


def sniff(data: bytes) -> Sniffed:
    """The true type of a whole file's bytes, and whether it can be read."""
    if not data:
        return Sniffed(OCTET, "exception", "corrupt", "The file is empty.")
    head = data[:16]
    if data.startswith(b"%PDF-") or b"%PDF-" in data[:1024]:
        return _check_pdf(data)
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return _check_image(data, PNG)
    if head.startswith(b"\xff\xd8\xff"):
        return _check_image(data, JPEG)
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return _check_image(data, TIFF)
    if looks_like_zip(head):
        kind = _zip_kind(data)
        if kind is None:
            return Sniffed(ZIP, "exception", "corrupt", "The archive is damaged and cannot be opened.")
        return Sniffed(kind)
    if head.startswith(_CFB):
        if _ENCRYPTED_PACKAGE in data:
            return Sniffed(OCTET, "exception", "encrypted", "The Office file is password-protected.")
        return Sniffed(
            OCTET, "rejected", None, "Older Office format (.xls or .doc) is not supported; send XLSX, DOCX or PDF."
        )
    text_kind = _is_text(data)
    if text_kind == CSV:
        return Sniffed(CSV)
    if text_kind == TEXT:
        return Sniffed(TEXT, "rejected", None, "Plain text is not a supported format; send PDF, image, XLSX, CSV or DOCX.")
    return Sniffed(OCTET, "rejected", None, "Unsupported format: the content is not PDF, image, XLSX, CSV, DOCX or ZIP.")


def _check_pdf(data: bytes) -> Sniffed:
    import pypdfium2 as pdfium

    if b"/Encrypt" in data:
        return Sniffed(PDF, "exception", "encrypted", "The PDF is password-protected.")
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            return Sniffed(PDF, "exception", "encrypted", "The PDF is password-protected.")
        return Sniffed(PDF, "exception", "corrupt", "The PDF is damaged and cannot be opened.")
    try:
        if len(pdf) == 0:
            return Sniffed(PDF, "exception", "blank", "The PDF has no pages.")
    finally:
        pdf.close()
    return Sniffed(PDF)


def _check_image(data: bytes, content_type: str) -> Sniffed:
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except Exception:  # Pillow raises many types for damaged images
        return Sniffed(content_type, "exception", "corrupt", "The image is damaged and cannot be opened.")
    return Sniffed(content_type)


def pdf_page_count(data: bytes) -> int:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()
