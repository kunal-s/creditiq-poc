"""Page images of a document's source file (F-05.6, F-16).

PDF pages are rendered with pypdfium2 (Apache-2.0 / BSD-3-Clause) to PNG
with Pillow (MIT-CMU); the rendered page keeps the page's own aspect, so
normalised evidence boxes ([0, 1] from the top-left) map straight onto it.
PNG and JPEG pass through unchanged; TIFF frames are converted to PNG;
the pasted message is drawn as text. Rendered images are cached under
`cases/<id>/pages/`.
"""

from __future__ import annotations

import io
import os
import sqlite3
from pathlib import Path

from . import filetypes
from .store import case_files_dir, cases_dir

RENDER_DPI = 150


class PageError(LookupError):
    pass


def _cache_dir(root: Path, case_id: str) -> Path:
    path = cases_dir(root) / case_id / "pages"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def _write_cache(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def page_image(conn: sqlite3.Connection, root: Path, case_id: str, document_id: str, page: int) -> tuple[bytes, str]:
    """(image bytes, media type) of absolute page `page` of the document's file."""
    doc = conn.execute("SELECT * FROM documents WHERE id = ? AND case_id = ?", (document_id, case_id)).fetchone()
    if doc is None:
        raise PageError(f"no document {document_id!r} in case {case_id!r}")
    file_row = conn.execute("SELECT * FROM files WHERE id = ?", (doc["file_id"],)).fetchone()
    if file_row is None or not file_row["stored_name"]:
        raise PageError("the source file is not held")
    source = case_files_dir(case_id, root) / file_row["stored_name"]
    content_type = file_row["content_type"]
    if content_type in (filetypes.PNG, filetypes.JPEG):
        if page != 1:
            raise PageError(f"an image has one page, not {page}")
        return source.read_bytes(), content_type

    cached = _cache_dir(root, case_id) / f"{file_row['sha256']}-p{page}.png"
    if cached.is_file():
        return cached.read_bytes(), filetypes.PNG
    if content_type == filetypes.PDF:
        data = _render_pdf(source.read_bytes(), page)
    elif content_type == filetypes.TIFF:
        data = _render_tiff(source.read_bytes(), page)
    elif content_type == "text/plain":
        if page != 1:
            raise PageError(f"the message has one page, not {page}")
        data = _render_text(source.read_text(encoding="utf-8", errors="replace"))
    else:
        raise PageError(f"no page images for {content_type}")
    _write_cache(cached, data)
    return data, filetypes.PNG


def _render_pdf(data: bytes, page: int) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        if not 1 <= page <= len(pdf):
            raise PageError(f"page {page} is outside 1-{len(pdf)}")
        bitmap = pdf[page - 1].render(scale=RENDER_DPI / 72)
        image = bitmap.to_pil()
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()
    finally:
        pdf.close()


def _render_tiff(data: bytes, page: int) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        frames = getattr(img, "n_frames", 1)
        if not 1 <= page <= frames:
            raise PageError(f"page {page} is outside 1-{frames}")
        img.seek(page - 1)
        out = io.BytesIO()
        img.convert("RGB").save(out, format="PNG")
        return out.getvalue()


def _render_text(text: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default()
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        while len(raw) > 110:
            lines.append(raw[:110])
            raw = raw[110:]
        lines.append(raw)
    width, line_height = 1240, 16
    img = Image.new("RGB", (width, max(1754, 40 + line_height * len(lines))), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((40, 30 + i * line_height), line, fill="black", font=font)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
