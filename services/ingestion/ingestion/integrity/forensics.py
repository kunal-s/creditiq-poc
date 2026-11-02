"""What the file's own bytes say about its history.

Everything else in the pipeline reasons about the figures a document prints.
This reasons about the bytes that carry them, and it is the only place that can
say something about *when* a change was made rather than merely that a figure
disagrees with another document.

Three facts are available without a cryptographic signature:

  * A PDF saved more than once without being rewritten keeps its earlier
    revisions. Each ends at a ``%%EOF``.
  * The trailer's ``/ID`` is a pair. The first half is fixed when the file is
    created, the second is refreshed on every save. When they differ, the file
    has been written to since it was made.
  * When an object is redefined by a later revision, the superseded definition
    is still in the bytes. If the earlier one carries a different figure in the
    same place, the file states both values and the earlier one can be shown.

None of this is proof of dishonesty. Signing, filling a form and adding an
annotation all append a revision, and so does a bank's own document system.
What a revision does establish is that the file is not the untouched original.

Ported from RBL/fault_detection `backend/src/tamper/pdfforensics.py` (see
PROVENANCE.md). The byte walking, the limits and the padding rule are unchanged.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field

__all__ = ["Revision", "RecoveredValue", "Forensics", "examine"]

#: End-of-file markers. Each one closes a revision.
_EOF = re.compile(rb"%%EOF")

#: The trailer identifier: [<original> <current>].
_ID_PAIR = re.compile(rb"/ID\s*\[\s*<([0-9A-Fa-f]*)>\s*<([0-9A-Fa-f]*)>\s*\]", re.S)

#: An indirect object header: "12 0 obj".
_OBJ = re.compile(rb"(?:^|[\s>])(\d{1,8})\s+(\d{1,5})\s+obj\b")

#: A signature dictionary.
_SIG = re.compile(rb"/Type\s*/Sig\b")

#: A money figure as it appears inside a content stream's text operators.
_MONEY_IN_STREAM = re.compile(rb"\(([^()\\]*\d[\d,]*\.\d{2}[^()\\]*)\)")

#: Object types a page draws. A later revision that replaced one of these
#: changed what a reader sees; one that replaced only, say, /Metadata did not.
_CONTENT_TYPES = (rb"/Type\s*/Page\b", rb"/Type\s*/XObject\b", rb"/Type\s*/Font\b", rb"/Type\s*/Annot\b")
_CONTENT = re.compile(b"|".join(_CONTENT_TYPES))

#: Bytes that carry nothing. Signing tools and file transfers pad a PDF out to a
#: block size with NULs — a genuine incorporation certificate in the PoC set
#: ends in 118 of them. Counted as content, that padding became a phantom extra
#: revision, which is the one thing this module must never say wrongly.
_PADDING = b" \t\r\n\x00\x0b\x0c"

#: How far one stream, and all the streams of one file together, may expand when
#: decompressed. A page's content is kilobytes; a file built to expand without
#: limit must still cost a bounded amount of memory to read.
STREAM_INFLATE_LIMIT = 32 << 20
FILE_INFLATE_LIMIT = 500 << 20

#: The most objects whose earlier definitions are opened, and the most figures
#: recovered. A file with thousands of superseded objects is a database export,
#: not an edited statement, and a reviewer cannot read thousands of findings.
MAX_SUPERSEDED_READ = 400
MAX_RECOVERED = 20


@dataclass(frozen=True, slots=True)
class Revision:
    """One saved state of the file, ending at its own ``%%EOF``."""

    index: int
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class RecoveredValue:
    """A figure an earlier revision printed where the current one differs."""

    object_number: int
    was: str
    now: str


@dataclass(slots=True)
class Forensics:
    total_bytes: int = 0
    revisions: list[Revision] = field(default_factory=list)
    id_original: str | None = None
    id_current: str | None = None
    signature_count: int = 0
    superseded_objects: list[int] = field(default_factory=list)
    recovered: list[RecoveredValue] = field(default_factory=list)
    content_revised: list[int] = field(default_factory=list)
    """Object numbers a later revision replaced that a page draws."""
    streams_over_limit: int = 0

    @property
    def revision_count(self) -> int:
        return len(self.revisions)

    @property
    def unexplained_revisions(self) -> int:
        """Revisions beyond the ones signing accounts for.

        Applying a signature appends a revision — that is how a PDF is signed
        without disturbing the bytes already signed. A file with one signature
        therefore holds two revisions, and counting the second as an anomaly
        would call every properly signed document into question.
        """
        return max(0, self.revision_count - 1 - self.signature_count)

    @property
    def id_changed(self) -> bool | None:
        if self.id_original is None or self.id_current is None:
            return None
        return self.id_original != self.id_current


class _Budget:
    """What is left to decompress, for one file."""

    __slots__ = ("left", "refused")

    def __init__(self, total: int = FILE_INFLATE_LIMIT):
        self.left = total
        self.refused = 0


def _inflate(blob: bytes, budget: _Budget) -> bytes | None:
    """The stream decompressed — or nothing, when it would expand beyond the
    limit for one stream or beyond what is left of the file's. Never more is
    allocated than the limit allows, whatever the stream claims."""
    limit = min(STREAM_INFLATE_LIMIT, budget.left)
    if limit <= 0:
        budget.refused += 1
        return None
    for candidate in (blob, blob.lstrip(b"\r\n")):
        inflater = zlib.decompressobj()
        try:
            out = inflater.decompress(candidate, limit)
        except zlib.error:
            continue
        if inflater.unconsumed_tail:  # it wanted more room than the limit allows
            budget.refused += 1
            return None
        budget.left -= len(out)
        return out
    return None


def _revisions(data: bytes) -> list[Revision]:
    out: list[Revision] = []
    start = 0
    for index, match in enumerate(_EOF.finditer(data)):
        end = match.end()
        out.append(Revision(index=index, start=start, end=end))
        start = end
    if start < len(data) and data[start:].strip(_PADDING):
        # Bytes after the last %%EOF: a truncated save or appended junk. Either
        # way the file does not end where it says it does.
        out.append(Revision(index=len(out), start=start, end=len(data)))
    return out


def _stream_text(data: bytes, at: int, budget: _Budget) -> bytes:
    """The decoded content of the stream belonging to the object at `at`."""
    head_end = data.find(b"stream", at)
    if head_end == -1:
        return b""
    header = data[at:head_end]
    body_start = head_end + len(b"stream")
    if data[body_start:body_start + 2] == b"\r\n":
        body_start += 2
    elif data[body_start:body_start + 1] in (b"\n", b"\r"):
        body_start += 1
    body_end = data.find(b"endstream", body_start)
    if body_end == -1:
        return b""
    body = data[body_start:body_end]
    if b"/FlateDecode" in header:
        return _inflate(body, budget) or b""
    return body


def _objects_by_number(data: bytes) -> dict[int, list[int]]:
    """Every offset at which each object number is defined, in file order."""
    found: dict[int, list[int]] = {}
    for match in _OBJ.finditer(data):
        found.setdefault(int(match.group(1)), []).append(match.start(1))
    return found


def _object_head(data: bytes, at: int) -> bytes:
    """The dictionary of the object at `at`, up to its stream or its end."""
    stop = data.find(b"stream", at)
    end = data.find(b"endobj", at)
    if stop == -1 or (end != -1 and end < stop):
        stop = end
    return data[at:stop if stop != -1 else at + 2048]


def _recover(data: bytes, offsets: dict[int, list[int]], budget: _Budget) -> tuple[list[int], list[RecoveredValue], list[int]]:
    """Figures an earlier definition printed where the latest one differs, and
    which replaced objects a page draws."""
    superseded: list[int] = []
    recovered: list[RecoveredValue] = []
    content: list[int] = []

    for number, positions in sorted(offsets.items()):
        if len(positions) < 2:
            continue
        superseded.append(number)
        if any(_CONTENT.search(_object_head(data, at)) for at in positions):
            content.append(number)
        if len(superseded) > MAX_SUPERSEDED_READ or len(recovered) >= MAX_RECOVERED:
            continue

        current = _MONEY_IN_STREAM.findall(_stream_text(data, positions[-1], budget))
        if not current:
            continue
        for earlier_at in positions[:-1]:
            previous = _MONEY_IN_STREAM.findall(_stream_text(data, earlier_at, budget))
            if not previous or len(previous) != len(current):
                continue
            for was, now in zip(previous, current):
                if was != now and len(recovered) < MAX_RECOVERED:
                    recovered.append(RecoveredValue(number, was.decode("latin-1").strip(), now.decode("latin-1").strip()))
    return superseded, recovered, content


def examine(data: bytes) -> Forensics:
    """Read the file's structure and say what it implies about its history."""
    report = Forensics(total_bytes=len(data))
    report.revisions = _revisions(data)

    ids = _ID_PAIR.findall(data)
    if ids:
        original, current = ids[-1]
        report.id_original = original.decode("ascii").lower() or None
        report.id_current = current.decode("ascii").lower() or None

    report.signature_count = len(_SIG.findall(data))

    budget = _Budget()
    if report.revision_count > 1:
        report.superseded_objects, report.recovered, report.content_revised = _recover(
            data, _objects_by_number(data), budget)
    report.streams_over_limit = budget.refused
    return report
