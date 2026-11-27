"""A multipart upload body, read as it streams (F-05.1): each part of field `files` spooled to disk with
its hash and cut off at its size limit, only the text fields a caller names kept (each to its limit), and
the body as a whole held to its parts and bytes. The limits are config/app.yaml `uploads`.
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from python_multipart.multipart import MultipartParser, parse_options_header

from . import filetypes
from .config import load_app_config

MB = 1024 * 1024


class UploadError(ValueError):
    pass


@dataclass
class Limits:
    max_file: int
    max_archive: int
    depth: int
    ratio: float
    max_entries: int
    junk_names: set[str]
    junk_prefixes: tuple[str, ...]
    junk_folders: set[str]
    max_form_field: int = 4096
    """Bytes a text field of an upload (its `channel`) may have (uploads.max_form_field_kb)."""
    max_case_part: int = 256 * 1024
    """Bytes the `case` part of the one-request create may have (uploads.max_case_part_kb)."""
    max_parts: int = 1000
    """Parts a multipart body may have, files and text fields together (uploads.max_parts)."""
    max_request: int = 1000 * MB
    """Bytes a multipart body may have in all (uploads.max_request_mb)."""


def limits() -> Limits:
    cfg = load_app_config()["uploads"]
    junk = cfg.get("junk", {})
    return Limits(
        max_file=int(cfg["max_file_mb"] * MB),
        max_archive=int(cfg["max_archive_mb"] * MB),
        depth=int(cfg["archive_depth"]),
        ratio=float(cfg.get("max_compression_ratio", 100)),
        max_entries=int(cfg.get("max_archive_entries", 5000)),
        junk_names={n.lower() for n in junk.get("names", [])},
        junk_prefixes=tuple(junk.get("prefixes", [])),
        junk_folders={n.lower() for n in junk.get("folders", [])},
        max_form_field=int(cfg.get("max_form_field_kb", 4) * 1024),
        max_case_part=int(cfg.get("max_case_part_kb", 256) * 1024),
        max_parts=int(cfg.get("max_parts", 1000)),
        max_request=int(cfg.get("max_request_mb", 1000) * MB),
    )


def check_content_length(value: str | None, lim: Limits) -> None:
    """Refuse a body that says it is larger than the request limit before any of it is read. A body that
    gives no length is held to the limit as it streams (MultipartReceiver.write)."""
    if value is None:
        return
    try:
        length = int(value)
    except ValueError:
        raise UploadError("the request's Content-Length is not a number") from None
    if length > lim.max_request:
        raise UploadError(f"the request is larger than the {lim.max_request // MB} MB limit")


def secure_dir(path: Path) -> Path:
    """The folder, created if need be, readable by the engine's user only (mode 700)."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


# --- Streaming multipart ---


@dataclass
class SpooledPart:
    original_name: str
    path: Path
    size: int = 0
    sha256: str = ""
    limit: int = 0
    oversize: bool = False


@dataclass
class _PartState:
    headers: dict[str, str] = field(default_factory=dict)
    header_field: bytes = b""
    header_value: bytes = b""
    name: str | None = None
    filename: str | None = None
    fh: io.BufferedWriter | None = None
    hasher: object = None
    head: bytes = b""
    part: SpooledPart | None = None
    text: bytes = b""
    text_limit: int | None = None
    """Bytes this text field may have; None for a field that is not kept (its data is dropped)."""


