"""What a PDF page draws, and in what order (F-07A, phase 2).

The phase-1 checks read the file's records. These read the page: every
character with its font, size and box, every filled shape and picture, and the
order they are painted in. A PDF paints later over earlier; that order is what
separates a block pasted over a figure from a cell background drawn beneath one
— the same rectangle, opposite meaning.

On pypdfium2 (BSD-3/Apache-2.0), never PyMuPDF (AGPL). Two coordinate systems
meet here: PDF points, origin bottom-left; and the fractions the screen draws
from, origin top-left. `to_fractions` is the only place the flip happens.

Ported from RBL/fault_detection `backend/src/tamper/pdfdoc.py` (PROVENANCE.md):
`Box`, `_page_bounds`, `_paint_order`, `_hidden_chars`, `_shows_through`,
`covered_text`, `images`, `char_styles`, `text_runs`, `to_fractions`. The
optical reading of pictures is not ported: nothing here reads pixels as text.
"""

from __future__ import annotations

import ctypes
import math
import threading
from dataclasses import dataclass

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

__all__ = ["Box", "Char", "Run", "Covered", "Picture", "PagePicture", "PageDoc", "PICTURE_PAGE_COVERAGE"]

#: pdfium is not thread-safe: two threads in it at once abort the process.
_PDFIUM = threading.RLock()

#: A filled shape hides what is under it only if it is opaque. A translucent
#: highlight leaves the text readable, so it is not a cover.
COVER_MIN_ALPHA = 200

#: A shape the size of most of the page is a background or a scan, not a block
#: placed over one figure.
COVER_MAX_PAGE_FRACTION = 0.25

#: Pictures covering at least this share of the page make it a picture of a page
#: (a scan, a photo, a screenshot), whatever text is drawn with them.
PICTURE_PAGE_COVERAGE = 0.50

#: Below this resolution a picture is a background stretched across the page,
#: not a picture of anything a person reads (fault_detection STRETCHED_IMAGE_DPI).
STRETCHED_IMAGE_DPI = 40.0

#: A picture smaller than this share of the page is a logo, a rule or a dot.
CONTENT_IMAGE_MIN_FRACTION = 0.002

#: One picture covering at least this share of all the content pictures is the
#: page's picture, however little of the sheet it fills (a card on an A4 page).
SOLE_IMAGE_SHARE = 0.8

#: A dark mark drawn over a picture (fault_detection L3.DARK_MARK_ON_PICTURE,
#: chosen on its check1 sample): an opaque, nearly black, bar-shaped fill at
#: least 12 by 4 pt and at most 2% of the page, lying mostly (80%) over a
#: picture painted before it that covers 15% of the page or more, and drawn as a
#: solid block (65% of its pixels dark at twice the page's size), not as dark
#: letters of outlined text.
DARK_MARK_MIN_ALPHA = 240
DARK_MARK_MAX_CHANNEL = 40
DARK_MARK_MIN_W_PT, DARK_MARK_MIN_H_PT, DARK_MARK_MIN_ASPECT = 12.0, 4.0, 2.0
DARK_MARK_MAX_PAGE_FRACTION = 0.02
DARK_MARK_PICTURE_MIN_FRACTION = 0.15
DARK_MARK_INSIDE = 0.8
DARK_MARK_SOLID = 0.65
DARK_MARK_DARK_GREY = 70


@dataclass(frozen=True, slots=True)
class Box:
    """A rectangle in PDF points, origin bottom-left."""

    left: float
    bottom: float
    right: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    def union(self, other: "Box") -> "Box":
        return Box(min(self.left, other.left), min(self.bottom, other.bottom),
                   max(self.right, other.right), max(self.top, other.top))

    def padded(self, pad: float) -> "Box":
        return Box(self.left - pad, self.bottom - pad, self.right + pad, self.top + pad)

    def centre_in(self, other: "Box") -> bool:
        cx, cy = (self.left + self.right) / 2, (self.bottom + self.top) / 2
        return other.left <= cx <= other.right and other.bottom <= cy <= other.top


def union(boxes: list[Box]) -> Box:
    out = boxes[0]
    for b in boxes[1:]:
        out = out.union(b)
    return out


