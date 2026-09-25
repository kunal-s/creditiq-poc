"""Reusable rendering scaffolding for sample-case documents.

Ported from the generic repo's `scripts/docgen/common.py`: `indian_group`,
`inr`, the two-pass `build_document`/`build_auto` mechanism and the style
sheet are genuinely generic and survive unchanged in spirit. What does not
survive: the watermark (deleted outright — plan.md finding 4/reference/05
finding 4 both call the old self-announcing footer and watermark out), the
Southgate `ENTITY`/`DIRECTORS`/`letterhead`, and the "Synthetic Demo
Generator" PDF metadata (finding 5: metadata must be neutral).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, HRFlowable, PageTemplate, Paragraph, Spacer

PAGE_W, PAGE_H = A4

# The one line every generated page carries (plan.md rule 8; reference/05
# section C). No watermark — CLAUDE.md rule 8 also bans anything that could
# read as a security feature, and a diagonal "SPECIMEN" stamp is exactly the
# kind of self-announcing defect finding 4 flags.
FOOTER_TEXT = "Sample case prepared for evaluation. Not an original document; all names and identifiers are fictitious."


def indian_group(n) -> str:
    """Group an integer in the Indian style: 18,42,67,400."""
    neg = n < 0
    s = str(int(abs(n)))
    if len(s) <= 3:
        out = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        out = ",".join(parts) + "," + last3
    return ("-" + out) if neg else out


def inr(n, paise: bool = False) -> str:
    if paise:
        rupees = int(n)
        p = int(round((n - rupees) * 100))
        return "INR " + indian_group(rupees) + f".{p:02d}"
    return "INR " + indian_group(n)


def rs(n) -> str:
    return indian_group(n)


@dataclass
class LocationRegistry:
    """Records where each tracked variable landed while a page is built.
    Reset between the two `build_auto` passes — only the second pass's
    positions (against final, correctly-labelled pages) are kept."""

    entries: list[dict] = field(default_factory=list)

    def reset(self) -> None:
        self.entries.clear()

    def record(self, var_id: str, page: int, x0: float, y0: float, x1: float, y1: float) -> None:
        self.entries.append({"var": var_id, "page": page, "bbox_pt": [x0, y0, x1, y1]})


class TrackedCanvas(canvas.Canvas):
    """Stamps the footer on every page and, if a page-label list was
    supplied, the printed page label — no watermark, neutral metadata set by
    the caller (`build_document`)."""

    page_labels: list[str] | None = None
    location_registry: LocationRegistry | None = None

    def showPage(self):
        self._stamp_footer()
        self._stamp_page_label()
        canvas.Canvas.showPage(self)

    def _stamp_footer(self):
        self.saveState()
        self.setFont("Helvetica-Oblique", 6.5)
        self.setFillColor(colors.HexColor("#666666"))
        self.drawCentredString(PAGE_W / 2.0, 9 * mm, FOOTER_TEXT)
        self.restoreState()

    def _stamp_page_label(self):
        if not self.page_labels:
            return
        idx = self._pageNumber - 1
        if not (0 <= idx < len(self.page_labels)):
            return
        label = self.page_labels[idx]
        if not label:
            return
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#333333"))
        self.drawRightString(PAGE_W - 18 * mm, 9 * mm, label)
        self.restoreState()


def _make_canvas_factory(page_labels: list[str] | None, registry: LocationRegistry | None):
    labels = list(page_labels) if page_labels else None

    class _Bound(TrackedCanvas):
        pass

    _Bound.page_labels = labels
    _Bound.location_registry = registry
    return _Bound


def build_document(
    path: str,
    story: list,
    page_labels: list[str] | None = None,
    registry: LocationRegistry | None = None,
    left=22 * mm,
    right=22 * mm,
    top=24 * mm,
    bottom=20 * mm,
    title: str = "",
    author: str = "",
) -> int:
    """Render a flowable story to `path`. Returns the physical page count.
    PDF metadata is neutral — no product name, no "specimen" (finding 5)."""
    doc = BaseDocTemplate(
        path,
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title=title,
        author=author,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])
    doc.build(story, canvasmaker=_make_canvas_factory(page_labels, registry))
    return doc.page


def build_auto(path: str, story_factory, registry: LocationRegistry | None = None, **kw) -> int:
    """Two-pass build: pass 1 counts pages, pass 2 stamps "Page i of N"
    labels against the final layout. `story_factory` must return a fresh
    story each call — platypus consumes flowables during a build."""
    if registry is not None:
        registry.reset()
    n = build_document(path, story_factory(), registry=None, **kw)
    labels = [f"Page {i + 1} of {n}" for i in range(n)]
    if registry is not None:
        registry.reset()
    return build_document(path, story_factory(), page_labels=labels, registry=registry, **kw)


def styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    S: dict[str, ParagraphStyle] = {}
    S["title"] = ParagraphStyle(
        "s_title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=15, leading=19,
        spaceAfter=4, alignment=TA_CENTER,
    )
    S["subtitle"] = ParagraphStyle(
        "s_subtitle", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=13,
        alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=6,
    )
    S["h1"] = ParagraphStyle(
        "s_h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=12, leading=15,
        spaceBefore=10, spaceAfter=5,
    )
    S["h2"] = ParagraphStyle(
        "s_h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=13,
        spaceBefore=8, spaceAfter=4,
    )
    S["body"] = ParagraphStyle(
        "s_body", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5,
        alignment=TA_JUSTIFY, spaceAfter=5,
    )
    S["body_l"] = ParagraphStyle("s_body_l", parent=S["body"], alignment=TA_LEFT)
    S["small"] = ParagraphStyle(
        "s_small", parent=ss["Normal"], fontName="Helvetica", fontSize=8.2, leading=11,
        textColor=colors.HexColor("#444444"),
    )
    S["center"] = ParagraphStyle("s_center", parent=S["body"], alignment=TA_CENTER)
    S["right"] = ParagraphStyle("s_right", parent=S["body"], alignment=TA_RIGHT)
    S["mono"] = ParagraphStyle("s_mono", parent=ss["Normal"], fontName="Courier", fontSize=8.5, leading=11)
    S["cell"] = ParagraphStyle("s_cell", parent=ss["Normal"], fontName="Helvetica", fontSize=8.6, leading=11)
    S["cell_b"] = ParagraphStyle("s_cell_b", parent=S["cell"], fontName="Helvetica-Bold")
    S["cell_r"] = ParagraphStyle("s_cell_r", parent=S["cell"], alignment=TA_RIGHT)
    S["cell_rb"] = ParagraphStyle("s_cell_rb", parent=S["cell_b"], alignment=TA_RIGHT)
    return S


def letterhead(S: dict[str, ParagraphStyle], entity: dict) -> list:
    """Flowables for an entity's own letterhead. `entity` needs name,
    business, office, and whichever of pan/gstin/cin apply."""
    out = [Paragraph(entity["name"], S["title"])]
    if entity.get("business"):
        out.append(Paragraph(entity["business"], S["subtitle"]))
    reg_parts = [f"Registered Office: {entity['office']}"]
    id_bits = []
    if entity.get("cin"):
        id_bits.append(f"CIN: {entity['cin']}")
    id_bits.append(f"PAN: {entity['pan']}")
    id_bits.append(f"GSTIN: {entity['gstin']}")
    reg_parts.append(" &nbsp;|&nbsp; ".join(id_bits))
    reg = "<br/>".join(reg_parts)
    out.append(Paragraph(reg, ParagraphStyle("lh", parent=S["small"], alignment=TA_CENTER)))
    out.append(Spacer(1, 4))
    out.append(
        HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#20406a"), spaceBefore=2, spaceAfter=8)
    )
    return out
