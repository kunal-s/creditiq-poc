"""The draft CAM and the PD note as downloads (F-23.5, F-24.3): Word and PDF files with the same
content as the screen.

`layout` turns the memo or the note into blocks that both files share; `docx` and `pdf` write them.
The writers take the contract's models only (Cam, PdNote), so the files can be drafted from any memo
or note, and the same memo always gives the same file.
"""

from __future__ import annotations

import re

from . import docx, pdf
from .layout import Document, cam_document, pd_note_document

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}
FILE_NAMES = {"cam": "CAM-draft", "pd_note": "PD-note"}
WRITERS = {"docx": docx.render, "pdf": pdf.render}

__all__ = ["FILE_NAMES", "MEDIA_TYPES", "Document", "cam_document", "file_name", "pd_note_document", "render"]


def render(document: Document, fmt: str) -> bytes:
    """The document as a file: fmt is docx or pdf."""
    return WRITERS[fmt](document)


def file_name(output: str, case_id: str, fmt: str) -> str:
    """"CAM-draft-BBG-2026-000004.docx", "PD-note-BBG-2026-000004.pdf"."""
    return f"{FILE_NAMES[output]}-{re.sub(r'[^A-Za-z0-9._-]', '_', case_id)}.{fmt}"
