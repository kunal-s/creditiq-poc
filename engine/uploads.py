"""Document upload: single files, several files and ZIP archives (F-05).

Every file ends in a visible state (F-05.5): registered, duplicate,
ignored, rejected or exception. Bytes are stored under
`cases/<id>/files/<sha256>` (generated names, F-05.8; directories mode 700),
the original name is metadata only. Registered files are queued as one
processing job (F-02.3).

The multipart body is parsed as it streams in, so the size limits are
enforced before a file is held in full (F-05.1).
"""

from __future__ import annotations

import hashlib
import io
import os
import posixpath
import re
import sqlite3
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from python_multipart.multipart import MultipartParser, parse_options_header

from . import filetypes, jobs
from .config import load_app_config
from .contracts import FileRecord, UploadResult
from .db import log_decision, transaction
from .review_items import raise_item
from .store import case_files_dir, cases_dir
from .util import dumps, now_iso

MB = 1024 * 1024
BIG_MEMBER = 1 * MB


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
    )


def _secure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def label_hint(original_name: str, archive_path: str | None) -> str | None:
    """F-10.1: the words of the file name and its folders inside an archive
    (archive names themselves are left out). Never used to classify."""
    parts = (archive_path or original_name).replace("\\", "/").split("/")
    folders = [p for p in parts[:-1] if p and not p.lower().endswith(".zip")]
    stem = posixpath.splitext(parts[-1])[0]
    words = [re.sub(r"[_\-.+()\[\]]+", " ", p).strip().lower() for p in [*folders, stem]]
    words = [re.sub(r"\s+", " ", w) for w in words if w]
    return " / ".join(words) or None


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


class MultipartReceiver:
    """Feeds a multipart body through python-multipart's streaming parser,
    spooling each part of field `files` to disk with its hash and cutting it
    off at the size limit."""

    def __init__(self, content_type: str, spool_dir: Path, lim: Limits) -> None:
        ctype, params = parse_options_header(content_type or "")
        if ctype != b"multipart/form-data" or b"boundary" not in params:
            raise UploadError("expected multipart/form-data with a boundary")
        self.spool_dir = _secure_dir(spool_dir)
        self.limits = lim
        self.parts: list[SpooledPart] = []
        self.fields: dict[str, str] = {}
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
        self.parser.write(chunk)

    def finish(self) -> None:
        self.parser.finalize()

    def _part_begin(self) -> None:
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
            if s.name and len(s.text) < 4096:
                s.text += chunk
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
        elif s.name:
            self.fields[s.name] = s.text.decode("utf-8", "replace")


# --- Registration ---


def _unsafe_member(name: str) -> bool:
    path = name.replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return True
    return any(part == ".." for part in path.split("/"))


