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
import shutil
import sqlite3
import uuid
import zipfile
from pathlib import Path

from . import filetypes, jobs
from .contracts import FileRecord, UploadResult
from .db import log_decision, transaction
from .multipart import (  # noqa: F401  (the upload's limits and receiver, as callers name them here)
    MB,
    Limits,
    MultipartReceiver,
    SpooledPart,
    UploadError,
    check_content_length,
    limits,
    secure_dir,
)
from .review_items import close_item, raise_item
from .store import case_files_dir, cases_dir
from .util import dumps, now_iso, stable_id

BIG_MEMBER = 1 * MB

_secure_dir = secure_dir


def label_hint(original_name: str, archive_path: str | None) -> str | None:
    """F-10.1: the words of the file name and its folders inside an archive
    (archive names themselves are left out). Never used to classify."""
    parts = (archive_path or original_name).replace("\\", "/").split("/")
    folders = [p for p in parts[:-1] if p and not p.lower().endswith(".zip")]
    stem = posixpath.splitext(parts[-1])[0]
    words = [re.sub(r"[_\-.+()\[\]]+", " ", p).strip().lower() for p in [*folders, stem]]
    words = [re.sub(r"\s+", " ", w) for w in words if w]
    return " / ".join(words) or None


# --- Registration ---


def _unsafe_member(name: str) -> bool:
    path = name.replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return True
    return any(part == ".." for part in path.split("/"))


