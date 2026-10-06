"""Stage 1: the quality gate (FRD F-07). Deterministic; no OCR and no model.
Decides whether a file can be read at all, and says why not in plain language."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from ..config.models import QualityConfig, RoutingConfig
from ..readers import sheet as sheet_reader
from ..readers.pdf_text import PdfError, probe_pdf


@dataclass
class GateResult:
    status: str                # accepted | rejected
    kind: str | None           # pdf | png | jpg | tiff | bmp | webp | xlsx | csv
    reason: str | None = None  # reason code from quality.yaml
    message: str | None = None
    rescan_request: str | None = None
    pages: int | None = None

    def to_json(self) -> dict:
        return {"status": self.status, "kind": self.kind, "reason": self.reason, "message": self.message,
                "rescan_request": self.rescan_request, "pages": self.pages}


def sniff(data: bytes) -> str | None:
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    return None


def run_gate(data: bytes, filename: str, content_type: str, q: QualityConfig, r: RoutingConfig) -> GateResult:
    def reject(code: str, detail: str, kind: str | None = None) -> GateResult:
        return GateResult("rejected", kind, code, detail, q.reason_codes.get(code), None)

    if not data:
        return reject("empty", "The file is empty.")
    if len(data) > q.max_file_bytes:
        return reject("too_large", f"The file is {len(data) / 1048576:.1f} MB, over the {q.max_file_bytes // 1048576} MB limit.")
    kind = sniff(data)
    if kind == "xls":
        return reject("legacy_xls", "Legacy .xls files are not supported.", "xls")
    if kind is None and (filename.lower().endswith((".csv", ".tsv")) or content_type in ("text/csv", "text/plain")):
        if sheet_reader.decode_csv(data) is not None and b"\x00" not in data[:4096]:
            kind = "csv"
    if kind is None:
        return reject("unsupported", f'The file type "{content_type or "unknown"}" could not be recognised from its content.')
    if kind not in r.reading.accepted_formats:
        return reject("unsupported", f"{kind} files are not accepted.", kind)

    if kind == "pdf":
        try:
            n = probe_pdf(data)
        except PdfError as e:
            return reject(e.code, str(e), kind)
        if n == 0:
            return reject("corrupt", "The document has no pages.", kind)
        if n > q.max_pages:
            return reject("too_many_pages", f"The document has {n} pages; the limit is {q.max_pages}.", kind)
        return GateResult("accepted", kind, pages=n)
    if kind == "xlsx":
        try:
            sheets = sheet_reader.read_xlsx(data, q.max_sheet_cells)
        except sheet_reader.SheetError as e:
            return reject(e.code, str(e), kind)
        return GateResult("accepted", kind, pages=len(sheets))
    if kind == "csv":
        try:
            sheet_reader.read_csv(data, q.max_sheet_cells)
        except sheet_reader.SheetError as e:
            return reject(e.code, str(e), kind)
        return GateResult("accepted", kind, pages=1)
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        frames = getattr(Image.open(io.BytesIO(data)), "n_frames", 1)
    except (UnidentifiedImageError, OSError, SyntaxError) as e:
        return reject("corrupt", str(e), kind)
    if frames > q.max_pages:
        return reject("too_many_pages", f"The image has {frames} frames.", kind)
    return GateResult("accepted", kind, pages=frames)