@dataclass(frozen=True, slots=True)
class Char:
    """One character of the text layer, as the page draws it."""

    index: int
    text: str
    box: Box
    font: str
    size: float
    painted: int | None
    """Its place in the order the page is painted; None when unknown."""
    visible: bool
    """False when drawn invisibly — a scanner's OCR layer is."""
    line: Box | None = None
    """The character's loose box: the font's full height on its baseline, the
    same for every glyph of one size, so a comma and a digit share a line."""


@dataclass(frozen=True, slots=True)
class Run:
    """Characters that share a line and do not jump, with their rectangle."""

    text: str
    box: Box
    chars: tuple[Char, ...]


@dataclass(frozen=True, slots=True)
class Covered:
    """Text an opaque shape was painted over, and any text painted on it."""

    cover: Box
    hidden: str
    hidden_box: Box
    shown: str | None
    indices: tuple[int, ...] = ()
    """The hidden characters, by their index in the text layer."""
    by: str = "block"
    """What lies over the text: a block painted on the page, or an annotation."""


@dataclass(frozen=True, slots=True)
class Picture:
    """A picture on the page, and the visible text painted under it."""

    box: Box
    fraction: float
    """How much of the page it covers."""
    under: str | None
    under_box: Box | None
    position: int


@dataclass(frozen=True, slots=True)
class PagePicture:
    """The pixels that stand for a picture page, and where they lie on it."""

    image: object
    """PIL image, RGB."""
    placed: Box
    """The rectangle on the page the image covers, in points."""
    dpi: float
    """The resolution the page's content is drawn at."""
    tiles: int
    """How many pictures make up the page (a scan stored as strips has several)."""
    largest_share: float
    """The share of the page the largest picture covers."""


def _handle(obj) -> int:
    return ctypes.cast(obj, ctypes.c_void_p).value or 0


#: Annotation subtypes that can hide or replace what is printed under them.
_COVERING_ANNOTS = {pdfium_c.FPDF_ANNOT_SQUARE: "box", pdfium_c.FPDF_ANNOT_CIRCLE: "box",
                    pdfium_c.FPDF_ANNOT_FREETEXT: "typed note", pdfium_c.FPDF_ANNOT_STAMP: "stamp",
                    pdfium_c.FPDF_ANNOT_INK: "drawing", pdfium_c.FPDF_ANNOT_REDACT: "box"}


def _annotations(page) -> list[tuple[str, Box, bool, str]]:
    """(kind, rectangle, filled, its text) for each annotation that can cover text."""
    out = []
    for i in range(max(pdfium_c.FPDFPage_GetAnnotCount(page.raw), 0)):
        annot = pdfium_c.FPDFPage_GetAnnot(page.raw, i)
        if not annot:
            continue
        try:
            kind = _COVERING_ANNOTS.get(pdfium_c.FPDFAnnot_GetSubtype(annot))
            if kind is None:
                continue
            rect = pdfium_c.FS_RECTF()
            if not pdfium_c.FPDFAnnot_GetRect(annot, ctypes.byref(rect)):
                continue
            box = Box(min(rect.left, rect.right), min(rect.bottom, rect.top),
                      max(rect.left, rect.right), max(rect.bottom, rect.top))
            r, g, b, a = (ctypes.c_uint(0) for _ in range(4))
            filled = kind in ("stamp",) or bool(pdfium_c.FPDFAnnot_GetColor(
                annot, pdfium_c.FPDFANNOT_COLORTYPE_InteriorColor,
                ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a)))
            out.append((kind, box, filled, _annot_text(annot)))
        finally:
            pdfium_c.FPDFPage_CloseAnnot(annot)
    return out


def _annot_text(annot) -> str:
    """An annotation's /Contents, as written."""
    n = pdfium_c.FPDFAnnot_GetStringValue(annot, b"Contents", None, 0)
    if n <= 2:
        return ""
    buf = ctypes.create_string_buffer(n)
    pdfium_c.FPDFAnnot_GetStringValue(annot, b"Contents", ctypes.cast(buf, ctypes.POINTER(pdfium_c.FPDF_WCHAR)), n)
    return buf.raw[: n - 2].decode("utf-16-le", "replace").strip()


