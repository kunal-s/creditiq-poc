"""What the file says about itself, kept for a reader (F-07A).

The integrity checks read the file's own records — its information dictionary,
its XMP packet, its identifier pair, its revisions — and answer from them. This
keeps those records, as read, so a reader can see what each answer rests on
rather than take a verdict on trust. Nothing here is judged; it is the evidence.
"""

from __future__ import annotations

import re

from ..contracts import IntegrityFacts, IntegrityObject, IntegrityRecovered, IntegrityRevision
from .forensics import Forensics
from .meta import FileMeta, _iso

__all__ = ["file_facts"]

_HEADER = re.compile(rb"%PDF-([12]\.\d)")


def file_facts(data: bytes, meta: FileMeta, f: Forensics) -> IntegrityFacts:
    header = _HEADER.search(data[:4096])
    return IntegrityFacts(
        size_bytes=len(data),
        pdf_version=header[1].decode() if header else None,
        header_offset=header.start() if header else 0,
        pages=meta.pages,
        page_sizes=meta.page_sizes,
        info=dict(meta.info),
        info_dates={k: iso for k in ("CreationDate", "ModDate") if (iso := _iso(meta.info.get(k)))},
        has_xmp=meta.has_xmp,
        xmp=dict(meta.xmp),
        id_original=f.id_original,
        id_current=f.id_current,
        revisions=[IntegrityRevision(index=r.index, start=r.start, end=r.end, length=r.length,
                                     replaced=[IntegrityObject(number=o.number, kind=o.kind) for o in r.replaced],
                                     added=[IntegrityObject(number=o.number, kind=o.kind) for o in r.added],
                                     replaced_count=r.replaced_count, added_count=r.added_count)
                   for r in f.revisions],
        signatures=f.signature_count,
        superseded_objects=len(f.superseded_objects),
        recovered=[IntegrityRecovered(object_number=r.object_number, was=r.was, now=r.now) for r in f.recovered],
        fonts=list(f.fonts),
    )
