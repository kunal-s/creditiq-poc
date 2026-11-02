"""Where on the page an integrity finding points, once the pages have been read.

The integrity checks run on the file's bytes before anything is read, so they
can say *what* stands out but not *where* it is printed. A recovered figure is
the exception that matters: the earlier value lives only in the bytes, but the
current one is printed on a page, and a reviewer wants to see it there.

After `read`, each piece of evidence that names text to find (`locate`) is
matched against the page's words and given its page and box, in fractions of
the page with the origin at the top left — the shape the document viewer draws.
Evidence that is about the file itself (its revisions, its metadata) names
nothing to find and is left without a place, which is the truth: it is in the
file's records, not printed anywhere.

Evidence that names an object of the file (`object`) — a page a later save
replaced, an image it added — is placed where the page draws it: an image at the
box it is painted in, a page or its content stream as the whole page.

Deterministic; a figure not found is left unplaced, never guessed.
"""

from __future__ import annotations

import io
import re

import pdfplumber
from pdfminer.pdftypes import resolve1

from ..contracts import IntegrityEvidence, IntegrityFinding
from ..pageindex import Page

__all__ = ["locate", "place_objects"]

#: The whole page, for an object that is the page or everything drawn on it.
WHOLE_PAGE = (0.0, 0.0, 1.0, 1.0)

#: The most pages searched for an object's place. A later save that touched a
#: page of a long file is found on the first pages it touched.
MAX_PAGES_SEARCHED = 200

#: Currency marks and spacing a figure may carry on the page but not in the stream.
_NOISE = re.compile(r"[\s₹]|^(?:rs\.?|inr)", re.I)


def _norm(text: str) -> str:
    return _NOISE.sub("", text.strip()).rstrip(".")


def _place(want: str, pages: list[Page]) -> tuple[int, tuple[float, float, float, float]] | None:
    """The first page and box where `want` is printed as one word."""
    target = _norm(want)
    if not target:
        return None
    for page in pages:
        if not (page.width and page.height):
            continue
        for w in page.words:
            if _norm(w.text) == target:
                return page.no, (round(w.x0 / page.width, 4), round(w.y0 / page.height, 4),
                                 round(w.x1 / page.width, 4), round(w.y1 / page.height, 4))
    return None


def locate(found: list[IntegrityFinding], pages: list[Page]) -> list[IntegrityFinding]:
    """The same findings, with each piece of evidence that names printed text placed on its page."""
    out: list[IntegrityFinding] = []
    for f in found:
        if not any(e.locate and e.rect is None for e in f.evidence):
            out.append(f)
            continue
        evidence: list[IntegrityEvidence] = []
        for e in f.evidence:
            spot = _place(e.locate, pages) if e.locate and e.rect is None else None
            evidence.append(e.model_copy(update={"page": spot[0], "rect": spot[1]}) if spot else e)
        out.append(f.model_copy(update={"evidence": evidence}))
    return out


Spot = tuple[int, tuple[float, float, float, float]]


def _ids(value) -> list[int]:
    """Object numbers of a reference, or of each reference in an array."""
    if isinstance(value, list):
        return [n for v in value for n in _ids(v)]
    n = getattr(value, "objid", None)
    return [n] if isinstance(n, int) else []


def _frac(box: tuple[float, float, float, float], w: float, h: float) -> tuple[float, float, float, float]:
    x0, top, x1, bottom = box
    clamp = lambda v: round(min(max(v, 0.0), 1.0), 4)  # noqa: E731
    return clamp(x0 / w), clamp(top / h), clamp(x1 / w), clamp(bottom / h)


def _where_drawn(data: bytes, wanted: set[int]) -> dict[int, Spot]:
    """The first page and box that draws each wanted object."""
    found: dict[int, Spot] = {}
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages[:MAX_PAGES_SEARCHED]:
            if wanted <= found.keys():
                break
            w, h, no = float(page.width), float(page.height), page.page_number
            attrs = page.page_obj.attrs
            # The page itself, and the content streams that draw it.
            for n in [page.page_obj.pageid, *_ids(attrs.get("Contents"))]:
                if n in wanted:
                    found.setdefault(n, (no, WHOLE_PAGE))
            # Images, at the box each is painted in.
            for im in page.images:
                n = getattr(im.get("stream"), "objid", None)
                if n in wanted:
                    found.setdefault(n, (no, _frac((im["x0"], im["top"], im["x1"], im["bottom"]), w, h)))
            # Annotations, at their own rectangle.
            mb = page.mediabox
            for ref in resolve1(attrs.get("Annots")) or []:
                n = getattr(ref, "objid", None)
                if n not in wanted:
                    continue
                rect = resolve1((resolve1(ref) or {}).get("Rect"))
                if rect and len(rect) == 4:
                    x0, y0, x1, y1 = (float(resolve1(v)) for v in rect)
                    found.setdefault(n, (no, _frac((x0 - mb[0], mb[3] - max(y0, y1), x1 - mb[0], mb[3] - min(y0, y1)), w, h)))
            # Anything else the page's resources name (a font, a drawing): the page.
            res = resolve1(attrs.get("Resources")) or {}
            for group in ("XObject", "Font"):
                for ref in (resolve1(res.get(group)) or {}).values():
                    n = getattr(ref, "objid", None)
                    if n in wanted:
                        found.setdefault(n, (no, WHOLE_PAGE))
    return found


def place_objects(found: list[IntegrityFinding], data: bytes) -> list[IntegrityFinding]:
    """The same findings, with each piece of evidence that names an object placed
    where a page draws it. An object no page draws is left unplaced."""
    wanted = {e.object for f in found for e in f.evidence if e.object is not None and e.rect is None}
    if not wanted:
        return found
    try:
        spots = _where_drawn(data, wanted)
    except Exception:  # noqa: BLE001 - placing is a convenience; the finding stands without it
        return found
    out: list[IntegrityFinding] = []
    for f in found:
        evidence = [e.model_copy(update={"page": spots[e.object][0], "rect": spots[e.object][1]})
                    if e.object in spots and e.rect is None else e for e in f.evidence]
        out.append(f.model_copy(update={"evidence": evidence}) if evidence != f.evidence else f)
    return out