def _clip_bounds(obj) -> tuple[float, float, float, float] | None:
    """The rectangle round an object's clip path, in its own space."""
    try:
        clip = pdfium_c.FPDFPageObj_GetClipPath(obj.raw)
    except Exception:  # noqa: BLE001
        return None
    if not clip:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for path in range(max(pdfium_c.FPDFClipPath_CountPaths(clip), 0)):
        for segment in range(max(pdfium_c.FPDFClipPath_CountPathSegments(clip, path), 0)):
            handle = pdfium_c.FPDFClipPath_GetPathSegment(clip, path, segment)
            if not handle:
                continue
            x, y = ctypes.c_float(0), ctypes.c_float(0)
            if pdfium_c.FPDFPathSegment_GetPoint(handle, ctypes.byref(x), ctypes.byref(y)):
                xs.append(x.value)
                ys.append(y.value)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _page_bounds(obj) -> Box | None:
    """An object's rectangle on the page. Inside a form, each form's matrix
    carries it out to the page; a picture drawn through a clip shows only what
    the clip lets through."""
    try:
        left, bottom, right, top = obj.get_bounds()
    except Exception:  # noqa: BLE001
        return None
    clip = _clip_bounds(obj) if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE else None
    if clip is not None:
        left, bottom = max(left, clip[0]), max(bottom, clip[1])
        right, top = min(right, clip[2]), min(top, clip[3])
        if right <= left or top <= bottom:
            return None
    corners = [(left, bottom), (left, top), (right, bottom), (right, top)]
    container = getattr(obj, "container", None)
    while container is not None:
        try:
            matrix = container.get_matrix()
        except Exception:  # noqa: BLE001
            break
        corners = [matrix.on_point(x, y) for x, y in corners]
        container = getattr(container, "container", None)
    xs = [x for x, _ in corners]
    ys = [y for _, y in corners]
    return Box(min(xs), min(ys), max(xs), max(ys))


def _overlap(a: Box, b: Box) -> float:
    """The area two rectangles share."""
    return max(0.0, min(a.right, b.right) - max(a.left, b.left)) * max(0.0, min(a.top, b.top) - max(a.bottom, b.bottom))


