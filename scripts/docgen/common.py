"""
Shared helpers for generating the Southgate Textiles synthetic specimen document set.

Every page produced through here carries:
  * a light diagonal SPECIMEN watermark, and
  * the mandatory synthetic-document footer notice.

Nothing in this set is real. All identifiers are fictional.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    NextPageTemplate, PageBreak, KeepTogether, HRFlowable, FrameBreak,
)
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4

WATERMARK_TEXT = "SPECIMEN - SYNTHETIC DEMO DOCUMENT - NOT A REAL INSTRUMENT"
FOOTER_TEXT = ("Synthetic specimen generated for demonstration. Not a real document. "
               "All identifiers are fictional.")


# --------------------------------------------------------------------------- #
# Indian-convention number formatting
# --------------------------------------------------------------------------- #
def indian_group(n):
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


def inr(n, paise=False):
    """Return an 'INR 18,42,67,400' style string."""
    if paise:
        rupees = int(n)
        p = int(round((n - rupees) * 100))
        return "INR " + indian_group(rupees) + ".{:02d}".format(p)
    return "INR " + indian_group(n)


def rs(n):
    """Rupee-symbol-free plain grouped number, e.g. for table cells."""
    return indian_group(n)


# --------------------------------------------------------------------------- #
# Watermark + footer canvas
# --------------------------------------------------------------------------- #
class SpecimenCanvas(canvas.Canvas):
    """
    Canvas that stamps the diagonal SPECIMEN watermark and the synthetic-document
    footer on every physical page.

    An optional list of page labels (e.g. "Page 1 of 7") may be supplied; the
    label for physical page i is drawn at bottom-right. This is how documents
    whose page numbering deliberately skips are produced -- the numbering is a
    property of the printed label, independent of the physical page count.
    """

    page_labels = None  # set via factory

    def showPage(self):
        self._stamp()
        canvas.Canvas.showPage(self)

    def save(self):
        canvas.Canvas.save(self)

    def _stamp(self):
        self._draw_watermark()
        self._draw_footer()
        self._draw_page_label()

    def _draw_watermark(self):
        # A single, light, medium-weight diagonal watermark across the page --
        # present and legible, but not so heavy it obscures the content.
        self.saveState()
        self.setFont("Helvetica", 20)
        try:
            self.setFillAlpha(0.12)
        except Exception:
            pass
        self.setFillColor(colors.HexColor("#9a9a9a"))
        self.translate(PAGE_W / 2.0, PAGE_H / 2.0)
        self.rotate(54.5)  # run corner-to-corner on A4
        self.drawCentredString(0, -7, WATERMARK_TEXT)
        self.restoreState()

    def _draw_footer(self):
        self.saveState()
        self.setFont("Helvetica-Oblique", 6.7)
        self.setFillColor(colors.HexColor("#666666"))
        self.drawCentredString(PAGE_W / 2.0, 9 * mm, FOOTER_TEXT)
        self.restoreState()

    def _draw_page_label(self):
        if not self.page_labels:
            return
        idx = self._pageNumber - 1
        if idx < 0 or idx >= len(self.page_labels):
            return
        label = self.page_labels[idx]
        if not label:
            return
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#333333"))
        self.drawRightString(PAGE_W - 18 * mm, 9 * mm, label)
        self.restoreState()


def make_canvas_factory(page_labels=None):
    """Return a Canvas subclass bound to a specific list of page labels."""
    labels = list(page_labels) if page_labels else None

    class _Bound(SpecimenCanvas):
        pass

    _Bound.page_labels = labels
    return _Bound


# --------------------------------------------------------------------------- #
# Document scaffolding
# --------------------------------------------------------------------------- #
def build_document(path, story, page_labels=None,
                   left=22 * mm, right=22 * mm, top=24 * mm, bottom=20 * mm,
                   title="Synthetic Specimen"):
    """Render a flowable story to `path` with watermark + footer on every page."""
    doc = BaseDocTemplate(
        path, pagesize=A4,
        leftMargin=left, rightMargin=right, topMargin=top, bottomMargin=bottom,
        title=title, author="Synthetic Demo Generator",
        subject="SPECIMEN - SYNTHETIC DEMO DOCUMENT - NOT A REAL INSTRUMENT",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])
    doc.build(story, canvasmaker=make_canvas_factory(page_labels))
    return doc.page


def build_auto(path, story_factory, title="Synthetic Specimen", **kw):
    """
    Build twice: first pass counts pages, second pass stamps 'Page i of N' labels.
    `story_factory` must be a zero-arg callable returning a *fresh* story list,
    because platypus consumes flowables during a build.
    """
    n = build_document(path, story_factory(), title=title, **kw)
    labels = ["Page %d of %d" % (i + 1, n) for i in range(n)]
    return build_document(path, story_factory(), page_labels=labels, title=title, **kw)


# --------------------------------------------------------------------------- #
# Style sheet
# --------------------------------------------------------------------------- #
def styles():
    ss = getSampleStyleSheet()
    S = {}
    S["title"] = ParagraphStyle("s_title", parent=ss["Title"], fontName="Helvetica-Bold",
                                fontSize=15, leading=19, spaceAfter=4, alignment=TA_CENTER)
    S["subtitle"] = ParagraphStyle("s_subtitle", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=10, leading=13, alignment=TA_CENTER,
                                   textColor=colors.HexColor("#333333"), spaceAfter=6)
    S["h1"] = ParagraphStyle("s_h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                             fontSize=12, leading=15, spaceBefore=10, spaceAfter=5)
    S["h2"] = ParagraphStyle("s_h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                             fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=4)
    S["body"] = ParagraphStyle("s_body", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY, spaceAfter=5)
    S["body_l"] = ParagraphStyle("s_body_l", parent=S["body"], alignment=TA_LEFT)
    S["small"] = ParagraphStyle("s_small", parent=ss["Normal"], fontName="Helvetica",
                                fontSize=8.2, leading=11, textColor=colors.HexColor("#444444"))
    S["center"] = ParagraphStyle("s_center", parent=S["body"], alignment=TA_CENTER)
    S["right"] = ParagraphStyle("s_right", parent=S["body"], alignment=TA_RIGHT)
    S["mono"] = ParagraphStyle("s_mono", parent=ss["Normal"], fontName="Courier",
                               fontSize=8.5, leading=11)
    S["cell"] = ParagraphStyle("s_cell", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=8.6, leading=11)
    S["cell_b"] = ParagraphStyle("s_cell_b", parent=S["cell"], fontName="Helvetica-Bold")
    S["cell_r"] = ParagraphStyle("s_cell_r", parent=S["cell"], alignment=TA_RIGHT)
    S["cell_rb"] = ParagraphStyle("s_cell_rb", parent=S["cell_b"], alignment=TA_RIGHT)
    S["stamp"] = ParagraphStyle("s_stamp", parent=ss["Normal"], fontName="Helvetica-Bold",
                                fontSize=11, leading=14, alignment=TA_CENTER,
                                textColor=colors.HexColor("#b22222"))
    return S


# Common brand / entity constants (all fictional)
ENTITY = dict(
    name="Southgate Textiles Private Limited",
    business="Home textiles and furnishing fabrics manufacturer",
    office="Plot 47, SIDCO Industrial Estate, Kurichi, Coimbatore 641021, Tamil Nadu",
    cin="U17291TZ2016PTC027431",
    pan="AAHCS6612M",
    gstin="33AAHCS6612M1ZQ",
    incorp="18 March 2016",
    employees=46,
    bank="Continental Commercial Bank, Coimbatore SME Branch",
    account="914020055831447",
)

DIRECTORS = [
    dict(name="Lakshmi Iyer", role="Managing Director", din="07421683",
         dob="12 July 1979", address="No. 9, Race Course Road, Coimbatore 641018, Tamil Nadu",
         pan_masked="AXXXX1683M", aadhaar_masked="XXXX XXXX 4471"),
    dict(name="Venkat Iyer", role="Director", din="07421699",
         dob="03 September 1976", address="No. 9, Race Course Road, Coimbatore 641018, Tamil Nadu",
         pan_masked="AXXXX1699V", aadhaar_masked="XXXX XXXX 9026"),
]


def letterhead(S, tagline=True):
    """Return flowables forming the Southgate letterhead block."""
    out = [Paragraph(ENTITY["name"], S["title"])]
    if tagline:
        out.append(Paragraph(ENTITY["business"], S["subtitle"]))
    reg = ("Registered Office: %s<br/>CIN: %s &nbsp;|&nbsp; PAN: %s &nbsp;|&nbsp; GSTIN: %s"
           % (ENTITY["office"], ENTITY["cin"], ENTITY["pan"], ENTITY["gstin"]))
    out.append(Paragraph(reg, ParagraphStyle("lh", parent=S["small"], alignment=TA_CENTER)))
    out.append(Spacer(1, 4))
    out.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#20406a"),
                          spaceBefore=2, spaceAfter=8))
    return out