class MultipartReceiver:
    """Feeds a multipart body through python-multipart's streaming parser,
    spooling each part of field `files` to disk with its hash and cutting it
    off at the size limit.

    Only the text fields named in `text_fields` (name -> bytes allowed) are kept, each up to its limit;
    any other field's data is dropped as it arrives. The body as a whole is held to `max_request` bytes
    and `max_parts` parts (UploadError)."""

    def __init__(self, content_type: str, spool_dir: Path, lim: Limits,
                 text_fields: dict[str, int] | None = None) -> None:
        ctype, params = parse_options_header(content_type or "")
        if ctype != b"multipart/form-data" or b"boundary" not in params:
            raise UploadError("expected multipart/form-data with a boundary")
        self.spool_dir = secure_dir(spool_dir)
        self.limits = lim
        self.parts: list[SpooledPart] = []
        self.fields: dict[str, str] = {}
        self.oversize_fields: set[str] = set()
        """Text fields larger than their limit: refused by the caller, never cut short."""
        self.text_fields = {"channel": lim.max_form_field} if text_fields is None else text_fields
        self.received = 0
        self.part_count = 0
        self._s = _PartState()
        self.parser = MultipartParser(
            params[b"boundary"],
            {
                "on_part_begin": self._part_begin,
                "on_header_field": self._header_field,
                "on_header_value": self._header_value,
                "on_header_end": self._header_end,
                "on_headers_finished": self._headers_finished,
                "on_part_data": self._part_data,
                "on_part_end": self._part_end,
            },
        )

    def write(self, chunk: bytes) -> None:
        self.received += len(chunk)
        if self.received > self.limits.max_request:
            raise UploadError(f"the request is larger than the {self.limits.max_request // MB} MB limit")
        self.parser.write(chunk)

    def finish(self) -> None:
        self.parser.finalize()

    def discard(self) -> None:
        """Remove every file spooled so far, the one being received too (a refused request)."""
        s = self._s
        if s.fh is not None and not s.fh.closed:
            s.fh.close()
        for part in [*self.parts, *([s.part] if s.part is not None else [])]:
            part.path.unlink(missing_ok=True)

    def _part_begin(self) -> None:
        self.part_count += 1
        if self.part_count > self.limits.max_parts:
            raise UploadError(f"more than {self.limits.max_parts} parts in one request")
        self._s = _PartState()

    def _header_field(self, data: bytes, start: int, end: int) -> None:
        self._s.header_field += data[start:end]

    def _header_value(self, data: bytes, start: int, end: int) -> None:
        self._s.header_value += data[start:end]

    def _header_end(self) -> None:
        s = self._s
        s.headers[s.header_field.decode("latin-1").lower()] = s.header_value.decode("utf-8", "replace")
        s.header_field, s.header_value = b"", b""

    def _headers_finished(self) -> None:
        s = self._s
        _, params = parse_options_header(s.headers.get("content-disposition", ""))
        s.name = params.get(b"name", b"").decode("utf-8", "replace")
        filename = params.get(b"filename")
        s.filename = filename.decode("utf-8", "replace") if filename is not None else None
        if not (s.name == "files" and s.filename is not None):
            s.text_limit = self.text_fields.get(s.name)
        if s.name == "files" and s.filename is not None:
            path = self.spool_dir / uuid.uuid4().hex
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            s.fh = os.fdopen(fd, "wb")
            s.hasher = hashlib.sha256()
            # The browser may send a path ("KYC/pan.jpg"); keep only the name.
            name = s.filename.replace("\\", "/").split("/")[-1] or "unnamed"
            s.part = SpooledPart(original_name=name, path=path, limit=self.limits.max_archive)

    def _part_data(self, data: bytes, start: int, end: int) -> None:
        s = self._s
        chunk = data[start:end]
        if s.part is None:
            if s.text_limit is not None and len(s.text) <= s.text_limit:
                s.text += chunk[: s.text_limit + 1 - len(s.text)]
            return
        part = s.part
        if len(s.head) < 8:
            s.head += chunk[: 8 - len(s.head)]
            if len(s.head) >= 4:
                # An archive may be as large as the archive limit; anything else the file limit.
                part.limit = self.limits.max_archive if filetypes.looks_like_zip(s.head) else self.limits.max_file
        part.size += len(chunk)
        if part.oversize:
            return
        if part.size > part.limit:
            part.oversize = True
            return
        s.hasher.update(chunk)
        s.fh.write(chunk)

    def _part_end(self) -> None:
        s = self._s
        if s.part is not None:
            s.fh.close()
            s.part.sha256 = s.hasher.hexdigest()
            self.parts.append(s.part)
        elif s.text_limit is not None:
            if len(s.text) > s.text_limit:
                self.oversize_fields.add(s.name)
            else:
                self.fields[s.name] = s.text.decode("utf-8", "replace")