class Registrar:
    """Turns received bytes into file records for one upload."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        root: Path,
        case_id: str,
        user_id: str,
        channel: str,
        *,
        files_dir: Path | None = None,
    ) -> None:
        """`files_dir` stages the bytes somewhere other than the case's folder, for a case that does not
        exist yet: `bind_case` then names it and the caller moves the folder into place."""
        self.conn = conn
        self.root = root
        self.case_id = case_id
        self.user_id = user_id
        self.channel = channel
        self.limits = limits()
        self.now = now_iso()
        self.records: list[dict] = []
        self.exceptions: list[dict] = []
        self.files_dir = files_dir or case_files_dir(case_id, root)
        if files_dir is None:
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
            # An archive may be as large as the archive limit, so it is opened from disk, never read whole.
            if not zipfile.is_zipfile(part.path):
                self._refuse_spooled(part, filetypes.ZIP, "The archive is damaged and cannot be opened; not unpacked.")
                return
            with zipfile.ZipFile(part.path) as zf:
                names = set(zf.namelist())
            if "xl/workbook.xml" not in names and "word/document.xml" not in names:
                self._unpack(str(part.path), part.original_name, 1, part.sha256, part.size)
                return
        if part.size > self.limits.max_file:
            # A workbook or document (a ZIP inside) admitted at the archive limit while it streamed.
            self._refuse_spooled(part, filetypes.OCTET, f"Larger than the {self.limits.max_file // MB} MB limit per file.")
            return
        self.add_bytes(part.path.read_bytes(), part.original_name, None, 0)

    def _refuse_spooled(self, part: SpooledPart, content_type: str, reason: str) -> None:
        self._record(original_name=part.original_name, archive_path=None, sha256=part.sha256, size=part.size,
                     content_type=content_type, status="rejected", reason=reason)

    @property
    def registered(self) -> int:
        """Files received as new documents (not ignored, rejected, duplicate or in exception)."""
        return sum(1 for r in self.records if r["status"] == "registered")

    def bind_case(self, case_id: str, files_dir: Path) -> None:
        """Name the case the files belong to and the folder they were moved to, for a Registrar that
        staged them before the case existed."""
        self.case_id = case_id
        self.files_dir = files_dir
        for r in self.records:
            r["case_id"] = case_id

    def commit(self) -> UploadResult:
        with transaction(self.conn):
            return self.write()

    def write(self) -> UploadResult:
        """Record every file, raise the items for the exceptions and queue the processing job, inside the
        transaction the caller holds (`commit` opens one; the one-request create shares the case's)."""
        registered = [r["id"] for r in self.records if r["status"] == "registered"]
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


#: Where the one-request create (POST /api/cases/intake) receives a case's files before the case exists.
INTAKE_SPOOL = "intake-spool"


def clear_intake_spool(root: Path) -> int:
    """Remove what a stopped engine left in the intake spool (a request's files are only ever there while
    the request runs). Returns how many folders were removed."""
    spool = Path(root) / INTAKE_SPOOL
    if not spool.is_dir():
        return 0
    removed = 0
    for entry in spool.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
        removed += 1
    return removed


def intake_staging(root: Path) -> Path:
    """A new folder (mode 700) for one request's files until its case exists: `incoming` receives the
    body as it streams, `files` holds the bytes registered. Outside the cases folder, so nothing that reads
    a case's folder sees it; the caller removes it whatever happens."""
    secure_dir(Path(root) / INTAKE_SPOOL)
    return secure_dir(Path(root) / INTAKE_SPOOL / uuid.uuid4().hex)


class ReadAgainError(ValueError):
    pass


def read_again(conn: sqlite3.Connection, root: Path, *, case_id: str, file_id: str, user_id: str) -> None:
    """Send a file in exception through processing again, as it was received.

    A file whose processing stopped (a step failed, or the configuration of the
    day could not read it) is not a judgement on the file, and uploading it again
    would be taken as a duplicate. Its earlier outcome is cleared, the quality
    item it raised is closed as read again, and the file is queued like a new one.
    """
    row = conn.execute("SELECT * FROM files WHERE id = ? AND case_id = ?", (file_id, case_id)).fetchone()
    if row is None:
        raise LookupError(f"no file {file_id!r} in case {case_id!r}")
    if row["status"] != "exception":
        raise ReadAgainError("only a file in exception is read again")
    if not row["stored_name"] or not (case_files_dir(case_id, root) / row["stored_name"]).is_file():
        raise ReadAgainError("the file's bytes are not held, so it cannot be read again")
    with transaction(conn):
        conn.execute(
            """UPDATE files SET status = 'registered', reason = NULL, reason_code = NULL, processed_at = NULL,
                   integrity = '[]', integrity_recommendation = NULL, integrity_facts = NULL, integrity_figures = NULL
               WHERE id = ?""",
            (file_id,),
        )
        close_item(conn, item_id=stable_id("RV", case_id, "quality", f"file:{file_id}"), decision="waive",
                   reason="Read again", decided_by=user_id)
        jobs.enqueue(conn, case_id=case_id, kind="process", payload={"file_ids": [file_id]})
        log_decision(conn, at=now_iso(), actor=user_id, case_id=case_id, action="file.read_again",
                     detail=dumps({"file_id": file_id, "was": row["reason"], "reason_code": row["reason_code"]}))


def recheck_integrity(conn: sqlite3.Connection, root: Path, *, case_id: str, file_id: str, user_id: str) -> None:
    """Queue a file's integrity checks to run again, its documents untouched (F-07A)."""
    row = conn.execute("SELECT * FROM files WHERE id = ? AND case_id = ?", (file_id, case_id)).fetchone()
    if row is None:
        raise LookupError(f"no file {file_id!r} in case {case_id!r}")
    if row["status"] != "registered" or row["processed_at"] is None:
        raise ReadAgainError("only a file that has been read can have its checks run again")
    if not row["stored_name"] or not (case_files_dir(case_id, root) / row["stored_name"]).is_file():
        raise ReadAgainError("the file's bytes are not held, so its checks cannot run again")
    with transaction(conn):
        jobs.enqueue(conn, case_id=case_id, kind="integrity", payload={"file_id": file_id})
        log_decision(conn, at=now_iso(), actor=user_id, case_id=case_id, action="integrity.recheck_requested",
                     detail=dumps({"file_id": file_id, "was": row["integrity_recommendation"]}))


class RemoveError(ValueError):
    pass


def remove_file(
    conn: sqlite3.Connection, root: Path, *, case_id: str, file_id: str, user_id: str, replacing: bool = False
) -> dict:
    """Take a file off the case, whatever its outcome (registered, in exception, rejected, duplicate).

    The file record stays, marked removed, for the audit trail; it no longer appears on the case.
    Its bytes are deleted when no other file of the case holds them, so its SHA-256 no longer counts
    as received and the same content uploaded again is registered as new, not a duplicate. Its
    documents are taken out of use (superseded), the review items they raised are closed, and the
    duplicate records that pointed at it are removed with it. The case's checks are re-run by the caller.
    `replacing` marks a removal made to put a new upload in the file's place (`replace_file`).
    """
    row = conn.execute("SELECT * FROM files WHERE id = ? AND case_id = ?", (file_id, case_id)).fetchone()
    if row is None or row["status"] == "removed":
        raise LookupError(f"no file {file_id!r} in case {case_id!r}")
    if row["status"] == "registered" and row["processed_at"] is None:
        raise RemoveError("the file is still being read; remove it once it has been read")
    files_dir = case_files_dir(case_id, root)
    with transaction(conn):
        ids = [file_id] + [
            r["id"] for r in conn.execute(
                "SELECT id FROM files WHERE case_id = ? AND duplicate_of = ? AND status = 'duplicate'", (case_id, file_id)
            )
        ]
        marks = ",".join("?" * len(ids))
        doc_ids = [r["id"] for r in conn.execute(f"SELECT id FROM documents WHERE file_id IN ({marks})", ids)]
        conn.execute(f"UPDATE files SET status = 'removed', stored_name = NULL WHERE id IN ({marks})", ids)
        if doc_ids:
            dmarks = ",".join("?" * len(doc_ids))
            conn.execute(f"UPDATE documents SET status = 'superseded' WHERE id IN ({dmarks})", doc_ids)
            field_ids = [r["id"] for r in conn.execute(
                f"SELECT id FROM field_values WHERE document_id IN ({dmarks})", doc_ids)]
        else:
            field_ids = []
        refs = [f"file:{i}" for i in ids] + [f"document:{d}" for d in doc_ids] + [f"field:{f}" for f in field_ids]
        for i in range(0, len(refs), 500):
            chunk = refs[i:i + 500]
            for item in conn.execute(
                f"SELECT id FROM review_items WHERE case_id = ? AND status = 'open' AND ref IN ({','.join('?' * len(chunk))})",
                (case_id, *chunk),
            ).fetchall():
                close_item(conn, item_id=item["id"], decision="waive", reason="File removed", decided_by=user_id)
        log_decision(conn, at=now_iso(), actor=user_id, case_id=case_id,
                     action="file.removed",
                     detail=dumps({"file_id": file_id, "name": row["archive_path"] or row["original_name"],
                                   "sha256": row["sha256"], "was": row["status"], "documents": doc_ids,
                                   "also_removed": ids[1:], "replacing": replacing}))
    stored = row["stored_name"]
    if stored and conn.execute(
        "SELECT 1 FROM files WHERE case_id = ? AND stored_name = ?", (case_id, stored)
    ).fetchone() is None:
        (files_dir / stored).unlink(missing_ok=True)
        for cached in (cases_dir(root) / case_id / "pages").glob(f"{stored}-p*.png"):
            cached.unlink(missing_ok=True)
    return dict(row)


def replace_file(
    conn: sqlite3.Connection,
    root: Path,
    *,
    case_id: str,
    file_id: str,
    user_id: str,
    channel: str,
    parts: list[SpooledPart],
) -> UploadResult:
    """Put a new upload in a file's place: the file is removed first (so the same content sent again
    is read afresh rather than taken as a duplicate), then the upload is registered as any other."""
    try:
        old = remove_file(conn, root, case_id=case_id, file_id=file_id, user_id=user_id, replacing=True)
    except Exception:
        for part in parts:
            part.path.unlink(missing_ok=True)
        raise
    result = register_parts(conn, root, case_id=case_id, user_id=user_id, channel=channel, parts=parts)
    with transaction(conn):
        log_decision(conn, at=now_iso(), actor=user_id, case_id=case_id, action="file.replaced",
                     detail=dumps({"file_id": file_id, "name": old["archive_path"] or old["original_name"],
                                   "by": [f.id for f in result.files], "job_id": result.job_id}))
    return result