class _Page:
    """One page read once: its characters, shapes and pictures in paint order."""

    def __init__(self, page):
        self.page = page
        self.width, self.height = page.get_size()
        self.covers: list[tuple[int, Box]] = []
        self.dark: list[tuple[int, Box]] = []
        """Opaque near-black bars, in paint order: candidates for a dark mark over a picture."""
        self.pictures: list[tuple[int, Box, float]] = []
        self.chars: list[Char] = []
        self._covered: list[Covered] | None = None
        area = max(self.width * self.height, 1.0)
        order: dict[int, int] = {}
        for position, obj in enumerate(page.get_objects(max_depth=4)):
            order[_handle(obj.raw)] = position
            if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:
                box = _page_bounds(obj)
                if box is not None and box.width * box.height > 0:
                    self.pictures.append((position, box, abs(box.width * box.height) / area))
                continue
            if obj.type != pdfium_c.FPDF_PAGEOBJ_PATH:
                continue
            fill, stroke = ctypes.c_int(0), ctypes.c_int(0)
            if not pdfium_c.FPDFPath_GetDrawMode(obj.raw, ctypes.byref(fill), ctypes.byref(stroke)) or not fill.value:
                continue
            r, g, b, a = (ctypes.c_uint(0) for _ in range(4))
            if not pdfium_c.FPDFPageObj_GetFillColor(obj.raw, ctypes.byref(r), ctypes.byref(g),
                                                    ctypes.byref(b), ctypes.byref(a)):
                continue
            if a.value < COVER_MIN_ALPHA:
                continue
            box = _page_bounds(obj)
            if box is None or box.width * box.height <= 0 or box.width * box.height / area > COVER_MAX_PAGE_FRACTION:
                continue
            self.covers.append((position, box))
            if (a.value >= DARK_MARK_MIN_ALPHA and max(r.value, g.value, b.value) <= DARK_MARK_MAX_CHANNEL
                    and box.width >= DARK_MARK_MIN_W_PT and box.height >= DARK_MARK_MIN_H_PT
                    and box.width / box.height >= DARK_MARK_MIN_ASPECT
                    and box.width * box.height / area <= DARK_MARK_MAX_PAGE_FRACTION):
                self.dark.append((position, box))

        self.annotations = _annotations(page)

        textpage = page.get_textpage()
        try:
            buf = ctypes.create_string_buffer(256)
            flags = ctypes.c_int(0)
            for i in range(textpage.count_chars()):
                ch = textpage.get_text_range(i, 1)
                if not ch or ch in "\r\n":
                    continue
                try:
                    box = Box(*textpage.get_charbox(i))
                except Exception:  # noqa: BLE001
                    continue
                pdfium_c.FPDFText_GetFontInfo(textpage, i, buf, 256, ctypes.byref(flags))
                # The size a reader sees: the nominal size scaled by the
                # character's matrix (some writers set 327.68 pt and scale it down).
                matrix = pdfium_c.FS_MATRIX()
                scale = 1.0
                if pdfium_c.FPDFText_GetMatrix(textpage, i, ctypes.byref(matrix)):
                    scale = math.hypot(matrix.c, matrix.d) or 1.0
                obj = pdfium_c.FPDFText_GetTextObject(textpage, i)
                painted = order.get(_handle(obj)) if obj else None
                visible = True
                if obj:
                    mode = pdfium_c.FPDFTextObj_GetTextRenderMode(obj)
                    visible = mode not in (pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE, pdfium_c.FPDF_TEXTRENDERMODE_CLIP)
                try:
                    line = Box(*textpage.get_charbox(i, loose=True))
                except Exception:  # noqa: BLE001
                    line = None
                self.chars.append(Char(i, ch, box, buf.value.decode("latin-1", "replace"),
                                       round(pdfium_c.FPDFText_GetFontSize(textpage, i) * scale, 2),
                                       painted, visible, line))
        finally:
            textpage.close()

    # --- what is drawn over what ------------------------------------------

    def _beneath(self, position: int, cover: Box) -> list[Char]:
        return [c for c in self.chars if c.visible and c.painted is not None and c.painted < position
                and c.text.strip() and c.box.centre_in(cover)]

    def _on_top(self, position: int, cover: Box) -> list[Char]:
        return [c for c in self.chars if c.visible and c.painted is not None and c.painted > position
                and c.box.centre_in(cover)]

    def _shows_through(self, boxes: list[Box]) -> bool:
        """Whether text painted under a shape can still be seen through it.

        A fill drawn after the text in a blend mode such as multiply — a
        highlight, a flattened annotation, some templates' shading — leaves the
        text readable; an opaque block leaves a flat colour. The spot is drawn
        and looked at: ink there, standing out from the fill, means it shows.
        """
        region = union(boxes).padded(0.5)
        left, bottom, right, top = self.page.get_bbox()
        crop = (max(region.left - left, 0.0), max(region.bottom - bottom, 0.0),
                max(right - region.right, 0.0), max(top - region.top, 0.0))
        try:
            image = self.page.render(scale=2.0, draw_annots=True, may_draw_forms=True, crop=crop).to_pil().convert("L")
        except Exception:  # noqa: BLE001
            return False
        histogram = image.histogram()
        total = max(sum(histogram), 1)
        mean = sum(i * n for i, n in enumerate(histogram)) / total
        spread = (sum(n * (i - mean) ** 2 for i, n in enumerate(histogram)) / total) ** 0.5
        dark = sum(histogram[: max(int(mean) - 80, 0)]) / total
        return spread > 25 and 0.02 < dark < 0.6

    def covered(self) -> list[Covered]:
        """Text an opaque shape was painted over. A shape with nothing under
        it is a box on the page; one the text shows through is shading."""
        if self._covered is None:
            self._covered = self._find_covered()
        return self._covered

    def _find_covered(self) -> list[Covered]:
        out: list[Covered] = []
        for position, cover in self.covers:
            under = self._beneath(position, cover)
            if not under:
                continue
            on_top = {c.painted for c in self._on_top(position, cover)}
            # What is printed on top is read whole: a longer figure than the one
            # it replaces runs out past the box.
            over = [c for c in self.chars if c.visible and c.painted in on_top]
            shown = "".join(c.text for c in over).strip() or None
            pictures = [b for p, b, _ in self.pictures if p > position and b.centre_in(cover.padded(1))]
            exposed = [c.box for c in under if not any(c.box.centre_in(p) for p in pictures)]
            if shown is None and (not pictures or exposed) and self._shows_through(exposed or [c.box for c in under]):
                continue
            out.append(Covered(cover, "".join(c.text for c in under).strip(), union([c.box for c in under]), shown,
                               tuple(c.index for c in under)))
        return out

    def annotations_over_text(self) -> list[Covered]:
        """Annotations laid over printed text that hide it or write over it: a
        filled box, or a typed note. A comment, a highlight or an outline drawn
        round a figure leaves the figure readable and is not counted. An
        annotation lies over the page whatever was painted, so every visible
        character under it counts."""
        out: list[Covered] = []
        for kind, box, filled, contents in self.annotations:
            if not (kind == "typed note" or filled):
                continue
            under = [c for c in self.chars if c.visible and c.text.strip() and c.box.centre_in(box)]
            if not under:
                continue
            out.append(Covered(box, "".join(c.text for c in under).strip(), union([c.box for c in under]),
                               contents or None, tuple(c.index for c in under), kind))
        return out

    def pictures_over_text(self) -> list[Picture]:
        """Every picture painted after visible text that lies under it."""
        out: list[Picture] = []
        for position, box, fraction in self.pictures:
            under = self._beneath(position, box)
            text = "".join(c.text for c in under).strip() or None
            out.append(Picture(box, round(fraction, 5), text, union([c.box for c in under]) if under else None,
                               position))
        return out

    def hidden_chars(self) -> set[int]:
        """Characters an opaque shape covers, so they are not read as shown."""
        return {i for c in [*self.covered(), *self.annotations_over_text()] for i in c.indices}

    def shown_chars(self) -> list[Char]:
        """Every character a person can see: drawn visibly, not under a block."""
        hidden = self.hidden_chars()
        return [c for c in self.chars if c.visible and c.index not in hidden]

    def runs(self, chars: list[Char], line_tolerance: float = 2.0) -> list[Run]:
        """Characters grouped into runs while they share a baseline and do not
        jump horizontally — enough to recover a cell without a layout engine."""
        runs: list[Run] = []
        buf: list[Char] = []
        for c in sorted(chars, key=lambda c: c.index):
            if not c.text.strip():
                if buf:
                    runs.append(_run(buf))
                buf = []
                continue
            if buf:
                last = buf[-1]
                # The loose boxes, where pdfium gives them: tight glyph boxes of a
                # comma and a digit differ by more than the tolerance at 12 pt.
                loose = c.line and buf[0].line and last.line
                here, first, prev = (c.line, buf[0].line, last.line) if loose else (c.box, buf[0].box, last.box)
                same_line = abs(here.bottom - first.bottom) <= line_tolerance
                adjacent = (here.left - prev.right) < max(here.height, 4.0)
                if not (same_line and adjacent):
                    runs.append(_run(buf))
                    buf = []
            buf.append(c)
        if buf:
            runs.append(_run(buf))
        return [r for r in runs if r.text.strip()]