class Registrar:
    """Turns received bytes into file records for one upload."""

    def __init__(self, conn: sqlite3.Connection, root: Path, case_id: str, user_id: str, channel: str) -> None:
        self.conn = conn
        self.root = root
        self.case_id = case_id
        self.user_id = user_id
        self.channel = channel
        self.limits = limits()
        self.now = now_iso()
        self.records: list[dict] = []
        self.exceptions: list[dict] = []
        self.files_dir = case_files_dir(case_id, root)
        _secure_dir(cases_dir(root))
        _secure_dir(self.files_dir.parent)
        _secure_dir(self.files_dir)
        # SHA-256 -> file id of every earlier file of the case whose bytes are held.
        self.seen: dict[str, str] = {
            row["sha256"]: row["id"]
            for row in conn.execute(
                """SELECT sha256, id FROM files WHERE case_id = ? AND stored_name IS NOT NULL
                   ORDER BY uploaded_at DESC""",
                (case_id,),
            )
        }

    # A record for every file, whatever happens to it.
    def _record(
        self,
        *,
        original_name: str,
        archive_path: str | None,
        sha256: str,
        size: int,
        content_type: str,
        status: str,
        reason: str | None = None,
        reason_code: str | None = None,
        duplicate_of: str | None = None,
        stored: bool = False,
    ) -> dict:
        record = {
            "id": "F-" + uuid.uuid4().hex[:12].upper(),
            "case_id": self.case_id,
            "sha256": sha256,
            "original_name": original_name,
            "archive_path": archive_path,
            "content_type": content_type,
            "size_bytes": size,
            "channel": self.channel,
            "uploaded_by": self.user_id,
            "uploaded_at": self.now,
            "status": status,
            "reason": reason,
            "reason_code": reason_code,
            "duplicate_of": duplicate_of,
            "label_hint": label_hint(original_name, archive_path),
            "stored_name": sha256 if stored else None,
        }
        self.records.append(record)
        return record

    def _is_junk(self, path: str) -> bool:
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if not parts:
            return False
        name = parts[-1]
        if any(p.lower() in self.limits.junk_folders for p in parts[:-1]):
            return True
        return name.lower() in self.limits.junk_names or name.startswith(self.limits.junk_prefixes)

    def _store(self, data: bytes, sha256: str) -> None:
        target = self.files_dir / sha256
        if target.exists():
            return
        tmp = self.files_dir / f".{sha256}.{uuid.uuid4().hex}"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)

    def add_bytes(self, data: bytes, original_name: str, archive_path: str | None, depth: int) -> None:
        """One file's bytes: a top-level file (depth 0) or an archive member
        (depth = how many archives it sits inside)."""
        sha = hashlib.sha256(data).hexdigest()
        common = dict(original_name=original_name, archive_path=archive_path, sha256=sha, size=len(data))
        if self._is_junk(archive_path or original_name):
            self._record(**common, content_type=filetypes.OCTET, status="ignored", reason="System file, not a document.")
            return
        sniffed = filetypes.sniff(data)
        if sniffed.is_archive:
            if depth + 1 > self.limits.depth:
                self._record(
                    **common,
                    content_type=filetypes.ZIP,
                    status="rejected",
                    reason=f"Archive nested more than {self.limits.depth} levels deep; not unpacked.",
                )
                return
            self._unpack(io.BytesIO(data), archive_path or original_name, depth + 1, sha, len(data))
            return
        if len(data) > self.limits.max_file:
            self._record(
                **common,
                content_type=sniffed.content_type,
                status="rejected",
                reason=f"Larger than the {self.limits.max_file // MB} MB limit per file.",
            )
            return
        if sniffed.outcome == "rejected":
            self._record(**common, content_type=sniffed.content_type, status="rejected", reason=sniffed.reason)
            return
        if sha in self.seen:
            self._record(
                **common,
                content_type=sniffed.content_type,
                status="duplicate",
                reason="Same content as a file already received.",
                duplicate_of=self.seen[sha],
            )
            return
        self._store(data, sha)
        if sniffed.outcome == "exception":
            record = self._record(
                **common,
                content_type=sniffed.content_type,
                status="exception",
                reason=sniffed.reason,
                reason_code=sniffed.reason_code,
                stored=True,
            )
            self.exceptions.append(record)
        else:
            record = self._record(**common, content_type=sniffed.content_type, status="registered", stored=True)
        self.seen[sha] = record["id"]

    def _refuse_archive(self, label: str, sha: str, size: int, reason: str) -> None:
        name = label.replace("\\", "/").split("/")[-1]
        self._record(
            original_name=name,
            archive_path=label if "/" in label else None,
            sha256=sha,
            size=size,
            content_type=filetypes.ZIP,
            status="rejected",
            reason=reason,
        )

    def _unpack(self, source, label: str, depth: int, sha: str, size: int) -> None:
        """Unpack one archive. `label` is its own path, used as the prefix of
        every member's archive_path; `depth` counts this archive."""
        lim = self.limits
        try:
            zf = zipfile.ZipFile(source)
        except (zipfile.BadZipFile, OSError, ValueError):
            name = label.replace("\\", "/").split("/")[-1]
            record = self._record(
                original_name=name,
                archive_path=label if "/" in label else None,
                sha256=sha,
                size=size,
                content_type=filetypes.ZIP,
                status="exception",
                reason="The archive is damaged and cannot be opened.",
                reason_code="corrupt",
            )
            self.exceptions.append(record)
            return
        with zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            if len(infos) > lim.max_entries:
                self._refuse_archive(label, sha, size, f"Archive holds more than {lim.max_entries} files; not unpacked.")
                return
            declared = sum(i.file_size for i in infos)
            if declared > lim.max_archive:
                self._refuse_archive(
                    label,
                    sha,
                    size,
                    f"Archive expands to {declared // MB} MB, beyond the {lim.max_archive // MB} MB limit"
                    " (possible decompression bomb); not unpacked.",
                )
                return
            for info in infos:
                if info.file_size > BIG_MEMBER and info.file_size > lim.ratio * max(info.compress_size, 1):
                    self._refuse_archive(
                        label,
                        sha,
                        size,
                        f"A member expands more than {lim.ratio:g} times (possible decompression bomb); not unpacked.",
                    )
                    return
            budget = lim.max_archive
            for info in infos:
                member = info.filename
                name = member.replace("\\", "/").rstrip("/").split("/")[-1] or member
                member_path = f"{label}/{member}"
                if _unsafe_member(member):
                    self._record(
                        original_name=name,
                        archive_path=member_path,
                        sha256=hashlib.sha256(member.encode()).hexdigest(),
                        size=info.file_size,
                        content_type=filetypes.OCTET,
                        status="rejected",
                        reason="The path points outside the archive; not unpacked.",
                    )
                    continue
                if info.flag_bits & 0x1:
                    if self._is_junk(member_path):
                        self._record(
                            original_name=name,
                            archive_path=member_path,
                            sha256=hashlib.sha256(member.encode()).hexdigest(),
                            size=info.file_size,
                            content_type=filetypes.OCTET,
                            status="ignored",
                            reason="System file, not a document.",
                        )
                        continue
                    record = self._record(
                        original_name=name,
                        archive_path=member_path,
                        sha256=hashlib.sha256(f"{sha}/{member}".encode()).hexdigest(),
                        size=info.file_size,
                        content_type=filetypes.OCTET,
                        status="exception",
                        reason="The file is password-protected inside the archive.",
                        reason_code="encrypted",
                    )
                    self.exceptions.append(record)
                    continue
                data, refused = self._read_member(zf, info, budget)
                if refused:
                    self._record(
                        original_name=name,
                        archive_path=member_path,
                        sha256=hashlib.sha256(member.encode()).hexdigest(),
                        size=info.file_size,
                        content_type=filetypes.OCTET,
                        status="rejected",
                        reason=refused,
                    )
                    continue
                budget -= len(data)
                self.add_bytes(data, name, member_path, depth)

    def _read_member(self, zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: int) -> tuple[bytes, str | None]:
        """Read a member without trusting its declared size."""
        lim = self.limits
        out = bytearray()
        limit = min(lim.max_file, budget)
        try:
            with zf.open(info) as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    out += chunk
                    if len(out) >= 4 and filetypes.looks_like_zip(bytes(out[:4])):
                        limit = min(lim.max_archive, budget)
                    if len(out) > limit:
                        if limit == budget:
                            return b"", "The archive expands beyond its size limit (possible decompression bomb)."
                        return b"", f"Larger than the {lim.max_file // MB} MB limit per file."
        except (zipfile.BadZipFile, OSError, EOFError, ValueError, NotImplementedError):
            return b"", "The file is damaged inside the archive and cannot be read."
        return bytes(out), None

    def add_spooled(self, part: SpooledPart) -> None:
        if part.oversize:
            name_limit = self.limits.max_archive if part.limit == self.limits.max_archive else self.limits.max_file
            self._record(
                original_name=part.original_name,
                archive_path=None,
                sha256=part.sha256,
                size=part.size,
                content_type=filetypes.OCTET,
                status="rejected",
                reason=f"Larger than the {name_limit // MB} MB upload limit; not received in full.",
            )
            return
        with open(part.path, "rb") as fh:
            head = fh.read(8)
        if filetypes.looks_like_zip(head):
            with zipfile.ZipFile(part.path) if zipfile.is_zipfile(part.path) else _NoZip() as zf:
                names = set(zf.namelist()) if zf else set()
            if zf is not None and "xl/workbook.xml" not in names and "word/document.xml" not in names:
                self._unpack(str(part.path), part.original_name, 1, part.sha256, part.size)
                return
        self.add_bytes(part.path.read_bytes(), part.original_name, None, 0)

    def commit(self) -> UploadResult:
        registered = [r["id"] for r in self.records if r["status"] == "registered"]
        with transaction(self.conn):
            for r in self.records:
                self.conn.execute(
                    """INSERT INTO files (id, case_id, sha256, original_name, archive_path, content_type, size_bytes,
                           channel, uploaded_by, uploaded_at, status, reason, duplicate_of, label_hint, stored_name,
                           reason_code)
                       VALUES (:id, :case_id, :sha256, :original_name, :archive_path, :content_type, :size_bytes,
                           :channel, :uploaded_by, :uploaded_at, :status, :reason, :duplicate_of, :label_hint,
                           :stored_name, :reason_code)""",
                    r,
                )
            for r in self.exceptions:
                raise_item(
                    self.conn,
                    case_id=self.case_id,
                    kind="quality",
                    ref=f"file:{r['id']}",
                    summary=f"{r['original_name']}: {r['reason']}",
                    detail={"file_id": r["id"], "reason_code": r["reason_code"]},
                )
            job_id = (
                jobs.enqueue(self.conn, case_id=self.case_id, kind="process", payload={"file_ids": registered})
                if registered
                else None
            )
            counts: dict[str, int] = {}
            for r in self.records:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
            log_decision(
                self.conn,
                at=self.now,
                actor=self.user_id,
                case_id=self.case_id,
                action="files.uploaded",
                detail=dumps({"counts": counts, "job_id": job_id, "files": [r["id"] for r in self.records]}),
            )
        return UploadResult(files=[FileRecord(**r) for r in self.records], job_id=job_id)


class _NoZip:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def register_parts(
    conn: sqlite3.Connection,
    root: Path,
    *,
    case_id: str,
    user_id: str,
    channel: str,
    parts: list[SpooledPart],
) -> UploadResult:
    registrar = Registrar(conn, root, case_id, user_id, channel)
    try:
        for part in parts:
            registrar.add_spooled(part)
    finally:
        for part in parts:
            part.path.unlink(missing_ok=True)
    return registrar.commit()


def spool_dir(root: Path, case_id: str) -> Path:
    return cases_dir(root) / case_id / "incoming"
