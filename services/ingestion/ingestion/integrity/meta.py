"""What the file says about itself: its information dictionary and its XMP.

A PDF keeps two records of its own provenance and they are written separately:
the information dictionary (``/Info``: Producer, Creator, CreationDate,
ModDate) and an XMP packet in ``/Metadata``. A program that saves a file is
expected to update both. When they disagree, one of them was written by
something that did not know about the other.

Both records are self-reported and trivially edited, so nothing here is proof
of anything. Dates in an impossible order, or two records that disagree, are a
reason to look.

The information dictionary is read with pypdfium2, which the pipeline already
uses. The XMP packet is found in the bytes and parsed with the standard
library: a second, independent reading, and no new dependency.

Ported from RBL/fault_detection `backend/src/tamper/filemeta.py` (PROVENANCE.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import pypdfium2 as pdfium

__all__ = ["FileMeta", "read_meta", "DATE_SLACK"]

#: Info and XMP timestamps further apart than this disagree. Two programs
#: writing the same save a second apart is ordinary; two minutes is not.
DATE_SLACK = timedelta(minutes=2)

#: An XMP packet larger than this is not read: metadata is kilobytes, and an
#: untrusted file can declare anything.
XMP_MAX_BYTES = 1 << 20

#: The packet, found in the bytes. Bounded so a file cannot make the search cost
#: without limit.
_XMP = re.compile(rb"<x:xmpmeta[\s\S]{0,%d}?</x:xmpmeta>" % XMP_MAX_BYTES)

_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "pdf": "http://ns.adobe.com/pdf/1.3/",
}

#: "D:20261007074141Z", "D:20251225103000+05'30'", or the same without the D:.
_PDF_DATE = re.compile(
    r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(?:([Zz+-])(\d{2})'?(\d{2})?'?)?")


def _iso(value: str | None) -> str | None:
    """A PDF or XMP timestamp as ISO-8601, or None when it does not parse.

    A date that does not parse keeps its raw text elsewhere and says so here;
    it never becomes a default, because a default would be read as a fact.
    """
    if not value:
        return None
    text = str(value).strip()
    try:  # XMP writes ISO-8601 already
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    m = _PDF_DATE.match(text)
    if not m:
        return None
    y, mo, d, h, mi, s, sign, oh, om = m.groups()
    try:
        when = datetime(int(y), int(mo or 1), int(d or 1), int(h or 0), int(mi or 0), int(s or 0))
    except ValueError:
        return None
    if sign in ("+", "-"):
        offset = timedelta(hours=int(oh or 0), minutes=int(om or 0))
        when = when.replace(tzinfo=timezone(-offset if sign == "-" else offset))
    elif sign in ("Z", "z"):
        when = when.replace(tzinfo=timezone.utc)
    return when.isoformat()


def _moment(iso: str | None) -> datetime | None:
    """An ISO timestamp as a comparable moment, naive times read as UTC."""
    if not iso:
        return None
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


@dataclass(slots=True)
class FileMeta:
    """Both records, as the file holds them."""

    info: dict[str, str] = field(default_factory=dict)
    xmp: dict[str, str] = field(default_factory=dict)
    has_xmp: bool = False
    unreadable: str | None = None
    """Why nothing could be read, when nothing could."""

    # --- what the records say, preferring the information dictionary ---
    @property
    def producer(self) -> str:
        return self.info.get("Producer") or self.xmp.get("producer") or ""

    @property
    def creator(self) -> str:
        return self.info.get("Creator") or self.xmp.get("creator_tool") or ""

    @property
    def created(self) -> str | None:
        return _iso(self.info.get("CreationDate")) or _iso(self.xmp.get("create_date"))

    @property
    def modified(self) -> str | None:
        return _iso(self.info.get("ModDate")) or _iso(self.xmp.get("modify_date"))

    def created_at(self) -> datetime | None:
        return _moment(self.created)

    def modified_at(self) -> datetime | None:
        return _moment(self.modified)

    def disagreements(self) -> list[str]:
        """Where the information dictionary and XMP state different things."""
        out: list[str] = []
        for word, a, b in (("the producer", self.info.get("Producer"), self.xmp.get("producer")),
                           ("the creating program", self.info.get("Creator"), self.xmp.get("creator_tool"))):
            if a and b and a.strip() != b.strip():
                out.append(f"{word}: “{a.strip()}” in the information dictionary against “{b.strip()}” in XMP")
        for word, a, b in (("the created date", self.info.get("CreationDate"), self.xmp.get("create_date")),
                           ("the modified date", self.info.get("ModDate"), self.xmp.get("modify_date"))):
            one, two = _moment(_iso(a)), _moment(_iso(b))
            if one and two and abs(one - two) > DATE_SLACK:
                out.append(f"{word}: {one.isoformat()} in the information dictionary against {two.isoformat()} in XMP")
        return out


def _read_xmp(data: bytes) -> tuple[dict[str, str], bool]:
    found = _XMP.search(data)
    if not found:
        return {}, False
    try:
        root = ElementTree.fromstring(found.group(0))
    except ElementTree.ParseError:
        return {}, True
    out: dict[str, str] = {}
    for key, path in (("producer", "pdf:Producer"), ("creator_tool", "xmp:CreatorTool"),
                      ("create_date", "xmp:CreateDate"), ("modify_date", "xmp:ModifyDate"),
                      ("metadata_date", "xmp:MetadataDate")):
        node = root.find(f".//{path}", _NS)
        if node is not None:
            text = "".join(node.itertext()).strip()
            if text:
                out[key] = text
        else:  # some writers put the property in the rdf:Description attributes
            for desc in root.findall(".//rdf:Description", _NS):
                ns, _, local = path.partition(":")
                value = desc.get("{%s}%s" % (_NS[ns], local))
                if value:
                    out[key] = value.strip()
                    break
    return out, True


def read_meta(data: bytes) -> FileMeta:
    """Both of the file's records of itself."""
    meta = FileMeta()
    try:
        doc = pdfium.PdfDocument(data)
    except Exception as e:  # noqa: BLE001 - an unreadable file says so, never a default
        meta.unreadable = f"{type(e).__name__}: {e}"
        return meta
    try:
        for key in ("Title", "Author", "Subject", "Keywords", "Creator", "Producer", "CreationDate", "ModDate"):
            try:
                value = doc.get_metadata_value(key)
            except Exception:  # noqa: BLE001, PERF203 - one absent key is not a failure
                continue
            if value:
                meta.info[key] = str(value).strip()
    finally:
        doc.close()
    meta.xmp, meta.has_xmp = _read_xmp(data)
    return meta