def _run(chars: list[Char]) -> Run:
    return Run("".join(c.text for c in chars), union([c.box for c in chars]), tuple(chars))


class PageDoc:
    """A PDF opened for its pages, read one page at a time and closed after."""

    def __init__(self, data: bytes):
        self._data = data
        self._geometry: dict[int, tuple] = {}
        """Each page's box, rotation and size, read once: loading a page from
        pdfium for every rectangle mapped cost seconds a page."""

    def __enter__(self) -> "PageDoc":
        _PDFIUM.acquire()
        try:
            self._doc = pdfium.PdfDocument(self._data)
        except Exception:
            _PDFIUM.release()
            raise
        return self

    def __exit__(self, *exc) -> None:
        try:
            self._doc.close()
        finally:
            _PDFIUM.release()

    def __len__(self) -> int:
        return len(self._doc)

    def page(self, index: int) -> _Page:
        return _Page(self._doc[index])

    def pictures(self, index: int) -> list[tuple[Box, float, float]]:
        """Every picture on the page as (rectangle, share of the page, resolution in dpi)."""
        page = self._doc[index]
        w, h = page.get_size()
        area = max(w * h, 1.0)
        out = []
        for obj in page.get_objects(max_depth=4):
            if obj.type != pdfium_c.FPDF_PAGEOBJ_IMAGE:
                continue
            box = _page_bounds(obj)
            if box is None or box.width <= 0 or box.height <= 0:
                continue
            try:
                px_w, _px_h = obj.get_px_size()
            except Exception:  # noqa: BLE001
                continue
            out.append((box, abs(box.width * box.height) / area, px_w / max(box.width / 72.0, 1e-6)))
        return out

    def dark_marks(self, index: int, page: "_Page | None" = None) -> list[Box]:
        """Solid dark marks drawn over a picture on the page, each the largest of
        the shapes that make it up (fault_detection DarkMarkOnPicture)."""
        page = page or self.page(index)
        big = [(pos, box) for pos, box, frac in page.pictures if frac >= DARK_MARK_PICTURE_MIN_FRACTION]
        found: list[Box] = []
        rendered = None
        for pos, box in page.dark:
            if not any(earlier < pos and _overlap(box, pic) >= box.width * box.height * DARK_MARK_INSIDE
                       for earlier, pic in big):
                continue
            if rendered is None:
                rendered = (self._doc[index].render(scale=2.0, draw_annots=False).to_pil().convert("L"),
                            self._doc[index].get_bbox())
            image, (left, bottom, _right, top) = rendered
            crop = image.crop((round((box.left - left) * 2), round((top - box.top) * 2),
                               round((box.right - left) * 2), round((top - box.bottom) * 2)))
            if not crop.width or not crop.height:
                continue
            if sum(crop.histogram()[:DARK_MARK_DARK_GREY]) / (crop.width * crop.height) < DARK_MARK_SOLID:
                continue
            # Nested shapes belonging to one mark share the larger rectangle.
            same = next((f for f in found if _overlap(box, f) >= min(box.width * box.height, f.width * f.height) * 0.7),
                        None)
            if same is not None:
                if same.width * same.height >= box.width * box.height:
                    continue
                found.remove(same)
            found.append(box)
        return found

    def picture_share(self, index: int) -> float:
        """How much of the page its pictures cover, together (overlaps counted once
        only roughly: the sum, capped at the page)."""
        return min(1.0, sum(f for _, f, _ in self.pictures(index)))

    def page_picture(self, index: int, max_dpi: float = 300.0) -> PagePicture | None:
        """The pixels that stand for a picture page, for measuring how it was made.

        One picture carrying the page (a scan filling it, or a card laid on a
        sheet) is drawn at its own resolution and measured alone. A page stored
        as strips, or with no single picture carrying it, is drawn at the
        resolution most of its content is drawn at, over the area its content
        pictures cover together. None when the page has no readable picture.
        """
        pictures = self.pictures(index)
        kept = [p for p in pictures if p[1] >= CONTENT_IMAGE_MIN_FRACTION and p[2] >= STRETCHED_IMAGE_DPI]
        if not kept:
            return None
        largest = max(kept, key=lambda p: p[1])
        covered = sum(p[1] for p in kept)
        if largest[1] >= PICTURE_PAGE_COVERAGE or largest[1] >= SOLE_IMAGE_SHARE * covered:
            extent, dpi = largest[0], largest[2]
        else:
            # The resolution most of the content is drawn at: the median, weighted by coverage.
            run, dpi = 0.0, sorted(p[2] for p in kept)[-1]
            for d, f in sorted((p[2], p[1]) for p in kept):
                run += f
                if run >= covered / 2:
                    dpi = d
                    break
            extent = union([p[0] for p in kept])
        page = self._doc[index]
        left, bottom, right, top = page.get_bbox()
        extent = Box(max(extent.left, left), max(extent.bottom, bottom), min(extent.right, right), min(extent.top, top))
        if extent.width <= 0 or extent.height <= 0:
            return None
        dpi = min(dpi, max_dpi)
        crop = (extent.left - left, extent.bottom - bottom, right - extent.right, top - extent.top)
        image = page.render(scale=dpi / 72.0, crop=crop, draw_annots=False).to_pil().convert("RGB")
        return PagePicture(image, extent, round(dpi, 1), len(kept), round(largest[1], 4))

    def to_fractions(self, index: int, box: Box) -> tuple[float, float, float, float]:
        """The rectangle as fractions of the page as it is shown, origin top-left,
        with the page's rotation applied."""
        if index not in self._geometry:
            page = self._doc[index]
            self._geometry[index] = (page.get_bbox(), page.get_rotation() % 360, page.get_size())
        (left, bottom, right, top), rotation, (w, h) = self._geometry[index]
        xs: list[float] = []
        ys: list[float] = []
        for x, y in ((box.left, box.bottom), (box.left, box.top), (box.right, box.bottom), (box.right, box.top)):
            if rotation == 90:
                px, py = (y - bottom) / w, (x - left) / h
            elif rotation == 180:
                px, py = (right - x) / w, (y - bottom) / h
            elif rotation == 270:
                px, py = (top - y) / w, (right - x) / h
            else:
                px, py = (x - left) / w, (top - y) / h
            xs.append(px)
            ys.append(py)
        return (round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4))
