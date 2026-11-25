"""Realistic test documents for the test pack: each follows the layout of a real document of its kind (the templates
in OneDrive_2026-10-13/Sample Docs, studied in place) or of a published format (a bank's or regulator's specimen),
filled with the fictional borrower of services/ingestion/tests/docsets.py. The builders take the same parameters as
the docsets builders they replace, so every scenario set keeps working; scripts/make_test_pack.py swaps them in.

Never reproduced (CLAUDE.md rule 8): the national or state emblem, any seal or stamp, logos, QR codes, barcodes,
watermarks, digital-signature boxes and signature images. A signatory line reads "Sd/-". Every page carries the
one-line footer. Every name and number is fictional; the fictional lenders, bureau and analytics firm are not real.

Where the app reads a table or a field by its label (config/ingestion/fields.yaml, keywords.yaml), the realistic
layout keeps the label the real documents use; where real issuers word it differently (bank statement columns), the
wording chosen is one real banks use that the app reads, and the README says so.
"""

from __future__ import annotations

import io
import re
import sys
import zlib
from dataclasses import replace
from itertools import zip_longest

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from tests import docsets as D

import template_pages as TP

W, H = A4
FOOTER = D.FOOTER
L, R = 50.0, W - 50.0           # page margins
BASE = D.BASE
TAN = "MUMK12345E"
AUDITOR = ("Daruwala and Rane", "Chartered Accountants", "112233W", "Kiran Daruwala", "104512")
VALUER = ("Er. Sunil Kale", "B.E. (Civil), Registered Valuer (Land and Building)", "IBBI/RV/03/2019/11042")
BUREAU = "Northstar Credit Information Company Limited"          # fictional
ANALYTICS = "Arcadia Data Analytics Private Limited"              # fictional
ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
        "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
ORD = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth",
       10: "Tenth", 11: "Eleventh", 12: "Twelfth", 13: "Thirteenth", 14: "Fourteenth", 15: "Fifteenth", 16: "Sixteenth",
       17: "Seventeenth", 18: "Eighteenth", 19: "Nineteenth", 20: "Twentieth", 21: "Twenty-first", 22: "Twenty-second",
       23: "Twenty-third", 24: "Twenty-fourth", 25: "Twenty-fifth", 26: "Twenty-sixth", 27: "Twenty-seventh",
       28: "Twenty-eighth", 29: "Twenty-ninth", 30: "Thirtieth", 31: "Thirty-first"}
CHECK: list[str] | None = None     # set to a list to collect pieces of text set too close together (see Doc.close_cells)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]


# --- numbers and dates in words ---------------------------------------------------------------------------------

def _two(n: int) -> str:
    return ONES[n] if n < 20 else (TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else ""))


def _three(n: int) -> str:
    h, r = divmod(n, 100)
    return " ".join(x for x in (f"{ONES[h]} Hundred" if h else "", _two(r) if r else "") if x)


def words(n: int) -> str:
    """Rupees in the Indian system: 4,25,00,000 -> Four Crore Twenty-Five Lakh."""
    parts = []
    for unit, size in (("Crore", 10_000_000), ("Lakh", 100_000), ("Thousand", 1000)):
        q, n = divmod(n, size)
        if q:
            parts.append(f"{words(q) if q >= 100 else _two(q)} {unit}")
    if n:
        parts.append(_three(n))
    return " ".join(parts) or "Zero"


def year_words(y: int) -> str:
    return f"Two thousand {_two(y - 2000).lower()}" if y > 2000 else "Two thousand"


def parse_date(text: str) -> tuple[int, int, int]:
    """'18 March 2015' or 'Monday, 12 October 2026' -> (18, 3, 2015)."""
    toks = text.replace(",", " ").split()
    d = int(next(t for t in toks if t.isdigit() and len(t) <= 2))
    m = next(i for i, name in enumerate(MONTHS, 1) if any(t.lower().startswith(name[:3].lower()) for t in toks if t.isalpha()))
    y = int(next(t for t in toks if t.isdigit() and len(t) == 4))
    return d, m, y


def date_words(text: str) -> str:
    d, m, y = parse_date(text)
    return f"{ORD[d]} day of {MONTHS[m - 1]} {year_words(y)}"


def dmy(text: str, sep: str = "/") -> str:
    d, m, y = parse_date(text)
    return f"{d:02d}{sep}{m:02d}{sep}{y}"


def inr(n: float) -> str:
    return D.inr(n) if n >= 0 else f"({D.inr(-n)})"


def num(*parts, digits: int = 7) -> str:
    """A stable number made from the parts (Python's hash() changes between runs)."""
    return f"{zlib.crc32('|'.join(map(str, parts)).encode()) % 10**digits:0{digits}d}"


def halves(address: str) -> tuple[str, str]:
    """An address broken into two lines at the comma nearest its middle."""
    parts = address.split(", ")
    best = min(range(1, len(parts)), key=lambda i: abs(len(", ".join(parts[:i])) - len(address) / 2)) if len(parts) > 1 else 1
    return ", ".join(parts[:best]), ", ".join(parts[best:]) or "-"


DISTRICT = {"Navi Mumbai": "Raigad", "Pune": "Pune", "Mumbai": "Mumbai Suburban", "Thane": "Thane",
            "Hyderabad": "Hyderabad", "Rangareddy": "Rangareddy", "Bengaluru": "Bengaluru Urban"}


def town(address: str) -> str:
    """The town of an address written "..., <town> <PIN>, <State>"."""
    parts = address.split(", ")
    return re.sub(r"\s*\d{6}$", "", parts[-2]) if len(parts) > 1 else address


def pin_state(address: str) -> tuple[str, str]:
    parts = address.split(", ")
    m = re.search(r"(\d{6})$", parts[-2]) if len(parts) > 1 else None
    return (m[1] if m else ""), parts[-1]


def mca_address(address: str) -> tuple[str, str]:
    """An address as the registry prints it: the premises in capitals ending in a comma, then city, district, state,
    country and PIN code."""
    parts = address.split(", ")
    state = parts[-1]
    m = re.search(r"^(.*?)\s*(\d{6})$", parts[-2])
    city, pin = (m[1], m[2]) if m else (parts[-2], "")
    return ", ".join(parts[:-2]).upper() + ",", f"{city}, {DISTRICT.get(city, city)}, {state}, India, {pin}"


def lakh(n: float) -> str:
    return f"{n / 100_000:,.2f}"


# --- the page builder -------------------------------------------------------------------------------------------

class Doc:
    """Pages of drawing operations from the top; render() adds the footer (and page numbers if asked)."""

    def __init__(self, *, page_numbers: str | None = None, header=None, foot_note: str | None = None):
        self.pages: list[list] = []
        self.page_numbers, self.header, self.foot_note = page_numbers, header, foot_note
        self.label = sys._getframe(1).f_code.co_name
        self.new_page()

    def new_page(self):
        self.ops: list = []
        self.pages.append(self.ops)
        self.y = H - 50
        if self.header:
            self.header(self)

    def need(self, h: float):
        if self.y - h < 70:
            self.new_page()

    def text(self, x, s, *, font="Helvetica", size=9.5, align="l", y=None):
        self.ops.append(("t", x, self.y if y is None else y, str(s), font, size, align))

    def line(self, x1, y1, x2, y2, w=0.6):
        self.ops.append(("l", x1, y1, x2, y2, w))

    def rect(self, x, y, w, h, lw=0.6, fill=None):
        self.ops.append(("r", x, y, w, h, lw, fill))

    def down(self, h=14.0):
        self.y -= h

    def write(self, s, *, x=L, font="Helvetica", size=9.5, align="l", lead=None):
        self.need(size + 4)
        if align == "c":
            x = W / 2
        elif align == "r":
            x = R
        self.text(x, s, font=font, size=size, align=align)
        self.down(lead or size + 4.5)

    def para(self, s, *, x=L, width=None, font="Helvetica", size=9.5, lead=None, indent=0.0):
        width = width or (R - x)
        lead = lead or size + 3.5
        line, first = "", True
        for word in s.split():
            trial = f"{line} {word}".strip()
            if stringWidth(trial, font, size) > width - (indent if first else 0) and line:
                self.need(lead)
                self.text(x + (indent if first else 0), line, font=font, size=size)
                self.down(lead)
                line, first = word, False
            else:
                line = trial
        if line:
            self.need(lead)
            self.text(x + (indent if first else 0), line, font=font, size=size)
            self.down(lead)

    def kv(self, pairs, *, x=L, x2=210, font="Helvetica", size=9.5, bold_key=False, lead=None):
        for k, v in pairs:
            self.need(size + 4)
            self.text(x, k, font="Helvetica-Bold" if bold_key else font, size=size)
            self.text(x2, v, font=font, size=size)
            self.down(lead or size + 5)

    def hr(self, w=0.8, gap=6):
        """A rule under the last line written (its baseline is at least 8 points up), clear of the next line's capitals."""
        self.line(L, self.y + 3, R, self.y + 3, w)
        self.down(gap + 8)

    def table(self, cols, rows, *, size=8.6, head_font="Helvetica-Bold", font="Helvetica", grid=True, row_h=None,
              repeat_head=True, head=True, head_valign="top", pad=7.0):
        """cols: [(title, x_left, x_right, align)]; rows: lists of cell text. Each cell on one line, so the app's
        column reader sees one value per column. A title may hold line breaks ("Total taxable\\nvalue"), set from the
        top or centred on the tallest title, as the portal printouts do. Cells sit `pad` points inside their column, so
        neighbouring cells stay more than the reader's column gap apart."""
        row_h = row_h or size + 6
        x0, x1 = cols[0][1], cols[-1][2]
        self._pad = pad
        n_head = max(len(c[0].split("\n")) for c in cols)
        lead = size + 2.5

        def header():
            h = row_h + (n_head - 1) * lead
            self.need(h + row_h)
            if grid:
                self.rect(x0, self.y - 4 - (n_head - 1) * lead, x1 - x0, h, 0.6, fill=0.9)
            for title, a, b, al in cols:
                parts = title.split("\n")
                off = (n_head - len(parts)) / 2 if head_valign == "middle" else 0
                for k, part in enumerate(parts):
                    self.text(a + pad if al != "r" else b - pad, part, font=head_font, size=size, align=al,
                              y=self.y - (off + k) * lead)
            self.down(row_h + (n_head - 1) * lead)

        if head:
            header()
        for r in rows:
            bold = isinstance(r, tuple) and len(r) == 2 and r[0] == "bold"
            cells = r[1] if bold else r
            n_lines = max(len(str(c).split("\n")) for c in cells if c is not None) if cells else 1
            h = row_h + (n_lines - 1) * lead          # a cell that wraps (the label) makes the row taller
            if self.y - h < 70:
                self.new_page()
                if head and repeat_head:
                    header()
            if grid:
                self.rect(x0, self.y - 4 - (n_lines - 1) * lead, x1 - x0, h, 0.4)
                for _, a, b, _ in cols[1:]:
                    self.line(a, self.y - 4 - (n_lines - 1) * lead, a, self.y - 4 + row_h, 0.4)
            for (title, a, b, al), cell in zip(cols, cells):
                if cell in (None, ""):
                    continue
                for k, part in enumerate(str(cell).split("\n")):
                    self.text(a + pad if al != "r" else b - pad, part, font="Helvetica-Bold" if bold else font, size=size,
                              align=al, y=self.y - k * lead)
            self.down(h)
        self.down(4)                                  # room between the table's last rule and the next line

    def close_cells(self, gap: float = 13.0) -> list[str]:
        """Pieces of text set on one line closer than the reader's column gap (12 points): the reader would join them
        into one cell. Each is a generator mistake unless the pieces are meant to read as one phrase."""
        out = []
        for no, ops in enumerate(self.pages, 1):
            rows: dict[float, list] = {}
            for op in ops:
                if op[0] != "t" or not op[3].strip():
                    continue
                _, x, y, s, font, size, al = op
                w = stringWidth(s, font, size)
                a = x if al == "l" else x - w if al == "r" else x - w / 2
                rows.setdefault(round(y), []).append((a, a + w, s))
            for y, items in rows.items():
                items.sort()
                for (a0, a1, s0), (b0, b1, s1) in zip(items, items[1:]):
                    if b0 - a1 < gap:
                        out.append(f"page {no}: '{s0[-30:]}' | '{s1[:30]}' gap {b0 - a1:.1f}")
        return out

    def render(self) -> bytes:
        if CHECK is not None:
            CHECK.extend(f"{self.label} {c}" for c in self.close_cells())
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4, invariant=1)
        c.setTitle("Specimen")
        n = len(self.pages)
        for i, ops in enumerate(self.pages, 1):
            for op in ops:
                if op[0] == "t":
                    _, x, y, s, font, size, al = op
                    c.setFont(font, size)
                    (c.drawRightString if al == "r" else c.drawCentredString if al == "c" else c.drawString)(x, y, s)
                elif op[0] == "l":
                    _, x1, y1, x2, y2, w = op
                    c.setLineWidth(w)
                    c.line(x1, y1, x2, y2)
                elif op[0] == "r":
                    _, x, y, w, h, lw, fill = op
                    c.setLineWidth(lw)
                    if fill is not None:
                        c.setFillGray(fill)
                        c.rect(x, y, w, h, stroke=1, fill=1)
                        c.setFillGray(0)
                    else:
                        c.rect(x, y, w, h, stroke=1, fill=0)
            if self.foot_note:
                c.setFont("Helvetica", 7)
                c.drawCentredString(W / 2, 50, self.foot_note)
            if self.page_numbers:
                c.setFont("Helvetica", 7.5)
                c.drawRightString(R, 36, self.page_numbers.format(i=i, n=n))
            c.setFont("Helvetica", 7)
            c.drawString(L, 24, FOOTER)
            c.showPage()
        c.save()
        return buf.getvalue()


def kind(e: D.Entity) -> str:
    """company, firm or individual (a proprietorship), from the fourth character of the PAN."""
    return {"C": "company", "F": "firm", "P": "individual"}.get(e.pan[3:4], "company")


CONSTITUTION = {"company": "Private Limited Company", "firm": "Partnership Firm", "individual": "Proprietorship"}


def letterhead(d: Doc, e: D.Entity = BASE, *, cin: str | None = None):
    d.write(e.name.upper(), font="Helvetica-Bold", size=14, align="c", lead=15)
    ident = f"CIN: {cin or e.cin}  |  " if (cin or e.cin) else f"GSTIN: {e.gstin}  |  "
    d.write(f"{ident}Regd. Office: {e.office}", size=7.5, align="c", lead=10)
    d.write("Tel: +91 22 2741 5520  |  Email: accounts@kestrel-fab.example", size=7.5, align="c", lead=8)
    d.hr(1.2)


# --- constitution and identity ------------------------------------------------------------------------------------

def certificate_of_incorporation(e: D.Entity = BASE, *, cin: str | None = None, name: str | None = None,
                                 date: str | None = None) -> bytes:
    """The Ministry of Corporate Affairs certificate (Central Registration Centre), drawn at the template's measured
    positions: US Letter, Times 12, the incorporation date in words, the CIN, the PAN and TAN in bold with their
    asterisks, the registrar's block on the right, the justified disclaimer, the rule and the mailing address. Not
    drawn (CLAUDE.md rule 8): the national emblem, the digital-signature box and the round seal; their space is left
    empty."""
    on = date if date and not date[0].isdigit() else date_words(date or e.incorporated)
    who = (name or e.name).upper()
    s = TP.Sheet(612.0, 792.0, footer_x=20.7, footer_y=14.0)
    TR, TB = "Times-Roman", "Times-Bold"
    s.text(234.2, 116.1, "GOVERNMENT OF INDIA ", TB, 12)          # the template's left edges
    s.text(199.7, 129.1, "MINISTRY OF CORPORATE AFFAIRS ", TB, 12)
    s.text(306.0, 148.1, "Central Registration Centre", TR, 12, align="c")
    s.text(306.0, 168.6, "Certificate of Incorporation", TB, 20, align="c")
    s.text(22.8, 198.6, "[Pursuant to sub-section (2) of section 7 and sub-section (1) of section 8 of the Companies "
                        "Act, 2013 (18 of 2013) and ", TR, 12)
    s.text(175.5, 211.6, "rule 18 of the Companies (Incorporation) Rules, 2014]", TR, 12)
    s.para(20.7, 251.6, 571.0, f"I hereby certify that {who} is incorporated on this {on} under the Companies Act, "
                               "2013 (18 of 2013) and that the company is limited by shares.", TR, 12, lead=13.4)
    s.text(20.7, 297.6, "The Corporate Identity Number of the company is", TR, 12)
    s.text(267.0, 297.6, f"{cin or e.cin}.", TR, 12)
    s.text(20.7, 324.6, "The Permanent Account Number (PAN) of the company is", TR, 12)
    s.text(310.5, 324.6, e.pan, TB, 12)
    s.text(412.6, 325.6, "*", "Helvetica", 12)
    s.text(20.7, 346.1, "The Tax Deduction and Collection Account Number (TAN) of the company is", TR, 12)
    s.text(400.0, 346.1, TAN, TB, 12)
    s.text(501.7, 347.6, "*", "Helvetica", 12)
    s.text(20.7, 371.6, f"Given under my hand at Manesar this {on} .", TR, 12)
    # the digital-signature box (397.5 to 413.5) is not drawn
    s.text(592.6, 421.6, "Digital Signature Certificate", TR, 12, align="r")
    s.text(592.0, 437.1, "Ms. Kavita Menon", TR, 12, align="r")
    s.text(592.5, 466.6, "For and on behalf of the Jurisdictional Registrar of Companies", TR, 12, align="r")
    s.text(591.3, 484.6, "Registrar of Companies", TR, 12, align="r")
    s.text(592.6, 502.6, "Central Registration Centre", TR, 12, align="r")
    top = s.para(20.3, 524.1, 571.3, "Disclaimer: This certificate only evidences incorporation of the company on the "
                 "basis of documents and declarations of the applicant(s). This certificate is neither a license nor "
                 "permission to conduct business or solicit deposits or funds from public. Permission of sector "
                 "regulator is necessary wherever required. Registration status and other details of the company can "
                 "be verified on", TR, 12, lead=13.35, justify=True)
    last = "company can be verified on "
    s.text(20.3 + TP.width(last, TR, 12), 564.1, "www.mca.gov.in", TR, 12, colour="#0000FF")
    s.line(20.3 + TP.width(last, TR, 12), 574.0, 20.3 + TP.width(last + "www.mca.gov.in", TR, 12), 574.0, 0.41, "#0000FF")
    s.line(19.0, 595.0, 593.0, 595.0, 1.44)
    s.text(20.7, 602.1, "Mailing Address as per record available in Registrar of Companies office", TR, 12)
    s.text(20.7 + TP.width("Mailing Address as per record available in Registrar of Companies office", TR, 12), 602.1,
           ":", TB, 12)
    first, second = mca_address(e.office)
    s.text(20.7, 624.1, who, TR, 12)
    s.text(20.7, 642.1, first, TR, 12)
    s.text(20.7, 660.1, second, TR, 12)
    s.text(19.4, 706.6, "*", TR, 12)
    s.text(27.2, 705.6, "as issued by the Income Tax Department", TR, 12)
    return s.render()


def company_pan(e: D.Entity = BASE, *, pan: str | None = None, name: str | None = None, status: str = "Company") -> bytes:
    """The e-PAN as the Income Tax Department issues it, drawn at the template's measured positions and colours: the
    bilingual header band, the title band, the Name and Date of Incorporation / Formation rows, the four notes with
    their Hindi lines, the cut line and the two-sided card. Not drawn (CLAUDE.md rule 8): the national emblem, the QR
    codes, the digital-signature mark, the hologram and the card's background artwork; their places are left plain.
    The notes are paraphrased."""
    p = pan or e.pan
    who = (name or e.name).upper()
    born = dmy(e.incorporated)
    s = TP.Sheet(595.32, 841.92, footer_x=24.0, footer_y=8.0)
    HI_B, HI, HS = "NotoSerifDevanagari-Bold", "NotoSansDevanagari-Regular", "NotoSerifDevanagari-Regular"
    INK, BLUE = "#1E0D15", "#24689E"
    s.box(19.5, 19.5, 575.0, 822.0, 0.8)
    # --- header band and title band
    s.gradient(20.0, 20.0, 574.6, 105.0, ["#CDDDEC", "#B6D8EC", "#A6D6EC"])
    s.script(35.5, 41.0, "आयकर   विभाग", 26, font=HI_B, colour=INK, fit_w=216.0, fit_h=23.5)
    s.text(32.0, 78.6, "INCOME TAX DEPARTMENT", "TimesNewRoman", 22.7, colour=INK, fit_w=219.5)
    s.script(369.0, 47.5, "भारत   सरकार", 26, font=HI_B, colour=INK, fit_w=186.0, fit_h=17.0)
    s.text(373.0, 78.6, "GOVT. OF INDIA", "TimesNewRoman", 22.7, colour=INK, fit_w=180.0)
    s.gradient(20.0, 107.0, 574.6, 175.5, ["#DAE5F4", "#CAE5F5", "#ADE1F5"])
    s.script(297.0, 115.5, "ई– स्थायी लेखा संख्या कार्ड", 12.5, font=HI, colour="#1A1A1A", align="c", fit_w=134.0, fit_h=13.5)
    s.text(122.5, 133.2, "e - Permanent Account Number (e-PAN) Card", "DejaVuSans-Bold", 13.5, colour=BLUE, fit_w=350.0)
    s.text(296.5, 151.2, p, "Arial", 14.7, align="c")
    # --- the rows: label cells, value cells, the large row (photo, code and signature places left plain)
    LAB, VAL = "#B7CBE4", "#DBE7F5"
    s.fill(20.0, 177.0, 175.0, 215.5, LAB)
    s.fill(177.0, 177.0, 574.6, 215.5, VAL)
    s.script(28.5, 190.0, "नाम /", 10, font=HI, colour="#333333", fit_h=7.5)
    s.text(51.5, 189.4, "Name", "Arial", 10, colour="#333333")
    s.text(181.5, 190.3, who, "Arial", 10)
    s.fill(20.0, 217.5, 175.0, 253.5, LAB)
    s.fill(177.0, 217.5, 574.6, 253.5, VAL)
    s.script(27.5, 222.5, "निगमन/गठन की तारीख", 10, font=HI, colour="#333333", fit_w=78.0, fit_h=9.0)
    s.text(29.0, 232.6, "Date of Incorporation / Formation", "Arial", 10, colour="#333333", fit_w=142.0)
    s.text(182.5, 232.6, born, "Arial", 10)
    s.fill(20.0, 255.5, 175.0, 365.5, LAB)
    s.fill(177.0, 255.5, 330.0, 365.5, VAL)
    s.fill(332.0, 255.5, 447.0, 365.5, LAB)
    s.fill(449.0, 255.5, 574.6, 365.5, VAL)
    # --- the notes (paraphrased), each with its Hindi line
    notes = [
        (374.5, ["Permanent Account Number (PAN) lets the Income Tax Department link a taxpayer's transactions, such as tax",
                 "payments, TDS/TCS credits, returns of income and specified transactions, and keep the information current."],
         ["स्थायी लेखा संख्या (पैन) से आयकर विभाग करदाता के लेनदेन, जैसे कर भुगतान, टीडीएस/टीसीएस क्रेडिट और आय विवरणी,",
          "आपस में जोड़ पाता है और जानकारी को अद्यतन रखता है।"]),
        (416.5, ["Quoting PAN is now mandatory for several financial transactions (see Rule 114B of the Income-tax Rules, 1962)."],
         ["अनेक वित्तीय लेनदेन में पैन का उल्लेख अब अनिवार्य है (आयकर नियम, 1962 का नियम 114बी देखें)।"]),
        (437.5, ["Possessing or using more than one PAN is against the law and may attract a penalty of up to Rs. 10,000."],
         ["एक से अधिक पैन रखना या उपयोग करना कानून के विरुद्ध है और इस पर 10,000 रुपये तक का दंड लग सकता है।"]),
        (459.0, ["An e-PAN issued electronically is a valid proof of the Permanent Account Number, and the card below may be",
                 "printed and used as the PAN card."],
         ["इलेक्ट्रॉनिक रूप से जारी ई-पैन स्थायी लेखा संख्या का वैध प्रमाण है, और नीचे दिया कार्ड मुद्रित कर पैन कार्ड के रूप में उपयोग किया जा सकता है।"]),
    ]
    for top, en, hi in notes:
        s.text(36.5, top - 0.5, "✓", "DejaVuSans", 8.5, colour="#303030")
        t = top
        for k, line in enumerate(en):
            full = k < len(en) - 1
            s.text(51.0, t, line, "TimesNewRoman", 9.1, colour="#1A1A1A", fit_w=507.0 if full else None)
            t += 10.0
        for line in hi:
            s.script(51.0, t - 0.5, line, 8.2, font="NotoSansDevanagari-Bold", colour="#2A2A2A", fit_h=9.0)
            t += 9.6
    # --- the cut line and the card
    s.dashed(20.0, 512.5, 278.0, 512.5, 0.6, (2.2, 1.6))
    s.dashed(298.0, 512.5, 575.0, 512.5, 0.6, (2.2, 1.6))
    s.text(280.5, 509.0, "Cut", "Arial", 7.0)
    for a in ((59.0, 534.0, 547.5, 534.0), (59.0, 692.0, 547.5, 692.0), (59.0, 534.0, 59.0, 692.0),
              (547.5, 534.0, 547.5, 692.0), (303.5, 534.0, 303.5, 692.0)):
        s.dashed(*a, 0.5, (2.0, 1.6), "#555555")
    s.rotated(307.0, 627.5, "Fold", "Arial-Bold", 5.0, 90)
    s.gradient(61.5, 538.5, 300.0, 687.5, ["#CDCBD8", "#9FC1DA", "#62B6DB"], radius=8)
    s.gradient(306.5, 538.5, 543.5, 687.5, ["#CBCFD8", "#A3C7D7", "#55B2D8"], radius=8)
    CARD = "#5E2233"
    s.script(76.0, 546.5, "आयकर   विभाग", 11.5, font=HI_B, colour=CARD, fit_w=87.0, fit_h=12.0)
    s.text(74.5, 562.7, "INCOME TAX DEPARTMENT", "TimesNewRoman", 10.6, colour=CARD, fit_w=88.5)
    s.script(213.5, 550.0, "भारत   सरकार", 11.5, font=HI_B, colour=CARD, fit_w=75.5, fit_h=8.5)
    s.text(215.5, 562.7, "GOVT. OF INDIA", "TimesNewRoman", 10.6, colour=CARD, fit_w=72.5)
    s.script(134.5, 578.5, "स्थायी लेखा संख्या कार्ड", 8.0, font=HI, colour="#22335A", fit_w=71.0, fit_h=7.5)
    s.text(122.0, 588.7, "Permanent Account Number Card", "Arial", 7.6, colour="#22335A", fit_w=95.0)
    s.text(146.0, 597.6, p, "Arial", 14.0, fit_w=83.5)
    s.script(74.5, 618.0, "नाम /", 5.2, font=HI, colour="#22335A", fit_h=5.0)
    s.text(88.5, 617.0, "Name", "Arial", 5.2, colour="#22335A")
    first, rest = (who.rsplit(" ", 2)[0], " ".join(who.rsplit(" ", 2)[1:])) if len(who) > 26 else (who, "")
    s.text(75.0, 625.0, first, "Arial", 8.4)
    s.text(78.5, 634.6, rest, "Arial", 8.4)
    s.script(75.0, 657.0, "निगमन/गठन की तारीख", 5.4, font=HI, colour="#22335A", fit_w=57.5, fit_h=6.0)
    s.text(75.0, 663.6, "Date of Incorporation/Formation", "Arial", 5.4, colour="#22335A", fit_w=64.5)
    s.text(75.0, 670.0, born, "Arial", 10.0)
    s.script(324.0, 548.5, "इस कार्ड के खोने/पाने पर कृपया सूचित करें/लौटाएं:", 5.8, font=HI_B, colour="#1A1A1A", fit_w=119.0, fit_h=7.0)
    for k, line in enumerate(("आयकर पैन सेवा इकाई,", "5 वीं मंज़िल, स्टर्लिंग टावर,", "मॉडल कॉलोनी,", "पुणे - 411 016.")):
        s.script(324.0, 558.0 + k * 9.0, line, 5.6, font=HS, colour="#1A1A1A", fit_h=6.6)
    s.text(323.0, 604.3, "If this card is lost / someone's lost card is found,", "TimesNewRoman", 7.4, colour="#1A1A1A")
    s.text(323.0, 612.3, "please inform / return to :", "TimesNewRoman", 7.4, colour="#1A1A1A")
    for k, line in enumerate(("Income Tax PAN Services Unit,", "5th Floor, Sterling Tower,", "Model Colony,", "Pune - 411 016.")):
        s.text(323.0, 621.8 + k * 8.4, line, "TimesNewRoman", 7.4, colour="#1A1A1A")
    s.text(323.0, 662.3, "Tel: 91-20-2400 1180, Fax: 91-20-2400 1181", "TimesNewRoman", 7.4, colour="#1A1A1A")
    # --- the closing note (paraphrased) with its link
    s.text(70.5, 721.2, "An e-PAN issued electronically and signed digitally is a valid mode of issue of the Permanent Account",
           "Arial-Bold", 8.0, fit_w=435.5)
    s.text(70.5, 730.7, "Number (PAN) under section 139A of the Income-tax Act, 1961 and rule 114 of the Income-tax Rules, 1962,",
           "Arial-Bold", 8.0, fit_w=440.0)
    tail = "as amended. For more details, "
    s.text(70.5, 740.2, tail, "Arial-Bold", 8.0)
    xl = 70.5 + TP.width(tail, "Arial-Bold", 8.0)
    s.text(xl, 740.2, "click here", "Arial-Bold", 8.0, colour="#E8308A")
    s.line(xl, 748.2, xl + TP.width("click here", "Arial-Bold", 8.0), 748.2, 0.5, "#E8308A")
    return s.render()


SUBSCRIBERS = {"Meera Sathe": ("wife of Rohan Sathe", "business", 300_000), "Rohan Sathe": ("son of Vinayak Sathe", "business", 200_000),
               "Anil Gokhale": ("son of Prakash Gokhale", "engineer", 5_000)}


FAMILY = {"Meera Sathe": ("Mrs.", "Rohan Sathe (Spouse)", "Sunanda Joshi", "Female", "Married"),
          "Rohan Sathe": ("Mr.", "Vinayak Sathe (Father)", "Shalini Sathe", "Male", "Married"),
          "Anil Gokhale": ("Mr.", "Prakash Gokhale (Father)", "Rekha Gokhale", "Male", "Married")}


def _kyc_summary(d: Doc, e: D.Entity, p, role: str):
    """The bank's summary sheet for one person: the particulars the credit file needs, verified against the originals."""
    d.write(e.name, font="Helvetica-Bold", size=10.5, lead=12)
    ident = f"CIN: {e.cin}  |  PAN: {e.pan}" if e.cin else f"PAN: {e.pan}  |  GSTIN: {e.gstin}"
    d.write(ident, size=8.5, lead=12)
    d.write(f"{role.upper()} KYC SUMMARY SHEET", font="Helvetica-Bold", size=12, lead=20)
    pairs = [(f"Name of {role}", p.name)]
    if role == "Director":
        pairs.append(("Director Identification Number", p.din))
    pairs += [("Designation", p.designation), ("Date of Birth", p.dob), ("PAN (masked)", p.pan_masked),
              ("Aadhaar (masked)", p.aadhaar_masked), ("Residential Address", p.address),
              ("Relationship with company" if role == "Director" else "Relationship with firm",
               f"Promoter and {role.lower()}")]
    d.kv(pairs, x2=230, size=9.5, lead=16)
    d.down(8)
    d.write("Documents verified with the originals", font="Helvetica-Bold", size=9, lead=13)
    d.table([("Document", L, 260, "l"), ("Purpose", 260, 400, "l"), ("Verified", 400, R, "l")],
            [["PAN card (self-attested copy)", "Proof of identity", "Yes"], ["Aadhaar letter (masked copy)", "Proof of address", "Yes"],
             ["Central KYC form (attached)", "KYC record", "Yes"]], size=8.6)
    d.down(12)
    d.kv([("Verified by", "Sd/-  Relationship Manager, Business Banking, Taloja"), ("Date of verification", "09 October 2026")],
         x2=230, size=9, lead=13)


def _ckyc(d: Doc, e: D.Entity, p, role: str):
    """One person's Central KYC Registry individual form (Part I), as banks print it."""
    prefix, father, mother, gender, marital = FAMILY.get(p.name, ("Mr.", "-", "-", "Male", "Married"))
    first, *rest = p.name.split()
    d.write("CENTRAL KYC REGISTRY  |  KNOW YOUR CUSTOMER (KYC) APPLICATION FORM", font="Helvetica-Bold", size=10, lead=12)
    d.write("Individual  |  Part I  |  Application type: New  |  Account type: Normal", size=8, lead=16)
    d.rect(R - 80, d.y - 70, 80, 90, 0.6)
    d.text(R - 40, "Photograph", size=7.5, align="c", y=d.y - 30)

    def sec(t):
        d.down(4)
        d.rect(L, d.y - 4, R - L - 90, 14, 0.4, fill=0.88)
        d.text(L + 4, t, font="Helvetica-Bold", size=8.6)
        d.down(16)

    sec("1. Personal Details")
    d.kv([("Name (same as ID proof)", f"{prefix} {p.name}"), ("Prefix  |  First  |  Last name", f"{prefix}  |  {first}  |  {' '.join(rest)}"),
          ("Father / Spouse name", father), ("Mother name", mother), ("Gender", gender), ("Marital status", marital),
          ("Citizenship", "IN - Indian"), ("Residential status", "Resident Individual"), ("Occupation type", "B - Business")],
         x2=230, size=8.6, lead=13)
    sec("2. Proof of Identity and Address")
    d.kv([("PAN", p.pan_masked), ("Proof of address", "Aadhaar (offline verification), number masked"),
          ("Address type", "Residential"), ("Address", halves(p.address)[0]), ("", halves(p.address)[1]),
          ("PIN code  |  State  |  Country", f"{pin_state(p.address)[0]}  |  {pin_state(p.address)[1]}  |  IN")], x2=230, size=8.6, lead=13)
    sec("3. Contact Details")
    d.kv([("Mobile", "+91 98XXX X4176"), ("Email", f"{first.lower()}.{rest[-1].lower() if rest else 'x'}@kestrel-fab.example")],
         x2=230, size=8.6, lead=13)
    sec("4. Applicant Declaration")
    d.para("I hereby declare that the details furnished above are true and correct to the best of my knowledge and belief "
           "and I undertake to inform you of any changes therein, immediately.", size=8.4, lead=11)
    d.kv([("Place", town(p.address)), ("Date", "08 October 2026"), ("Signature of applicant", "Sd/-")], x2=230, size=8.6, lead=13)
    d.down(6)
    d.rect(L, d.y - 30, R - L, 40, 0.4)
    d.text(L + 4, "For office use only:  KYC verification carried out by  Employee name / code / designation / branch", size=7.5,
           y=d.y - 2)
    d.down(40)


def director_kyc(e: D.Entity = BASE, *, persons: tuple | None = None, role: str = "Director") -> bytes:
    """The bank's KYC set for the directors: a covering sheet naming them, then for each one the bank's summary sheet
    and the person's Central KYC form."""
    persons = persons if persons is not None else e.persons
    d = Doc()
    d.write(f"KYC OF THE {role.upper()}S", font="Helvetica-Bold", size=13, lead=16)
    d.write(f"Borrower: {e.name}", size=9.5, lead=18)
    d.para(f"Enclosed for each {role.lower()}: the bank's KYC summary sheet and the Central KYC Registry form, verified with "
           "self-attested copies of PAN and of the address proof. Personal identifiers are shown masked.", size=9.5, lead=13)
    d.down(6)
    for i, p in enumerate(persons, 1):
        d.write(f"{i}.  {p.name}, {p.designation}", size=9.5, lead=13)
    for p in persons:
        d.new_page()
        _kyc_summary(d, e, p, role)
        d.new_page()
        _ckyc(d, e, p, role)
    return d.render()


# --- authority and obligations -------------------------------------------------------------------------------------

def board_resolution(e: D.Entity = BASE, *, amount: str = "4,25,00,000", amount_words: str = "Four Crore Twenty-Five Lakh",
                     lender: str = "Harbour Commercial Bank, Taloja Branch", date: str = "Monday, 12 October 2026",
                     signed: bool = True, signatories: tuple | None = None, stamped: bool = True) -> bytes:
    """A certified true copy of the borrowing resolution on the company's letterhead (Section 179(3)(d)), with the
    authorised signatories and the certifying director's block."""
    sig = signatories if signatories is not None else e.persons
    d = Doc()
    letterhead(d, e)
    for t in ("CERTIFIED TRUE COPY OF THE RESOLUTION PASSED AT THE MEETING OF THE",
              f"BOARD OF DIRECTORS OF {e.name.upper()} (CIN {e.cin})",
              f"HELD ON {date.upper()} AT 11.00 A.M. AT THE REGISTERED OFFICE OF THE COMPANY"):
        d.write(t, font="Helvetica-Bold", size=9, lead=12.5)
    d.down(6)
    d.write(f"BORROWING FROM {lender.split(',')[0].upper()}", font="Helvetica-Bold", size=9.5, lead=16)
    d.para(f"\"RESOLVED THAT pursuant to Section 179(3)(d) and the other applicable provisions, if any, of the Companies "
           f"Act, 2013 and the rules made thereunder, the consent of the Board of Directors be and is hereby accorded to "
           f"borrow from {lender}, credit facilities by way of cash credit and term loan aggregating to Rs. {amount}/- "
           f"(Rupees {amount_words} only), on the terms and conditions set out in the bank's sanction letter, and that the "
           f"said borrowing is within the limits approved by the members under Section 180(1)(c) of the Act.", size=9.5, lead=13)
    d.down(4)
    names = " and ".join(f"{'Mrs.' if p.name.startswith('Meera') else 'Mr.'} {p.name}, {p.designation} (DIN {p.din})" for p in sig)
    d.para(f"RESOLVED FURTHER THAT {names} be and are hereby severally authorised to execute the loan agreement, "
           "hypothecation deed, guarantees and all other documents required by the bank, and to do all acts, deeds and "
           "things necessary to give effect to this resolution.", size=9.5, lead=13)
    d.down(4)
    d.para("RESOLVED FURTHER THAT the common seal of the company be affixed to such documents as may be required, in the "
           "presence of any one director, and that a certified true copy of this resolution be furnished to the bank.\"",
           size=9.5, lead=13)
    d.down(8)
    d.write("Authorised signatories", font="Helvetica-Bold", size=9, lead=13)
    d.table([("Name", L, 220, "l"), ("Designation", 220, 380, "l"), ("DIN", 380, R, "l")],
            [[p.name, p.designation, p.din] for p in sig], size=8.8)
    d.down(12)
    d.write("Certified to be a true copy", font="Helvetica-Bold", size=9.5, lead=14)
    d.write(f"For {e.name.upper()}", size=9.5, lead=16)
    d.kv([("Signature:", "Sd/-" if signed else ""), ("Name:", sig[0].name), ("Designation:", sig[0].designation),
          ("DIN:", sig[0].din), ("Company seal:", "affixed" if stamped else ""),
          ("Place:", town(e.office)), ("Date:", date.split(",")[-1].strip())], x2=L + 95, size=9.5, lead=14)
    return d.render()


def facilities_declaration(e: D.Entity = BASE, *, facilities=None, accounts=None, pan=None, cin=None, gstin=None,
                           signed: bool = True) -> bytes:
    """The borrower's declaration of existing credit facilities (the RBI's Annex I format for multiple banking) on its
    letterhead: fund-based and non-fund-based facilities, then its bank accounts."""
    facilities = facilities if facilities is not None else [(e.lender, "Term Loan", "2,50,00,000", "1,62,50,000", "1,25,000")]
    accounts = accounts if accounts is not None else [(e.bank, e.account, "Current Account")]
    d = Doc()
    letterhead(d, e, cin=cin)
    d.write("DECLARATION OF EXISTING CREDIT FACILITIES AND BANK ACCOUNTS", font="Helvetica-Bold", size=10.5, align="c", lead=12)
    d.write("(Information to be furnished by the borrower: multiple banking arrangement)", size=8, align="c", lead=18)
    ident = [("Name of Company" if kind(e) == "company" else "Name of Borrower", e.name), ("Date of Declaration", "12 October 2026"),
             ("PAN", pan or e.pan)] + ([("CIN", cin or e.cin)] if (cin or e.cin) else []) + [
             ("GSTIN", gstin or e.gstin), ("Constitution", CONSTITUTION[kind(e)]), ("Banking arrangement", "Multiple banking")]
    d.kv(ident, x2=200, size=9.5, lead=13)
    d.down(4)
    d.write("To, The Branch Manager, Harbour Commercial Bank, Taloja Branch", size=9.5, lead=16)
    d.para(f"We hereby declare that the {'company' if kind(e) == 'company' else 'firm'} enjoys the following existing credit facilities from banks and financial "
           "institutions as on the date of this declaration:", size=9.5, lead=13)
    d.write("A. Fund-based facilities (amounts outstanding as on 30 September 2026)", font="Helvetica-Bold", size=9, lead=13)
    cols = [("Name of Lender", L, 190, "l"), ("Nature of Facility", 190, 300, "l"), ("Sanctioned Limit", 300, 390, "r"),
            ("Outstanding", 390, 470, "r"), ("EMI", 470, R, "r")]
    d.table(cols, [list(f) for f in facilities], size=8.6)
    d.write("Total", font="Helvetica-Bold", size=8.6, lead=14)
    d.write("B. Non-fund-based facilities (letters of credit, bank guarantees): Nil", size=9, lead=14)
    d.para("We further declare that the company has no other borrowing or credit facility from any bank, financial "
           "institution or other lender, and we undertake to inform you before availing of any.", size=9.5, lead=13)
    d.down(4)
    d.write("We also declare that the company holds the following bank accounts:", size=9.5, lead=14)
    d.table([("Name of Bank", L, 220, "l"), ("Account Number", 220, 380, "l"), ("Type of Account", 380, R, "l")],
            [list(a) for a in accounts], size=8.6)
    d.down(10)
    d.write(f"For {e.name}", size=9.5, lead=16)
    d.kv([("Signature:", "Sd/-" if signed else ""), ("Name:", e.persons[0].name),
          ("Designation:", f"{e.persons[0].designation} (Authorised signatory)"), ("Place:", town(e.office)),
          ("Date:", "12 October 2026")], x2=L + 85, size=9.5, lead=14)
    return d.render()


def sanction_letter(e: D.Entity = BASE, *, lender: str | None = None, facility: str = "Term Loan", amount: str = "2,50,00,000",
                    rate: str = "10.75% p.a.", tenure: str = "72 months", emi: str = "1,25,000") -> bytes:
    """A lender's sanction letter: letterhead, reference, a facility table, security, the key terms and conditions
    (as MSME lending policies list them) and the borrower's acceptance."""
    lender = lender or e.lender
    d = Doc()
    d.write(lender.upper(), font="Helvetica-Bold", size=14, align="c", lead=15)
    d.write("Registered Office: 4th Floor, Sterling Arcade, Bandra Kurla Complex, Mumbai 400051", size=7.5, align="c", lead=9)
    d.write("Customer care: 1800 266 0417  |  www.lotuscrest-finance.example", size=7.5, align="c", lead=8)
    d.hr(1.2)
    d.write("SANCTION LETTER", font="Helvetica-Bold", size=11, align="c", lead=18)
    d.kv([("Reference", "LCF/SL/2024/0457"), ("Date of Sanction", "12 April 2024"), ("Borrower", e.name), ("Lender", lender)],
         x2=170, size=9.5, lead=13)
    d.down(4)
    d.write(f"To, The Board of Directors, {e.name}, {e.office}", size=8.8, lead=16)
    d.write(f"Sub: Sanction of {facility.lower()} of Rs. {amount}", font="Helvetica-Bold", size=9.5, lead=14)
    d.para("With reference to your application, we are pleased to sanction the following credit facility on the terms and "
           "conditions below. This letter is valid for acceptance within 30 days of its date.", size=9.5, lead=13)
    d.down(4)
    cols = [("Facility", L, 150, "l"), ("Sanctioned Amount", 150, 270, "r"), ("Rate of Interest", 270, 370, "l"),
            ("Tenure", 370, 450, "l"), ("EMI", 450, R, "r")]
    d.table(cols, [[facility, amount, rate, tenure, emi]], size=8.8)
    d.down(6)
    d.para("Security: hypothecation of the plant and machinery financed; personal guarantee of the directors, Mrs. Meera Sathe "
           "and Mr. Rohan Sathe.", size=9.5, lead=13)
    d.down(4)
    d.write("Terms and conditions", font="Helvetica-Bold", size=9.5, lead=14)
    for i, t in enumerate(("Interest is linked to the lender's benchmark rate plus a spread, reset every three months; the "
                           "key fact statement enclosed sets out the annual percentage rate.",
                           "Processing fee: 0.50% of the sanctioned amount plus GST, payable before disbursement.",
                           "Repayment in 72 equated monthly instalments by NACH from the borrower's current account.",
                           "Penal charges of 2% per annum on overdue amounts; no penal interest is added to the rate.",
                           "The assets financed are to be insured for their full value with the lender as loss payee.",
                           "The borrower will submit audited financial statements within six months of each year end."), 1):
        d.para(f"{i}.  {t}", size=9, lead=12, indent=0)
        d.down(2)
    d.down(8)
    d.write(f"For {lender}", size=9.5, lead=14)
    d.kv([("Signature:", "Sd/-"), ("Name:", "Ashish Bhandarkar"), ("Designation:", "Head - SME Credit")], x2=L + 85, size=9.5,
         lead=13)
    d.down(8)
    d.write(f"Accepted. For {e.name}", size=9.5, lead=14)
    d.kv([("Authorised signatory:", f"Sd/-  {e.persons[0].name}"), ("Date:", "16 April 2024")], x2=L + 120, size=9.5, lead=13)
    return d.render()


def bureau_report(e: D.Entity = BASE, *, facilities=None, pan=None, cin=None, gstin=None, parties=None, rank: str = "4") -> bytes:
    """A company credit report in the sections a commercial bureau prints (header, company details, rank, summary,
    enquiries, suits and wilful default, facilities, related parties), from a fictional bureau."""
    facilities = facilities if facilities is not None else [(e.lender, "Term Loan", "2,50,00,000", "1,62,50,000", "0", "Standard")]
    parties = parties if parties is not None else [(p.name, "Director", p.pan_masked) for p in e.persons]
    d = Doc()
    d.write(BUREAU, font="Helvetica-Bold", size=10, lead=12)
    d.write("COMPANY CREDIT REPORT", font="Helvetica-Bold", size=14, lead=14)
    d.write("Commercial Credit Information Report", size=9.5, lead=16)
    d.kv([("Report Date", "13 October 2026"), ("Control Number", "NCI-26-1013-448172"), ("Member", "Harbour Commercial Bank")],
         x2=170, size=9, lead=12)
    d.hr()
    d.write("COMPANY DETAILS", font="Helvetica-Bold", size=9.5, lead=13)
    d.kv([("Company Name", e.name), ("PAN", pan or e.pan)] + ([("CIN", cin or e.cin)] if (cin or e.cin) else []) + [
          ("GSTIN", gstin or e.gstin), ("Constitution", CONSTITUTION[kind(e)]),
          ("Date of Incorporation" if kind(e) == "company" else "Date of Formation", e.incorporated),
          ("Registered Office", e.office)], x2=170, size=9, lead=12)
    d.hr()
    d.write("RANK", font="Helvetica-Bold", size=9.5, lead=13)
    d.kv([("Credit Rank", rank)], x2=170, size=10, lead=13)
    d.para("Rank on a scale of 1 to 10, where 1 is the lowest risk; based on credit behaviour reported by members.", size=8,
           lead=11)
    d.hr()
    d.write("SUMMARY", font="Helvetica-Bold", size=9.5, lead=13)
    sanc = sum(int(f[2].replace(",", "")) for f in facilities)
    outs = sum(int(f[3].replace(",", "")) for f in facilities)
    over = sum(int(f[4].replace(",", "")) for f in facilities)
    d.kv([("Open credit facilities", str(len(facilities))), ("Total sanctioned", D.inr(sanc)), ("Total outstanding", D.inr(outs)),
          ("Total overdue", D.inr(over)), ("Asset Classification", "Standard" if not over else "Special Mention Account - 1"),
          ("DPD", "0 days past due in the last 12 months" if not over else "Up to 30 days past due"),
          ("Enquiries in the last 6 months", "1"), ("Suit Filed", "No suit filed"), ("Wilful Defaulter", "No")], x2=210, size=9, lead=12)
    d.hr()
    d.write("CREDIT FACILITIES", font="Helvetica-Bold", size=9.5, lead=13)
    cols = [("Lender", L, 190, "l"), ("Facility", 190, 270, "l"), ("Sanctioned", 270, 345, "r"), ("Outstanding", 345, 420, "r"),
            ("Overdue", 420, 480, "r"), ("Status", 480, R, "l")]
    d.table(cols, [list(f) for f in facilities], size=8.4)
    d.down(6)
    d.write("RELATED PARTIES", font="Helvetica-Bold", size=9.5, lead=13)
    d.table([("Name", L, 230, "l"), ("Relationship", 230, 380, "l"), ("PAN", 380, R, "l")], [list(p) for p in parties], size=8.6)
    d.down(8)
    d.write("END OF REPORT", font="Helvetica-Bold", size=9, align="c")
    return d.render()


# --- the bank statement -------------------------------------------------------------------------------------------

LEGEND = [("NEFT", "National Electronic Funds Transfer"), ("RTGS", "Real Time Gross Settlement"), ("IMPS", "Immediate Payment Service"),
          ("NACH", "National Automated Clearing House"), ("CHQ", "Cheque"), ("CSH", "Cash"), ("INT", "Interest"),
          ("GST", "Goods and Services Tax payment"), ("RTN", "Returned instrument")]


def bank_statement(e: D.Entity = BASE, *, txns, opening: int, start: str, end: str, account: str | None = None,
                   holder: str | None = None, bank: str | None = None) -> bytes:
    """A bank's current-account statement: the account block, the transactions with the running balance page by page
    (the column order of a large private bank's statement: date, narration, reference, value date, withdrawal,
    deposit, closing balance, worded as the app reads them), then the statement summary and the code legend."""
    account = account or e.account
    bank = bank or e.bank
    home = bank == e.bank
    d = Doc(page_numbers="Page {i} of {n}")
    d.write(bank.upper(), font="Helvetica-Bold", size=13, lead=14)
    d.write(f"{e.branch if home else 'Main'} Branch  |  {(e.branch + ', ' + town(e.office) + ' ' + pin_state(e.office)[0]) if home else 'Fort, Mumbai 400001'}",
            size=8, lead=12)
    d.write("Statement of Account", font="Helvetica-Bold", size=11, lead=16)
    office = e.office.split(", ")
    address = [", ".join(office[:2]), ", ".join(office[2:])]
    if max(stringWidth(a, "Helvetica", 8.2) for a in address) > 318 - (L + 84) - 8:     # wider than its column
        address = [""]
        for part in office:
            trial = f"{address[-1]}, {part}" if address[-1] else part
            if stringWidth(trial, "Helvetica", 8.2) > 318 - (L + 84) - 8 and address[-1]:
                address.append(part)
            else:
                address[-1] = trial
    left = ([("Account Name", holder or e.name)] + [("Address" if i == 0 else "", a) for i, a in enumerate(address)]
            + [("Customer ID", "CUS" + account[-6:]), ("Account Type", "Current Account")])
    city = pin_state(e.office)[0][:3] if home and pin_state(e.office)[0] else "400"     # MICR: the branch's city code
    right = [("Account Number", account), ("Branch / IFSC", f"{e.branch} / {e.ifsc}" if home else "Main / MRTB0000110"),
             ("MICR", city + account[-6:]), ("Currency", "INR"), ("Statement", f"{start} to {end}")]
    y0 = d.y
    for (k1, v1), (k2, v2) in zip_longest(left, right, fillvalue=("", "")):
        d.text(L, k1, font="Helvetica-Bold", size=8.2)
        d.text(L + 84, v1, size=8.2)
        d.text(318, k2, font="Helvetica-Bold", size=8.2)
        d.text(400, v2, size=8.2)
        d.down(12)
    d.rect(L - 4, d.y + 4, R - L + 8, y0 - d.y + 8, 0.5)
    d.down(4)
    d.write(f"Opening Balance ({start})   {D.inr(opening)}", font="Helvetica-Bold", size=8.2, lead=14)
    bal = opening
    rows = []
    credits = debits = 0
    for t in txns:
        bal += t.credit - t.debit
        credits += t.credit
        debits += t.debit
        rows.append([t.day, t.narration, t.ref, t.day, D.inr(t.debit) if t.debit else "", D.inr(t.credit) if t.credit else "",
                     D.inr(bal)])
    size, pad = 7.2, 2.0
    titles = ["Date", "Particulars", "Reference", "Value Date", "Debit", "Credit", "Balance"]
    aligns = ["l", "l", "l", "l", "r", "r", "r"]
    widths = [max(stringWidth(str(r[i]), "Helvetica", size) for r in rows + [titles]) for i in range(7)]
    widths = [max(w, stringWidth(t, "Helvetica-Bold", size)) for w, t in zip(widths, titles)]
    x0, x1 = 36.0, W - 36.0
    gap = (x1 - x0 - sum(widths) - 2 * pad * 7) / 6
    if gap < 14:
        raise ValueError(f"statement columns do not fit: gap {gap:.1f}")
    cols, x = [], x0
    for t, w, al in zip(titles, widths, aligns):
        cols.append((t, x, x + w + 2 * pad, al))
        x += w + 2 * pad + gap
    d.table(cols, rows, size=size, row_h=11.5, grid=False, pad=pad)
    d.down(8)
    d.write("Statement Summary", font="Helvetica-Bold", size=9.5, lead=13)
    d.kv([(f"Opening Balance ({start})", D.inr(opening)), ("Total Credits during period", D.inr(credits)),
          ("Total Debits during period", D.inr(debits)), (f"Closing Balance ({end})", D.inr(bal))], x2=250, size=9, lead=12)
    d.down(6)
    d.write("Legends used in the statement", font="Helvetica-Bold", size=8.5, lead=12)
    for code, meaning in LEGEND:
        d.write(f"{code}  -  {meaning}", size=7.6, lead=10)
    d.down(4)
    d.write("This is a computer-generated statement and does not require a signature.", size=7.6)
    return d.render()


# --- GST, tax and financial statements -----------------------------------------------------------------------------

def _gst_period(month):
    y, m = month
    fy = f"{y}-{(y + 1) % 100:02d}" if m >= 4 else f"{y - 1}-{y % 100:02d}"
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    return y, m, fy, ny, nm


def rs2(n: float) -> str:
    """Rupees and paise in the Indian grouping, as the GST portal prints them: 2,27,00,000.00."""
    whole, paise = divmod(round(n * 100), 100)
    return f"{D.inr(whole)}.{paise:02d}"


def gstr_3b(e: D.Entity = BASE, *, month, taxable: int, gstin: str | None = None, filed_on: str | None = None,
            name: str | None = None) -> bytes:
    """The GST portal's filed GSTR-3B (View/Download): drawn at the template's measured positions, in its fonts
    (Roboto), fills and rules. Page 1: Year and Period, 2(a) to 2(d), tables 3.1, 3.2 and 4; page 2: tables 5, 5.1,
    6.1, the break-up of tax liability and the verification. Amounts as the portal prints them (no grouping). The
    portal's diagonal "FILED" watermark is not drawn (CLAUDE.md rule 8)."""
    y, m, fy, ny, nm = _gst_period(month)
    filed = filed_on or f"20 {MONTHS[nm - 1]} {ny}"
    inter = round(taxable * 0.4, 2)
    igst, cgst = round(inter * 0.18, 2), round((taxable - inter) * 0.09, 2)
    sgst = cgst
    itc = {k: round(v * 0.62, 2) for k, v in (("i", igst), ("c", cgst), ("s", sgst))}
    P, z, dash = TP.plain, "0.00", "-"
    who = (name or e.name).upper()
    s = TP.Sheet()
    PEACH, BAND = "#FAD2B1", "#FDE9D9"
    # --- page 1
    s.text(243.0, 43.1, "Form GSTR-3B", "Roboto-Medium", 18)
    s.text(258.1, 73.2, "[See rule 61(5)]", "Roboto-Italic", 12)
    for k, (lab, val) in enumerate((("Year", fy), ("Period", D.MON[m - 1]))):
        t = 105.4 + k * 15.05
        s.fill(380.2, t, 463.8, t + 15.05, PEACH)
        s.text(384.5, t + 3.8, lab, "Roboto-Medium", 9)
        s.text(468.0, t + 3.8, val, "Roboto-Regular", 9)
    for yy in (105.4, 120.5, 135.5):
        s.line(380.0, yy, 572.0, yy, 0.5)
    for xx in (380.2, 463.8, 572.2):
        s.line(xx, 105.2, xx, 135.8, 0.5)
    arn = f"AA27{m:02d}{y % 100:02d}{num('3b', y, m)}"
    ident = [("GSTIN of the supplier", gstin or e.gstin), ("2(a). Legal name of the registered person", who),
             ("2(b). Trade name, if any", who), ("2(c). ARN", arn), ("2(d). Date of ARN", dmy(filed))]
    for k, (lab, val) in enumerate(ident):
        t = 156.0 + k * 13.87
        s.fill(20.2, t, 228.8, t + 13.87, PEACH)
        s.text(24.5, t + 3.6, lab, "Roboto-Regular", 8)
        s.text(233.0, t + 3.6, val, "Roboto-Regular", 8)
        s.line(20.0, t, 574.8, t, 0.5)
    s.line(20.0, 156.0 + 5 * 13.87, 574.8, 156.0 + 5 * 13.87, 0.5)
    for xx in (20.2, 228.8, 575.0):
        s.line(xx, 155.8, xx, 225.6, 0.5)
    s.text(460.0, 232.0, "(Amount in ₹ for all tables)", "Roboto-Regular", 8)

    def band(top, title):
        s.fill(20.0, top, 575.3, top + 15.7, BAND)
        s.text(25.0, top + 3.7, title, "Roboto-Medium", 10)
        return top + 21.2

    t = band(250.0, "3.1 Details of Outward supplies and inward supplies liable to reverse charge")
    e31 = [20.5, 292.1, 372.2, 435.1, 487.5, 545.8, 574.8]
    t = s.grid(e31, t, [
        {"head": True, "cells": ["Nature of Supplies", "Total taxable \nvalue", "Integrated \ntax", "Central \ntax",
                                 "State/UT \ntax", "Cess"]},
        {"cells": ["(a) Outward taxable supplies (other than zero rated, nil rated and exempted)", P(taxable), P(igst),
                   P(cgst), P(sgst), z]},
        {"cells": ["(b) Outward taxable supplies (zero rated)", z, z, dash, dash, z]},
        {"cells": ["(c ) Other outward supplies (nil rated, exempted)", z, dash, dash, dash, dash]},
        {"cells": ["(d) Inward supplies (liable to reverse charge)", z, z, z, z, z]},
        {"cells": ["(e) Non-GST outward supplies", z, dash, dash, dash, dash]}])
    t = band(t + 25.5, "3.2 Out of supplies made in 3.1 (a) above, details of inter-state supplies made")
    t = s.grid([20.5, 205.3, 390.0, 574.8], t, [
        {"head": True, "cells": ["Nature of Supplies", "Total taxable value", "Integrated tax"]},
        {"cells": ["Supplies made to Unregistered Persons", z, z]},
        {"cells": ["Supplies made to Composition Taxable Persons", z, z]},
        {"cells": ["Supplies made to UIN holders", z, z]}])
    t = band(t + 25.5, "4.  Eligible ITC")
    zz = [z, z, z, z]
    s.grid([20.5, 309.6, 379.7, 449.8, 519.9, 574.8], t, [
        {"head": True, "cells": ["Details", "Integrated tax", "Central tax", "State/UT tax", "Cess"]},
        {"bold": True, "cells": ["A. ITC Available (whether in full or part)", "", "", "", ""]},
        {"cells": ["(1) Import of goods", *zz]}, {"cells": ["(2) Import of services", *zz]},
        {"cells": ["(3) Inward supplies liable to reverse charge (other than 1 & 2 above)", *zz]},
        {"cells": ["(4) Inward supplies from ISD", *zz]},
        {"cells": ["(5) All other ITC", P(itc["i"]), P(itc["c"]), P(itc["s"]), z]},
        {"bold": True, "cells": ["B. ITC Reversed", "", "", "", ""]},
        {"cells": ["(1) As per rules 38,42 & 43 of CGST Rules and section 17(5)", *zz]},
        {"cells": ["(2) Others", *zz]},
        {"bold": True, "cells": ["C. Net ITC available (A-B)", P(itc["i"]), P(itc["c"]), P(itc["s"]), z]},
        {"bold": True, "cells": ["(D) Other Details", *zz]},
        {"cells": ["(1) ITC reclaimed which was reversed under Table 4(B)(2) in earlier tax period", *zz]},
        {"cells": ["(2) Ineligible ITC under section 16(4) & ITC restricted due to PoS rules", *zz]}])
    # --- page 2
    s.page()
    t = band(40.0, "5  Values of exempt, nil-rated and non-GST inward supplies")
    t = s.grid([20.5, 345.9, 460.3, 574.8], t, [
        {"head": True, "cells": ["Nature of Supplies", "Inter- State supplies", "Intra- State supplies"]},
        {"cells": ["From a supplier under composition scheme, Exempt, Nil rated supply", z, z]},
        {"cells": ["Non GST supply", z, z]}])
    t = band(t + 25.5, "5.1 Interest and Late fee for previous tax period")
    e4 = [20.5, 131.4, 242.2, 353.1, 463.9, 574.8]
    t = s.grid(e4, t, [
        {"head": True, "cells": ["Details", "Integrated tax", "Central tax", "State/UT tax", "Cess"]},
        {"cells": ["System computed Interest", dash, dash, dash, dash]},
        {"cells": ["Interest Paid", z, z, z, z]},
        {"cells": ["Late fee", dash, z, z, dash]}])
    t = band(t + 25.5, "6.1 Payment of tax")
    e6 = [20.5, 70.5, 120.5, 175.0, 225.0, 274.9, 324.9, 374.9, 424.9, 474.8, 524.8, 574.8]
    top6 = t
    # the two-level header: outer columns span both rows; "Tax paid through ITC" spans its four sub-columns
    for i in range(11):
        s.fill(e6[i], top6, e6[i + 1], top6 + 15.6, "#F2F2F2")
        s.fill(e6[i], top6 + 15.6, e6[i + 1], top6 + 68.3, "#F2F2F2")
    heads = {0: ["Descripti", "on"], 1: ["Tax ", "payable"], 2: ["Adjustment", " of ", "negative ", "liability of ",
             "previous ", "tax period"], 3: ["Net Tax ", "Payable"], 8: ["Tax paid ", "in cash"],
             9: ["Interest ", "paid in ", "cash"], 10: ["Late fee ", "paid in ", "cash"]}
    for i, lines in heads.items():
        for k, txt in enumerate(lines):
            s.text(e6[i] + 4.5, top6 + 4.1 + k * 10.55, txt, "Roboto-Medium", 9)
    s.text((e6[4] + e6[8]) / 2, top6 + 4.1, "Tax paid through ITC", "Roboto-Medium", 9, align="c")
    for i, lines in {4: ["Integrated", " tax"], 5: ["Central ", "tax"], 6: ["State/UT ", "tax"], 7: ["Cess"]}.items():
        for k, txt in enumerate(lines):
            s.text(e6[i] + 4.5, top6 + 19.6 + k * 10.6, txt, "Roboto-Medium", 9)
    for i in range(12):
        if i in (5, 6, 7):
            s.line(e6[i], top6 + 15.1, e6[i], top6 + 68.8)
        else:
            s.line(e6[i], top6 - 0.5, e6[i], top6 + 68.8)
    s.line(20.0, top6, 574.3, top6)
    s.line(e6[4] - 0.5, top6 + 15.6, e6[8] - 0.5, top6 + 15.6)
    t = top6 + 68.3
    full = [(0, 10)]
    r0 = lambda v: f"{round(v):.2f}"  # noqa: E731  (6.1 is in whole rupees)
    cash = {k: round(v) - round(itc[k]) for k, v in (("i", igst), ("c", cgst), ("s", sgst))}
    t = s.grid(e6, t, [
        {"bold": True, "span": full, "cells": ["(A) Other than reverse charge"] + [""] * 10},
        {"cells": ["Integrated tax", r0(igst), z, r0(igst), r0(itc["i"]), z, z, dash, f"{cash['i']:.2f}", z, dash]},
        {"cells": ["Central tax", r0(cgst), z, r0(cgst), z, r0(itc["c"]), dash, dash, f"{cash['c']:.2f}", z, z]},
        {"cells": ["State/UT tax", r0(sgst), z, r0(sgst), z, dash, r0(itc["s"]), dash, f"{cash['s']:.2f}", z, z]},
        {"cells": ["Cess", z, z, z, dash, dash, dash, z, z, z, dash]},
        {"bold": True, "span": full, "cells": ["(B) Reverse charge and supplies made u/s 9(5)"] + [""] * 10},
        *[{"cells": [lab, z, z, z, dash, dash, dash, dash, z, dash, dash]}
          for lab in ("Integrated tax", "Central tax", "State/UT tax", "Cess")]])
    t = band(t + 20.5, "Breakup of tax liability declared (for interest computation)")
    t = s.grid(e4, t, [
        {"head": True, "cells": ["Period", "Integrated tax", "Central tax", "State/UT tax", "Cess"]},
        {"cells": [f"{D.FULLMON[m - 1]} {y}", r0(igst), r0(cgst), r0(sgst), z]}])
    t += 17.2
    s.text(20.0, t, "Verification:", "Roboto-Medium", 10)
    s.text(20.0, t + 11.5, "I hereby solemnly affirm and declare that the information given herein above is true and "
                           "correct to the best of my knowledge and belief and ", "Roboto-Regular", 9)
    s.text(20.0, t + 22.1, "nothing has been concealed there from.", "Roboto-Regular", 9)
    s.text(20.0, t + 48.6, f"Date: {dmy(filed)}", "Roboto-Regular", 9)   # on the signatory line's baseline
    for k, (dt, txt) in enumerate(((48.6, "Name of Authorized Signatory"), (63.2, e.persons[0].name.upper()),
                                   (81.7, "Designation /Status"), (96.3, "DIRECTOR"))):
        s.text(301.6, t + dt, txt, "Roboto-Regular", 9)
    return s.render()


# GSTR-1 rows: ("sec", title) | ("sub", title) | ("note", text) | ("blank",) | (label, x, records, doc, cols, grey)
# cols: which of value/igst/cgst/sgst/cess print ("v", "i", "c", "s", "e"); grey: {col: "d"ark or "l"ight};
# "nil" rows have no record and document cells.
_G1_ALL, _G1_INTER = "vicse", "vie"
_DARK_CS = {5: "d", 6: "d"}
_DARK_TAX = {4: "d", 5: "d", 6: "d", 7: "d"}
_LIGHT_TAX = {4: "l", 5: "l", 6: "l", 7: "l"}
_LIGHT_ALL = {3: "l", 4: "l", 5: "l", 6: "l", 7: "l"}


def _g1_rows(rec: int) -> list:
    amend = lambda doc, cols, grey: [("Amended amount - Total", 44.3, 0, doc, cols, grey),  # noqa: E731
                                     ("Net differential amount (Amended - Original)", 44.3, None, "", cols, grey)]
    exp = lambda x, doc: [("-  EXPWP", x, 0, doc, _G1_INTER, _DARK_CS), ("-  EXPWOP", x, 0, doc, "v", _DARK_TAX)]  # noqa: E731
    sez = lambda x, doc: [("-  SEZWP", x, 0, doc, _G1_INTER, _DARK_CS), ("-  SEZWOP", x, 0, doc, "v", _DARK_TAX)]  # noqa: E731
    net_cd = ("Net Total (Debit notes – Credit notes)")
    net_acd = "Net total (Net Amended Debit notes - Net Amended Credit notes)"
    return [
        ("sec", "4A - Taxable outward supplies made to registered persons (other than reverse charge supplies) including "
                "supplies made through e-commerce operator attracting TCS - B2B Regular"),
        ("Total", 44.3, rec, "Invoice", "4A", {}), ("blank",),
        ("sec", "4B - Taxable outward supplies made to registered persons attracting tax on reverse charge - B2B Reverse charge"),
        ("Total", 44.3, 0, "Invoice", _G1_ALL, _LIGHT_TAX), ("blank",),
        ("sec", "5 - Taxable outward inter-state supplies made to unregistered persons (where invoice value is more than "
                "Rs. 1 lakh) including supplies made through e-commerce operator, rate wise - B2CL (Large)"),
        ("Total", 44.3, 0, "Invoice", _G1_INTER, _DARK_CS), ("blank",),
        ("sec", "6A – Exports (with/without payment)"),
        ("Total", 44.3, 0, "Invoice", _G1_INTER, _DARK_CS), *exp(59.3, "Invoice"), ("blank",),
        ("sec", "6B - Supplies made to SEZ unit or SEZ developer - SEZWP/SEZWOP"),
        ("Total", 44.3, 0, "Invoice", _G1_INTER, _DARK_CS), *sez(59.3, "Invoice"), ("blank",),
        ("sec", "6C - Deemed Exports – DE"), ("Total", 44.3, 0, "Invoice", _G1_ALL, {}), ("blank",),
        ("sec", "7- Taxable supplies (Net of debit and credit notes) to unregistered persons (other than the supplies "
                "covered in Table 5) including supplies made through e-commerce operator attracting TCS - B2CS (Others)"),
        ("Total", 44.3, 0, "Net Value", _G1_ALL, {}), ("blank",),
        ("sec", "8 - Nil rated, exempted and non GST outward supplies"),
        *[("nil", lab) for lab in ("Total", "-  Nil", "-  Exempted", "-  Non-GST")], ("blank",),
        ("sec", "9A - Amendment to taxable outward supplies made to registered person in returns of earlier tax periods "
                "in table 4 - B2B Regular"), *amend("Invoice", _G1_ALL, {}), ("blank",),
        ("sec", "9A - Amendment to taxable outward supplies made to registered person in returns of earlier tax periods "
                "in table 4 - B2B Reverse charge"), *amend("Invoice", _G1_ALL, _LIGHT_TAX), ("blank",),
        ("sec", "9A - Amendment to Inter-State supplies made to unregistered person (where invoice value is more than "
                "Rs. 1 lakh) in returns of earlier tax periods in table 5 - B2CL (Large)"),
        *amend("Invoice", _G1_INTER, _DARK_CS), ("blank",),
        ("sec", "9A - Amendment to Export supplies in returns of earlier tax periods in table 6A (EXPWP/EXPWOP)"),
        ("Amended amount - Total", 44.3, 0, "Invoice", _G1_INTER, _DARK_CS),
        ("Net differential amount (Amended - Original) - Total", 44.3, None, "", _G1_INTER, _DARK_CS),
        *exp(59.3, "Invoice"), ("blank",),
        ("sec", "9A - Amendment to supplies made to SEZ units or SEZ developers in returns of earlier tax periods in "
                "table 6B (SEZWP/SEZWOP)"),
        ("Amended amount - Total", 44.3, 0, "Invoice", _G1_INTER, _DARK_CS),
        ("Net differential amount (Amended - Original) - Total", 44.3, None, "", _G1_INTER, _DARK_CS),
        *sez(59.3, "Invoice"), ("blank",),
        ("sec", "9A - Amendment to Deemed Exports in returns of earlier tax periods in table 6C (DE)"),
        *amend("Invoice", _G1_ALL, {}), ("blank",),
        ("sec", "9B - Credit/Debit Notes (Registered) – CDNR"),
        ("Total - Net off debit/credit notes (Debit notes - Credit notes)", 44.3, 0, "Note", _G1_ALL, {}),
        ("sub", "Credit / Debit notes issued to registered person for taxable outward supplies in table 4 other than "
                "table 6 - B2B Regular"), (net_cd, 74.3, 0, "Note", _G1_ALL, {}),
        ("sub", "Credit / Debit notes issued to registered person for taxable outward supplies in table 4 other than "
                "table 6 - B2B Reverse charge"), (net_cd, 74.3, 0, "Note", _G1_ALL, _LIGHT_TAX),
        ("sub", "Credit / Debit notes issued to registered person for taxable outward supplies in table 6B - SEZWP/SEZWOP"),
        (net_cd, 74.3, 0, "Note", _G1_INTER, _DARK_CS),
        ("sub", "Credit / Debit notes issued to registered person for taxable outward supplies in table 6C – DE"),
        (net_cd, 74.3, 0, "Note", _G1_ALL, {}), ("blank",),
        ("sec", "9B - Credit/Debit Notes (Unregistered) – CDNUR"),
        ("Total - Net off debit/credit notes (Debit notes - Credit notes)", 44.3, 0, "Note", _G1_INTER, _DARK_CS),
        ("note", "Unregistered Type "), ("-  B2CL", 74.3, 0, "Note", _G1_INTER, _DARK_CS), *exp(74.3, "Note"),
        ("blank",),
        ("sec", "9C - Amended Credit/Debit Notes (Registered) - CDNRA    "),
        ("Amended amount - Total", 44.3, 0, "Note", _G1_ALL, {}),
        ("Net Differential amount (Net Amended Debit notes - Net Amended Credit notes) - Total", 44.3, None, "", _G1_ALL, {}),
        ("sub", "Amended Credit / Debit notes issued to registered person for taxable outward supplies in table 4 other "
                "than table 6 - B2B Regular"), (net_acd, 74.3, 0, "Note", _G1_ALL, {}),
        ("sub", "Amended Credit / Debit notes issued to registered person for taxable outward supplies in table 4 other "
                "than table 6 - B2B Reverse charge"), (net_acd, 74.3, 0, "Note", _G1_ALL, _LIGHT_TAX),
        ("sub", "Amended Credit / Debit notes issued to registered person for taxable outward supplies in table 6B - "
                "SEZWP/SEZWOP"), (net_acd, 74.3, 0, "Note", _G1_INTER, _DARK_CS),
        ("sub", "Amended Credit / Debit notes issued to registered person for taxable outward supplies in table 6C – DE"),
        (net_acd, 74.3, 0, "Note", _G1_ALL, {}), ("blank",),
        ("sec", "9C - Amended Credit/Debit Notes (Unregistered) - CDNURA"),
        ("Amended amount - Total", 44.3, 0, "Note", _G1_INTER, _DARK_CS),
        ("Net Differential amount (Net Amended Debit notes - Net Amended Credit notes) - Total", 44.3, None, "",
         _G1_INTER, _DARK_CS),
        ("note", "Unregistered Type "), ("-  B2CL", 74.3, 0, "Note", _G1_INTER, _DARK_CS), *exp(74.3, "Note"),
        ("blank",),
        ("sec", "10 - Amendment to taxable outward supplies made to unregistered person in returns for earlier tax periods "
                "in table 7 including supplies made through e-commerce operator attracting TCS - B2C (Others)"),
        *amend("Net Value", _G1_ALL, {}), ("blank",),
        ("sec", "11A(1), 11A(2) - Advances received for which invoice has not been issued (tax amount to be added to the "
                "output tax liability) (Net of refund vouchers, if any)"),
        ("Total", 44.3, 0, "Net Value", _G1_ALL, {}), ("blank",),
        ("sec", "11B(1), 11B(2) - Advance amount received in earlier tax period and adjusted against the supplies being "
                "shown in this tax period in Table Nos. 4, 5, 6 and 7 (Net of refund vouchers, if any)"),
        ("Total", 44.3, 0, "Net Value", _G1_ALL, {}), ("blank",),
        ("sec", "11A - Amendment to advances received in returns for earlier tax periods in table 11A(1), 11A(2) (Net of "
                "refund vouchers, if any)"),
        ("Amended amount - Total", 44.3, 0, "Net Value", _G1_ALL, {}), ("Total", 44.3, None, "", _G1_ALL, {}), ("blank",),
        ("sec", "11B - Amendment to advances adjusted in returns for earlier tax periods in table 11B(1), 11B(2) (Net of "
                "refund vouchers, if any)"),
        ("Amended amount - Total", 44.3, 0, "Net Value", _G1_ALL, {}), ("Total", 44.3, None, "", _G1_ALL, {}), ("blank",),
        ("sec", "12 - HSN-wise summary of outward supplies"),
        ("Total", 44.3, "hsn", "NA", "4A", _LIGHT_ALL), ("B2B Total", 44.3, "hsn", "NA", "4A", _LIGHT_ALL),
        ("B2C Total", 44.3, 0, "NA", _G1_ALL, _LIGHT_ALL), ("blank",),
        ("sec", "13 - Documents issued"), ("docs", rec), ("blank",),
        ("sec", "14 - Supplies made through E-Commerce Operators"),
        *[(lab, 44.3, 0, "Net Value", _G1_ALL, _LIGHT_ALL) for lab in
          ("Total", "(a) Liable to collect tax u/s 52", "(b) Liable to pay tax u/s 9(5)")], ("blank",),
        ("sec", "14A - Amended Supplies made through E-Commerce Operators"),
        ("Amended amount – Total", 44.3, 0, "Net Value", _G1_ALL, _LIGHT_ALL),
        ("Net differential amount (Amended - Original)", 44.3, 0, "Net Value", _G1_ALL, _LIGHT_ALL),
        ("note-grey", "(a) Liable to collect tax u/s 52"),
        ("Amended amount – Total", 44.3, 0, "Net Value", _G1_ALL, _LIGHT_ALL),
        ("Net differential amount (Amended - Original)", 44.3, 0, "Net Value", _G1_ALL, _LIGHT_ALL),
        ("note-grey", "(b) Liable to pay tax u/s 9(5)"),
        ("Amended amount – Total", 44.3, 0, "Net Value", _G1_ALL, _LIGHT_ALL),
        ("Net differential amount (Amended - Original)", 44.3, 0, "Net Value", _G1_ALL, _LIGHT_ALL), ("blank",),
        ("sec", "15 - Supplies U/s 9(5) "),
        ("Total", 59.3, 0, "Document/Net \nValue", _G1_ALL, {}),
        ("-  For Registered Recipients", 59.3, 0, "Document", _G1_ALL, {}),
        ("  -     Regular", 55.6, 0, "Document", _G1_ALL, {}), ("  -     DE", 55.6, 0, "Document", _G1_ALL, {}),
        ("  -     SEZWP", 55.6, 0, "Document", _G1_INTER, _DARK_CS), ("  -     SEZWOP", 55.6, 0, "Document", "v", _DARK_TAX),
        ("  -  For Unregistered Recipient", 55.6, 0, "Net Value", _G1_ALL, {}), ("blank",),
        ("sec", "15A (I) - Amended Supplies U/s 9(5) – For Registered Recipients"),
        ("Amended amount - Total", 59.3, 0, "Document", _G1_ALL, {}),
        ("Net differential amount (Amended - Original)", 59.3, 0, "Document", _G1_ALL, {}),
        ("  -     Regular", 55.6, 0, "Document", _G1_ALL, {}), ("  -     DE", 55.6, 0, "Document", _G1_ALL, {}),
        ("  -     SEZWP", 55.6, 0, "Document", _G1_INTER, _DARK_CS), ("  -     SEZWOP", 55.6, 0, "Document", "v", _DARK_TAX),
        ("blank",),
        ("sec", "15A (II) - Amended Supplies U/s 9(5) – For Unregistered Recipients"),
        ("Amended amount - Total", 59.3, 0, "Net Value", _G1_ALL, {}),
        ("Net differential amount (Amended - Original)", 59.3, 0, "Net Value", _G1_ALL, {}), ("blank",),
        ("liability",)]


def gstr_1(e: D.Entity = BASE, *, month, taxable: int, filed_on: str | None = None) -> bytes:
    """The GST portal's filed GSTR-1 (View/Download, landscape A4): drawn at the template's measured positions, in its
    fonts (Roboto), colours and 0.3-pt rules. The navy column header repeats on every page; each table has its peach
    title row and its Total line; cells that do not apply are grey. The portal's "FILED" watermark is not drawn
    (CLAUDE.md rule 8)."""
    y0, m, fy, ny, nm = _gst_period(month)
    filed = filed_on or f"11 {MONTHS[nm - 1]} {ny}"
    inter = round(taxable * 0.4, 2)
    tax = {"v": taxable, "i": round(inter * 0.18, 2), "c": round((taxable - inter) * 0.09, 2), "e": 0.0}
    tax["s"] = tax["c"]
    rec = 30 + int(num("r1n", y0, m, digits=2)) % 25
    PEACH, NAVY, DARK, LIGHT = "#FBE4D5", "#002060", "#949494", "#D3D0D0"
    edges = [40.1, 257.0, 314.0, 377.9, 462.7, 547.4, 632.2, 717.0, 801.7]
    s = TP.Sheet(841.9, 595.3, footer_x=40.0, footer_y=12.0)
    ip = f"IP Address: 10.{num('ip', y0, m, digits=2)[:2].lstrip('0') or '1'}.{int(num('ip2', y0, m, digits=3)) % 250}.{int(num('ip3', y0, m, digits=3)) % 250}"
    lw = 0.3

    def hline(y, x0=40.1, x1=801.7):
        s.line(x0, y, x1, y, lw)

    def vlines(top, bottom, xs):
        for x in xs:
            s.line(x, top, x, bottom, lw)

    def head(top):
        for a, b in zip(edges, edges[1:]):
            s.fill(a + 0.2, top, b - 0.1, top + 25.4, NAVY)
        w = "#FFFFFF"
        for i, txt in ((0, "Description"), (3, "Value (₹)"), (4, "Integrated Tax (₹)"), (5, "Central Tax (₹)"),
                       (6, "State/UT Tax (₹)"), (7, "Cess (₹)")):
            s.text((edges[i] + edges[i + 1]) / 2, top + 8.6, txt, "Roboto-Medium", 9, align="c", colour=w)
        for i, (a, b) in ((1, ("No. of ", "records")), (2, ("Document ", "Type"))):
            s.text((edges[i] + edges[i + 1]) / 2, top + 3.6, a.strip(), "Roboto-Medium", 9, align="c", colour=w)
            s.text((edges[i] + edges[i + 1]) / 2, top + 14.2, b, "Roboto-Medium", 9, align="c", colour=w)
        hline(top)
        hline(top + 25.4)
        vlines(top, top + 25.4, edges)
        return top + 25.4

    def page_end():
        s.text(801.9, 556.7, ip, "Roboto-Regular", 8, align="r")

    # --- page 1 heading
    s.text(420.9, 47.1, "FORM GSTR-1", "Roboto-Medium", 12, align="c")
    s.text(420.9, 66.1, "[See rule 59(1)]", "Roboto-Medium", 12, align="c")
    s.text(420.9, 85.2, "Details of outward supplies of goods or services", "Roboto-Medium", 12, align="c")
    for k, (lab, val) in enumerate((("Financial year", fy), ("Tax period", D.MON[m - 1]))):
        t = 102.3 + k * 13.1
        s.fill(640.3, t, 728.0, t + 13.1, PEACH)
        s.text(644.3, t + 3.2, lab, "Roboto-Regular", 7.5)
        s.text(732.3, t + 3.2, val, "Roboto-Regular", 7.5)
        hline(t, 640.1)
        vlines(t, t + 13.1, (640.1, 728.2, 801.7))
    hline(128.5, 640.1)
    arn = f"AA27{m:02d}{y0 % 100:02d}{num('r1', y0, m)}"
    ident = [("1", "GSTIN", None, e.gstin), ("2", "(a)", "Legal name of the registered person", e.name.upper()),
             ("", "(b)", "Trade name if any", e.name.upper()), ("", "(c)", "ARN", arn), ("", "(d)", "ARN date", dmy(filed))]
    for k, (no, a, lab, val) in enumerate(ident):
        t = 143.8 + k * 13.1
        if lab is None:
            s.fill(85.0, t, 356.3, t + 13.1, PEACH)
            vlines(t, t + 13.1, (40.1, 84.9, 356.4, 801.7))
        else:
            s.fill(85.0, t, 129.4, t + 13.1, PEACH)
            s.fill(129.7, t, 356.3, t + 13.1, PEACH)
            s.text(133.7, t + 3.2, lab, "Roboto-Regular", 7.5)
            vlines(t, t + 13.1, (40.1, 84.9, 129.6, 356.4, 801.7))
        s.text(44.3, t + 3.2, no, "Roboto-Regular", 7.5)
        s.text(89.0, t + 3.2, a, "Roboto-Regular", 7.5)
        s.text(360.6, t + 3.2, val, "Roboto-Regular", 7.5)
        hline(t, 40.1 if k <= 1 else 84.9)
    hline(209.3)
    y = head(224.6)
    amounts = lambda cols: {"v": 3, "i": 4, "c": 5, "s": 6, "e": 7}  # noqa: E731
    cidx = {"v": 3, "i": 4, "c": 5, "s": 6, "e": 7}

    def money(v):
        return rs2(v)

    for row in _g1_rows(rec):
        lines = 1
        if row[0] not in ("sec", "sub", "note", "note-grey", "blank", "nil", "docs", "liability"):
            label = row[0]
            lines = len(TP.Sheet._wrap(label, "Roboto-Regular", 7.5, 257.0 - row[1] - 4, by_char=False))
            lines = max(lines, len(str(row[3]).split("\n")))
        h = 13.087 if lines == 1 else 21.9
        if y + h > 551.2:
            page_end()
            s.page()
            y = head(40.1)
        kind = row[0]
        if kind == "blank":
            s.text(42.4, y + 3.2, " ", "Roboto-Regular", 7.5)
            vlines(y, y + h, (40.1, 801.7))
        elif kind in ("sec", "sub", "note", "note-grey"):
            if kind == "sec":
                s.fill(40.3, y, 801.6, y + h, PEACH)
            if kind == "note-grey":
                for i in range(3, 8):
                    s.fill(edges[i] + 0.3, y, edges[i + 1] - 0.1, y + h, LIGHT)
                vlines(y, y + h, edges)
                s.text(44.3, y + 3.2, row[1], "Roboto-Regular", 7.5)
            else:
                s.text(44.3 if kind == "sec" else 59.3, y + 3.2, row[1], "Roboto-Regular", 7.5,
                       colour=NAVY if kind in ("sec", "sub") else "#000000")
                vlines(y, y + h, (40.1, 801.7))
        elif kind == "nil":
            for i in range(4, 8):
                s.fill(edges[i] + 0.1, y, edges[i + 1] - 0.1, y + h, DARK)
            s.text(44.3 if row[1] == "Total" else 59.3, y + 3.2, row[1], "Roboto-Regular", 7.5)
            s.text(edges[4] - 4.2, y + 3.2, "0.00", "Roboto-Regular", 7.5, align="r")
            vlines(y, y + h, (40.1, 377.9, 462.7, 547.4, 632.2, 717.0, 801.7))
        elif kind == "docs":
            for i in range(3, 8):
                s.fill(edges[i] + 0.1, y, edges[i + 1] - 0.1, y + h, DARK)
            s.text(44.3, y + 3.2, "Net issued documents", "Roboto-Regular", 7.5)
            s.text((edges[1] + edges[2]) / 2, y + 3.2, str(row[1]), "Roboto-Regular", 7.5, align="c")
            s.text((edges[2] + edges[3]) / 2, y + 3.2, "All Documents", "Roboto-Regular", 7.5, align="c")
            vlines(y, y + h, edges)
        elif kind == "liability":
            for a, b in ((40.3, 377.7), *[(edges[i] + 0.1, edges[i + 1] - 0.1) for i in range(3, 8)]):
                s.fill(a, y, b, y + h, "#ED7D31")
            s.text(44.3, y + 3.2, "Total Liability (Outward supplies other than Reverse charge)", "Roboto-Regular", 7.5)
            for k in "vicse":
                s.text(edges[cidx[k] + 1] - 4.2, y + 3.2, money(tax[k]), "Roboto-Regular", 7.5, align="r")
            vlines(y, y + h, (40.1, 377.9, 462.7, 547.4, 632.2, 717.0, 801.7))
        else:
            label, x, records, doc, cols, grey = row
            filled = cols == "4A"
            if filled:
                cols = "vicse"
            for i, shade in grey.items():
                s.fill(edges[i] + 0.1, y, edges[i + 1] - 0.1, y + h, DARK if shade == "d" else LIGHT)
            for k, part in enumerate(TP.Sheet._wrap(label, "Roboto-Regular", 7.5, 257.0 - x - 4, by_char=False)):
                s.text(x, y + 3.2 + k * 8.0, part, "Roboto-Regular", 7.5)
            if records is not None:
                n = rec if records == "hsn" and False else (3 if records == "hsn" else records)
                s.text((edges[1] + edges[2]) / 2, y + 3.2, str(n), "Roboto-Regular", 7.5, align="c")
            for k, part in enumerate(str(doc).split("\n")):
                s.text((edges[2] + edges[3]) / 2, y + 3.2 + k * 8.0, part.strip(), "Roboto-Regular", 7.5, align="c")
            for k in cols:
                v = tax[k] if filled else 0.0
                s.text(edges[cidx[k] + 1] - 4.2, y + 3.2, money(v), "Roboto-Regular", 7.5, align="r")
            vlines(y, y + h, edges)
        hline(y)
        hline(y + h)
        y += h
    t = y + 16.7
    s.text(40.0, t, "Verification:", "Roboto-Medium", 9)
    s.text(40.0, t + 10.5, "I hereby solemnly affirm and declare that the information given herein above is true and "
                           "correct to the best of my knowledge and belief and nothing has been concealed there from and "
                           "in case ", "Roboto-Regular", 9)
    s.text(40.0, t + 21.1, "of any reduction in output tax liability the benefit thereof has been/ will be passed on to "
                           "the recipient of supply.", "Roboto-Regular", 9)
    s.text(40.0, t + 41.6, f"Date: {dmy(filed)}", "Roboto-Regular", 9)
    s.text(40.0, t + 52.2, "Signature", "Roboto-Regular", 9)
    page_end()
    s.page()
    s.text(40.0, 41.5, "Name of Authorized Signatory", "Roboto-Regular", 9)
    s.text(40.0, 52.1, e.persons[0].name.upper(), "Roboto-Regular", 9)
    s.text(40.0, 62.6, "Designation/Status: DIRECTOR", "Roboto-Regular", 9)
    page_end()
    return s.render()


YEAR = {   # each year's own figures, so a year's column reads the same in its own report and in the next year's
    2026: {"f": 1.00, "res": 41_200_000, "cash": 9_500_000, "ltb": 16_250_000, "ppe": 29_450_000},
    2025: {"f": 0.93, "res": 35_900_000, "cash": 8_200_000, "ltb": 19_800_000, "ppe": 30_800_000},
    2024: {"f": 0.86, "res": 31_100_000, "cash": 7_400_000, "ltb": 23_000_000, "ppe": 31_900_000},
    2023: {"f": 0.80, "res": 27_000_000, "cash": 6_900_000, "ltb": 25_500_000, "ppe": 32_700_000},
}
ORDINAL_WORDS = ["", "FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH", "ELEVENTH",
                 "TWELFTH", "THIRTEENTH", "FOURTEENTH", "FIFTEENTH"]


def _bs_year(fy_end: int, *, reserves: int | None = None, cash: int | None = None, borrowings: int | None = None) -> dict:
    """One year's balance sheet, balanced: plant and equipment and the current assets set the total, and other current
    liabilities take up the difference (so a negative net worth is carried by the liabilities)."""
    y = YEAR.get(fy_end, YEAR[2023])
    f = y["f"]
    ca = {"inv": round(21_600_000 * f), "tr": round(31_900_000 * f), "cash": y["cash"] if cash is None else cash,
          "stla": round(2_100_000 * f)}
    total = y["ppe"] + sum(ca.values())
    fixed = {"sc": 5_000_000, "res": y["res"] if reserves is None else reserves, "ltb": y["ltb"] if borrowings is None else borrowings,
             "stb": round(12_000_000 * f), "tp": round(14_800_000 * f), "stp": round(1_900_000 * f)}
    fixed["ocl"] = total - sum(fixed.values())
    return {**ca, **fixed, "ppe": y["ppe"], "total": total}


def audited_statements(e: D.Entity = BASE, *, revenue: int, profit_before_tax: int, fy_end: int = 2026, name: str | None = None,
                       cash: int | None = None, borrowings: int | None = None, auditor: str = "",
                       signed_on: str = "27 August 2026") -> bytes:
    return annual_report(e, revenue=revenue, profit_before_tax=profit_before_tax, fy_end=fy_end, name=name, cash=cash,
                         borrowings=borrowings, signed_on=signed_on)


# --- documents with no type in the app yet --------------------------------------------------------------------------

def udyam_certificate(e: D.Entity = BASE, *, owner: str | None = None, enterprise_type: str = "Small",
                      urn: str = "UDYAM-MH-33-0012345", activity: str = "MANUFACTURING", unit: str = "1. MAIN WORKS, TALOJA",
                      registered: str = "14/08/2020", dic: str = "RAIGAD (MAHARASHTRA)", dfo: str = "MUMBAI",
                      nic: tuple[str, str, str] = ("25 - Fabricated metal products", "2511 - Structural metal products",
                                                   "Manufacturing")) -> bytes:
    """A Udyam registration certificate's particulars (Ministry of MSME): URN, enterprise name and type by year, major
    activity, social category, address, dates, NIC codes. No emblem and no QR code. The defaults are the pack's
    manufacturer; another enterprise passes its own activity, unit, district and NIC code."""
    d = Doc()
    d.write("Government of India", font="Helvetica-Bold", size=10, align="c", lead=12)
    d.write("Ministry of Micro, Small and Medium Enterprises", size=9.5, align="c", lead=16)
    d.write("UDYAM REGISTRATION CERTIFICATE", font="Helvetica-Bold", size=13, align="c", lead=20)
    d.kv([("UDYAM REGISTRATION NUMBER", urn), ("NAME OF ENTERPRISE", e.name.upper())], x2=250, size=9.5, lead=15)
    d.write("TYPE OF ENTERPRISE", font="Helvetica-Bold", size=9, lead=12)
    d.table([("S.No.", L, 90, "l"), ("Classification Year", 90, 230, "l"), ("Enterprise Type", 230, 370, "l"), ("Classification Date", 370, R, "l")],
            [["1", "2026-27", enterprise_type, "01/04/2026"], ["2", "2025-26", enterprise_type, "01/04/2025"]], size=8.6, row_h=13)
    d.down(6)
    d.kv([("MAJOR ACTIVITY", activity), ("SOCIAL CATEGORY OF ENTREPRENEUR", "GENERAL"),
          ("NAME OF ENTREPRENEUR", (owner or e.persons[0].name).upper()), ("NAME OF UNIT(S)", unit),
          ("OFFICIAL ADDRESS OF ENTERPRISE", halves(e.office)[0]), ("", halves(e.office)[1]),
          ("DATE OF INCORPORATION / REGISTRATION", dmy(e.incorporated)),
          ("DATE OF COMMENCEMENT OF PRODUCTION/BUSINESS", dmy(e.incorporated)), ("DATE OF UDYAM REGISTRATION", registered),
          ("DISTRICT INDUSTRIES CENTRE", dic), ("MSME-DFO", dfo)], x2=310, size=8.8, lead=13)
    d.down(4)
    d.write("NATIONAL INDUSTRY CLASSIFICATION CODE(S)", font="Helvetica-Bold", size=9, lead=12)
    d.table([("S.No.", L, 85, "l"), ("NIC 2 Digit", 85, 220, "l"), ("NIC 4 Digit", 220, 360, "l"), ("Activity", 360, R, "l")],
            [["1", *nic]], size=8.2, row_h=13)
    d.down(8)
    d.para("Disclaimer: This is a system-generated certificate based on the information provided by the entrepreneur; the "
           "registration can be verified on the Udyam Registration portal.", size=8, lead=11)
    return d.render()


def provisional_financials(e: D.Entity = BASE, *, revenue: int, profit_before_tax: int, period_end: str = "30.09.2026") -> bytes:
    """Provisional (unaudited) statements for the half year, under a chartered accountant's compilation certificate on
    the firm's letterhead, with UDIN."""
    d = Doc()
    d.write(AUDITOR[0].upper(), font="Helvetica-Bold", size=12, align="c", lead=13)
    d.write(f"{AUDITOR[1]}  |  FRN {AUDITOR[2]}  |  402, Nariman Chambers, Fort, Mumbai 400001", size=8, align="c", lead=8)
    d.hr(1.0)
    d.write("TO WHOMSOEVER IT MAY CONCERN", font="Helvetica-Bold", size=10, align="c", lead=14)
    d.write("CERTIFICATE ON PROVISIONAL FINANCIAL STATEMENTS", font="Helvetica-Bold", size=10, align="c", lead=18)
    d.para(f"We have compiled the provisional financial statements of {e.name} (CIN {e.cin}) for the period from 1st April "
           f"2026 to {period_end}, comprising the provisional balance sheet and statement of profit and loss annexed, on the "
           "basis of the books of account and the information and explanations given to us by the management, in accordance "
           "with the Standard on Related Services (SRS) 4410, Compilation Engagements.", size=9.6, lead=13)
    d.para("These statements are unaudited and provisional. Management is responsible for them; we have not audited or reviewed "
           "them and accordingly express no opinion on them. They are subject to change on audit.", size=9.6, lead=13)
    d.down(8)
    d.write(f"For {AUDITOR[0]}, {AUDITOR[1]}", size=9.6, lead=13)
    d.write(f"Sd/-  {AUDITOR[3]}, Partner, Membership No. {AUDITOR[4]}", size=9.6, lead=13)
    d.write(f"UDIN: 26{AUDITOR[4]}BKPROV7781  |  Place: Mumbai  |  Date: 18 October 2026", size=9.6, lead=20)
    half_rev, half_pbt = round(revenue * 0.53), round(profit_before_tax * 0.5)
    d.write(f"PROVISIONAL BALANCE SHEET AS AT {period_end} (UNAUDITED)", font="Helvetica-Bold", size=9.6, align="c", lead=14)
    b = _bs_year(2026, reserves=41_200_000 + round(half_pbt * 0.75), cash=10_100_000, borrowings=14_400_000)
    d.table([("Particulars", L, 380, "l"), (f"As at {period_end} (Rs.)", 380, R, "r")],
            [["Share capital", D.inr(b["sc"])], ["Reserves and surplus", D.inr(b["res"])], ["Long-term borrowings", D.inr(b["ltb"])],
             ["Short-term borrowings", D.inr(b["stb"])], ["Trade payables and other liabilities", D.inr(b["tp"] + b["ocl"] + b["stp"])],
             ("bold", ["Total", D.inr(b["total"])]), ["Property, plant and equipment", D.inr(b["ppe"])],
             ["Inventories", D.inr(b["inv"])], ["Trade receivables", D.inr(b["tr"])], ["Cash and bank balances", D.inr(b["cash"])],
             ["Loans and advances", D.inr(b["stla"])], ("bold", ["Total", D.inr(b["total"])])], size=8.6, row_h=12.5)
    d.down(8)
    d.write(f"PROVISIONAL STATEMENT OF PROFIT AND LOSS FOR THE PERIOD 01.04.2026 TO {period_end} (UNAUDITED)",
            font="Helvetica-Bold", size=9.6, align="c", lead=14)
    d.table([("Particulars", L, 380, "l"), ("Amount (Rs.)", 380, R, "r")],
            [["Revenue from operations", D.inr(half_rev)], ["Other income", D.inr(round(half_rev * 0.004))],
             ["Total expenses", D.inr(half_rev + round(half_rev * 0.004) - half_pbt)], ("bold", ["Profit before tax", inr(half_pbt)]),
             ["Provision for tax", D.inr(half_pbt - round(half_pbt * 0.75))], ("bold", ["Profit after tax", inr(round(half_pbt * 0.75))])],
            size=8.6, row_h=12.5)
    return d.render()


def stock_statement(e: D.Entity = BASE, *, as_on: str = "31 October 2026", factor: float = 1.0) -> bytes:
    """The monthly stock and book-debts statement for the cash credit: stock by category less creditors, book debts by age,
    the bank's margins and the drawing power."""
    rm, wip, fg, stores = (round(x * factor) for x in (9_800_000, 4_100_000, 6_900_000, 800_000))
    cred = round(14_800_000 * factor)
    bd90, bdover = round(28_400_000 * factor), round(3_500_000 * factor)
    stock = rm + wip + fg + stores
    paid = stock - cred
    dp_stock, dp_bd = round(paid * 0.75), round(bd90 * 0.60)
    d = Doc()
    letterhead(d, e)
    d.write(f"STATEMENT OF STOCK AND BOOK DEBTS AS ON {as_on.upper()}", font="Helvetica-Bold", size=10.5, align="c", lead=16)
    d.kv([("To", f"The Branch Manager, {e.bank}, {e.branch} Branch"), ("Cash credit account", "602030088812"),
          ("Sanctioned limit", "Rs. 1,20,00,000")], x2=170, size=9, lead=12)
    d.down(4)
    rows = [["Raw materials", D.inr(rm)], ["Work in progress", D.inr(wip)], ["Finished goods", D.inr(fg)],
            ["Stores and spares", D.inr(stores)], ("bold", ["Total stock (A)", D.inr(stock)]),
            ["Less: Sundry creditors for goods (B)", D.inr(cred)], ("bold", ["Paid stock (A - B)", D.inr(paid)]),
            ["Book debts up to 90 days (C)", D.inr(bd90)], ["Book debts over 90 days (not eligible)", D.inr(bdover)],
            ["Drawing power on paid stock (margin 25%)", D.inr(dp_stock)], ["Drawing power on book debts (margin 40%)", D.inr(dp_bd)],
            ("bold", ["Drawing power", D.inr(min(dp_stock + dp_bd, 12_000_000))])]
    d.table([("Particulars", L, 380, "l"), ("Amount (Rs.)", 380, R, "r")], rows, size=8.8, row_h=13)
    d.down(8)
    d.para("We certify that the goods hypothecated to the bank are our absolute property, free from any other charge, are "
           "fully insured, and that the book debts are not more than 90 days old except as shown above.", size=9, lead=12)
    d.down(8)
    d.write(f"For {e.name}", size=9.5, lead=14)
    d.kv([("Signature:", "Sd/-"), ("Name:", e.persons[0].name), ("Date:", as_on)], x2=L + 85, size=9.5, lead=13)
    return d.render()


def valuation_report(e: D.Entity = BASE, *, inspected_on: str = "06 October 2026", market_value: int = 6_85_00_000) -> bytes:
    """A valuation report for an immovable property in a bank's Appendix-I format (S.No | Particulars | Content):
    introduction, physical characteristics with boundaries, legal aspects, valuation and the valuer's declaration."""
    d = Doc()
    d.write(f"{VALUER[0]}", font="Helvetica-Bold", size=11, align="c", lead=12)
    d.write(f"{VALUER[1]}  |  Registration No. {VALUER[2]}", size=8, align="c", lead=8)
    d.hr(1.0)
    d.write("VALUATION REPORT FOR IMMOVABLE PROPERTY (LAND AND BUILDING)", font="Helvetica-Bold", size=10.5, align="c", lead=16)
    cols = [("S.No.", L, 85, "l"), ("Particulars", 85, 300, "l"), ("Content", 300, R, "l")]
    rows = [("bold", ["I.", "Introduction", ""]), ["1.", "Name of Valuer", VALUER[0]], ["2.", "Date of inspection", inspected_on],
            ["", "Date of valuation", inspected_on], ["3.", "Purpose of valuation", "Collateral security for bank finance"],
            ["4.", "Name of property owner", e.name], ["5.", "Name of Bank / FI", e.bank],
            ("bold", ["II.", "Physical characteristics of the asset", ""]), ["1.", "Location / Plot No.", "Plot 21, MIDC Industrial Area"],
            ["2.", "City / Town", "Taloja, Navi Mumbai"], ["3.", "Classification of the area", "Industrial, Middle"],
            ["4.", "Postal address of the property", "\n".join(halves(e.office))], ["5.", "Area of the plot (as per deed)", "4,200 sq. m."],
            ["6.", "Boundaries (as per deed / actual)", ""], ["", "North", "Plot 20 / Plot 20"], ["", "South", "MIDC Road / MIDC Road"],
            ["", "East", "Nallah / Nallah"], ["", "West", "Plot 22 / Plot 22"],
            ["7.", "Type of building", "Industrial shed, RCC and steel frame"], ["8.", "Built-up area", "2,650 sq. m."],
            ("bold", ["IV.", "Legal aspects", ""]), ["1.", "Ownership documents", "MIDC lease deed for 95 years"],
            ["2.", "Encumbrances", "First charge to existing term lender"],
            ("bold", ["XI.", "Valuation", ""]), ["1.", "Fair market value", f"Rs. {D.inr(market_value)}"],
            ["2.", "Realisable value (90%)", f"Rs. {D.inr(round(market_value * 0.9))}"],
            ["3.", "Distress value (75%)", f"Rs. {D.inr(round(market_value * 0.75))}"]]
    d.table(cols, rows, size=8.4, row_h=12.5)
    d.down(8)
    d.write("Declaration", font="Helvetica-Bold", size=9.5, lead=13)
    d.para(f"I hereby declare that I inspected the property on {inspected_on}, that the information furnished in this report "
           "is true and correct to the best of my knowledge, and that I have no direct or indirect interest in the property.",
           size=9, lead=12)
    d.kv([("Signature:", "Sd/-"), ("Name:", VALUER[0]), ("Place / Date:", f"Navi Mumbai / {inspected_on}")], x2=L + 90, size=9.5, lead=13)
    return d.render()


def partnership_deed(e: D.Entity) -> bytes:
    """A partnership deed: parties, name and business, capital, profit sharing, banking and the usual clauses."""
    p1, p2 = e.persons[0], e.persons[1]
    d = Doc()
    d.write("PARTNERSHIP DEED", font="Times-Bold", size=14, align="c", lead=22)
    d.para(f"THIS DEED OF PARTNERSHIP is made at Navi Mumbai on this {date_words(e.incorporated)} BETWEEN {p1.name.upper()}, "
           f"residing at {p1.address} (the First Partner), AND {p2.name.upper()}, residing at {p2.address} (the Second Partner).",
           font="Times-Roman", size=10.5, lead=14)
    d.down(6)
    for i, (head, text) in enumerate((
            ("Name and business", f"The partnership shall carry on the business of trading in steel and fabricated products under "
                                  f"the name and style of {e.name.upper()}."),
            ("Place of business", f"The principal place of business shall be at {e.office}."),
            ("Commencement and duration", f"The partnership commenced on {e.incorporated} and shall be at will."),
            ("Capital", "The partners shall contribute capital of Rs. 30,00,000 and Rs. 20,00,000 respectively."),
            ("Profit and loss", "Profits and losses shall be shared between the partners in the ratio of 60 : 40."),
            ("Banking", "The firm's bank accounts shall be operated by either partner singly."),
            ("Accounts", "Books of account shall be kept at the principal place of business and closed on 31st March each year."),
            ("Arbitration", "Any dispute between the partners shall be referred to arbitration under the Arbitration and "
                            "Conciliation Act, 1996.")), 1):
        d.para(f"{i}.  {head}: {text}", font="Times-Roman", size=10.5, lead=14)
        d.down(4)
    d.down(10)
    d.write("IN WITNESS WHEREOF the partners have signed this deed on the day and year first written above.", font="Times-Roman", size=10)
    d.down(10)
    d.kv([("First Partner", f"Sd/-  {p1.name}"), ("Second Partner", f"Sd/-  {p2.name}"), ("Witnesses", "1. Sd/-  Ganesh Patil   2. Sd/-  Nitin More")],
         x2=200, font="Times-Roman", size=10, lead=16)
    return d.render()


def form_a(e: D.Entity) -> bytes:
    """Form A under section 58 of the Indian Partnership Act, 1932: the statement for registration of the firm."""
    d = Doc()
    d.write("FORM A", font="Times-Bold", size=13, align="c", lead=15)
    d.write("(See Section 58 of the Indian Partnership Act, 1932)", font="Times-Roman", size=9.5, align="c", lead=12)
    d.write("Application for registration of a firm", font="Times-Bold", size=11, align="c", lead=18)
    d.write("To, The Registrar of Firms, Maharashtra State, Mumbai", font="Times-Roman", size=10, lead=16)
    d.kv([("1. Name of the firm", e.name.upper()), ("2. Principal place of business", halves(e.office)[0]), ("", halves(e.office)[1]),
          ("3. Other places of business", "None"), ("4. Duration of the firm", "At will"),
          ("5. Date of commencement", e.incorporated)], x2=230, font="Times-Roman", size=10, lead=14)
    d.write("6. Partners", font="Times-Bold", size=10, lead=13)
    d.table([("Name of partner", L, 190, "l"), ("Permanent address", 190, 420, "l"), ("Date of joining", 420, R, "l")],
            [[p.name, "\n".join(halves(p.address)), e.incorporated] for p in e.persons], size=8.4, row_h=13)
    d.down(8)
    d.para("We, the partners, hereby declare that the particulars given above are true to the best of our knowledge and belief.",
           font="Times-Roman", size=10, lead=13)
    d.kv([(p.name, "Sd/-") for p in e.persons] + [("Place / Date", f"Navi Mumbai / {e.incorporated}")], x2=230,
         font="Times-Roman", size=10, lead=14)
    d.down(8)
    d.write("Acknowledgement: Registered as Firm No. MUM/2015/004417", font="Times-Bold", size=9.5)
    return d.render()


def gst_analytics_report(e: D.Entity = BASE, *, months=None) -> bytes:
    """A lender's GST analytics report from a fictional analytics firm: summary, filing record with delays, monthly
    turnover from GSTR-3B and GSTR-1 compared, and the top customers."""
    months = months or [m for m in D.MONTHS][-12:]
    d = Doc(page_numbers="Page {i} of {n}")
    d.write(ANALYTICS, font="Helvetica-Bold", size=10, lead=12)
    d.write("GST COMPLIANCE AND TURNOVER REPORT", font="Helvetica-Bold", size=14, lead=16)
    d.kv([("Report ID", f"ADA-GST-{num('gst', e.gstin)}"), ("Generated on", "13 November 2026"), ("Requested by", "Harbour Commercial Bank"),
          ("Period covered", f"{D.MON[months[0][1] - 1]} {months[0][0]} to {D.MON[months[-1][1] - 1]} {months[-1][0]}")],
         x2=200, size=9, lead=12)
    d.down(4)
    d.write("Taxpayer profile", font="Helvetica-Bold", size=10, lead=13)
    d.kv([("Legal name", e.name.upper()), ("Trade name", e.name.upper()), ("GSTIN", e.gstin), ("Registration status", "Active"),
          ("Date of registration", "01/07/2017"), ("Constitution of business", "Private Limited Company"),
          ("Taxpayer type", "Regular"), ("Nature of business", "Manufacturer, supplier of goods"),
          ("Principal place of business", halves(e.office)[0]), ("", halves(e.office)[1])], x2=200, size=9, lead=12)
    d.down(6)
    tot = sum(D.GST_BY_MONTH[m] for m in months)
    d.write("Summary", font="Helvetica-Bold", size=10, lead=13)
    for t in (f"Turnover declared in GSTR-3B over the period: Rs. {D.inr(tot)}.",
              "All twelve GSTR-3B returns are filed, each on or before its due date.",
              "Turnover in GSTR-1 and GSTR-3B agrees for every month.",
              "The top three customers account for 48% of sales in GSTR-1."):
        d.para(f"-  {t}", size=9, lead=12)
    d.down(6)
    d.write("Filing status of GSTR-3B", font="Helvetica-Bold", size=10, lead=13)
    rows = []
    for (y, m) in months:
        ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
        rows.append([f"{D.MON[m - 1]}-{y % 100}", f"20-{D.MON[nm - 1]}-{ny % 100}", f"{20 if (y, m) != (2026, 10) else 12}-{D.MON[nm - 1]}-{ny % 100}",
                     "0", D.inr(D.GST_BY_MONTH[(y, m)]), D.inr(D.GST_BY_MONTH[(y, m)])])
    d.table([("Return period", L, 120, "l"), ("Due date", 120, 190, "l"), ("Filed on", 190, 260, "l"), ("Delay (days)", 260, 320, "r"),
             ("GSTR-3B taxable value", 320, 430, "r"), ("GSTR-1 value", 430, R, "r")], rows, size=8.2, row_h=12)
    d.down(8)
    d.write("Top customers (GSTR-1)", font="Helvetica-Bold", size=10, lead=13)
    d.table([("Customer", L, 300, "l"), ("Share of sales", 300, R, "r")],
            [["Bharat Pumps Ltd", "21%"], ["Orient Gearbox Co", "15%"], ["Vardhan Automotive", "12%"], ["Others", "52%"]], size=8.6, row_h=12)
    return d.render()


def bank_statement_analysis(e: D.Entity = BASE, *, months=None, account: str | None = None) -> bytes:
    """A lender's bank statement analysis report from a fictional analytics firm: account details, summary, monthly
    credits and debits with average balance, recurring obligations and returns."""
    months = months or D.STATEMENT_MONTHS[-12:]
    d = Doc(page_numbers="Page {i} of {n}")
    d.write(ANALYTICS, font="Helvetica-Bold", size=10, lead=12)
    d.write("BANK STATEMENT ANALYSIS REPORT", font="Helvetica-Bold", size=14, lead=18)
    d.write("Account details", font="Helvetica-Bold", size=10, lead=13)
    d.kv([("Account holder", e.name), ("Bank", f"{e.bank}, {e.branch}"), ("Account number", account or e.account),
          ("Account type", "Current Account"), ("Period", f"{D.MON[months[0][1] - 1]} {months[0][0]} to {D.MON[months[-1][1] - 1]} {months[-1][0]}")],
         x2=200, size=9, lead=12)
    d.down(4)
    credits = {m: D.GST_BY_MONTH[m] for m in months}
    d.write("Account summary", font="Helvetica-Bold", size=10, lead=13)
    d.kv([("Total credits", D.inr(sum(credits.values()))), ("Total debits", D.inr(round(sum(credits.values()) * 0.97))),
          ("Average monthly balance", D.inr(2_31_00_000)), ("EMIs to lenders (monthly)", "1,25,000 to Lotuscrest Finance"),
          ("Cheque and NACH returns", "0"), ("Cash deposits", "0")], x2=220, size=9, lead=12)
    d.down(4)
    d.write("Monthly analysis", font="Helvetica-Bold", size=10, lead=13)
    rows = [[f"{D.MON[m - 1]} {y}", D.inr(credits[(y, m)]), D.inr(round(credits[(y, m)] * 0.97)), "1", "0", "0"] for (y, m) in months]
    d.table([("Month", L, 120, "l"), ("Credits", 120, 230, "r"), ("Debits", 230, 340, "r"), ("EMIs", 340, 400, "r"),
             ("Returns", 400, 460, "r"), ("Cash deposits", 460, R, "r")], rows, size=8.2, row_h=12)
    return d.render()


# --- documents outside the checklist (TC-07) -------------------------------------------------------------------------

def tax_invoice(e: D.Entity = BASE) -> bytes:
    """A supplier's GST tax invoice to the borrower."""
    d = Doc()
    d.write("STEELCRAFT METALS PRIVATE LIMITED", font="Helvetica-Bold", size=13, align="c", lead=14)
    d.write(f"GSTIN: {D.gstin_with_check('27AABCS7781K1Z')}  |  Plot 7, Kalamboli Steel Market, Navi Mumbai 410218", size=8, align="c", lead=8)
    d.hr(1.0)
    d.write("TAX INVOICE", font="Helvetica-Bold", size=11, align="c", lead=16)
    d.kv([("Invoice No.", "SC/2026/0457"), ("Invoice Date", "02 October 2026"), ("Place of supply", "27 - Maharashtra"),
          ("Bill to", e.name), ("Buyer GSTIN", e.gstin)], x2=160, size=9, lead=12)
    d.down(4)
    d.table([("Description of goods", L, 270, "l"), ("HSN", 270, 320, "l"), ("Qty", 320, 370, "r"), ("Rate", 370, 440, "r"), ("Amount", 440, R, "r")],
            [["Cold rolled steel coil, 2 mm", "7209", "18 MT", "70,000", "12,60,000"], ["CGST @ 9%", "", "", "", "1,13,400"],
             ["SGST @ 9%", "", "", "", "1,13,400"], ("bold", ["Total payable", "", "", "", "14,86,800"])], size=8.6, row_h=12.5)
    d.down(6)
    d.write("Amount in words: Rupees Fourteen Lakh Eighty-Six Thousand Eight Hundred only", size=8.8, lead=20)
    d.write("For Steelcraft Metals Private Limited  -  Authorised Signatory: Sd/-", size=9)
    return d.render()


def insurance_schedule(e: D.Entity = BASE) -> bytes:
    """The policy schedule of a fire insurance policy for a small enterprise's premises (the standard MSME property
    cover), from a fictional insurer: insured, period, risk location, the sums insured by item, the bank's interest and
    the premium."""
    d = Doc()
    d.write("ZENITH GENERAL INSURANCE LIMITED", font="Helvetica-Bold", size=13, align="c", lead=14)
    d.write("Regd. Office: 9th Floor, Meridian Tower, Lower Parel, Mumbai 400013", size=8, align="c", lead=8)
    d.hr(1.0)
    d.write("BHARAT SOOKSHMA UDYAM SURAKSHA POLICY", font="Helvetica-Bold", size=11, align="c", lead=13)
    d.write("POLICY SCHEDULE", font="Helvetica-Bold", size=10.5, align="c", lead=18)
    d.kv([("Policy number", "PIP/MH/2026/118822"), ("Period of insurance", "01 July 2026 to 30 June 2027 (both days inclusive)"),
          ("Name of the insured", e.name), ("Address of the insured", halves(e.office)[0]), ("", halves(e.office)[1]), ("Risk location", "Same as above"),
          ("Occupancy", "Engineering workshop - structural steel fabrication"),
          ("Financier's interest", f"{e.bank}, {e.branch} (hypothecation)")], x2=190, size=9, lead=13)
    d.down(6)
    d.table([("Item insured", L, 330, "l"), ("Sum insured (Rs.)", 330, R, "r")],
            [["Building (superstructure and plinth)", "2,40,00,000"], ["Plant and machinery", "2,80,00,000"],
             ["Stocks (raw material, work in progress, finished goods)", "1,30,00,000"], ("bold", ["Total sum insured", "6,50,00,000"])],
            size=8.8, row_h=13)
    d.down(6)
    d.kv([("Premium", "Rs. 1,62,500.00"), ("GST @ 18%", "Rs. 29,250.00"), ("Total premium", "Rs. 1,91,750.00"),
          ("Add-on covers", "Earthquake; terrorism; burglary of stocks")], x2=190, size=9, lead=13)
    d.down(8)
    d.para("Subject otherwise to the terms, conditions and exclusions of the policy wording. This schedule forms part of the "
           "policy and must be read with it.", size=8.4, lead=11)
    d.write("For Zenith General Insurance Limited  -  Authorised Signatory: Sd/-", size=9)
    return d.render()


def covering_letter(e: D.Entity = BASE) -> bytes:
    """The borrower's covering letter on its letterhead, sending the documents without naming them."""
    d = Doc()
    letterhead(d, e)
    d.write("Ref: KFPL/HCB/2026/31", size=9.5, lead=13)
    d.write("Date: 14 November 2026", size=9.5, lead=18)
    for t in ("To,", "The Branch Manager", f"{e.bank}", f"{e.branch} Branch, Navi Mumbai"):
        d.write(t, size=9.5, lead=13)
    d.down(8)
    d.write("Sub: Our application for working capital and term loan facilities", font="Helvetica-Bold", size=9.5, lead=16)
    d.write("Dear Sir or Madam,", size=9.5, lead=16)
    d.para("With reference to our discussion with your relationship manager, please find enclosed the documents you asked "
           "for. Kindly let us know if anything further is needed to process our application.", size=9.5, lead=13)
    d.down(6)
    d.write("Thanking you,", size=9.5, lead=13)
    d.write("Yours faithfully,", size=9.5, lead=20)
    d.write(f"For {e.name}", size=9.5, lead=16)
    d.kv([("Signature:", "Sd/-"), ("Name:", e.persons[0].name), ("Designation:", e.persons[0].designation)], x2=L + 85, size=9.5,
         lead=13)
    return d.render()


# Builders drawn from a measured real document in modules of their own (scripts/tpl_*.py).
from tpl_annual_report import annual_report  # noqa: E402
from tpl_gst_registration import gst_registration_certificate  # noqa: E402
from tpl_shop_establishment import shop_establishment_certificate  # noqa: E402
from tpl_income_tax_return import income_tax_return  # noqa: E402
from tpl_memorandum import memorandum  # noqa: E402

BUILDERS = ("certificate_of_incorporation", "company_pan", "memorandum", "director_kyc", "board_resolution",
            "facilities_declaration", "sanction_letter", "bureau_report", "bank_statement", "gstr_3b", "income_tax_return",
            "audited_statements")


def install() -> None:
    """Swap the realistic builders into the scenario generator, so its baseline and every scenario use them."""
    for name in BUILDERS:
        setattr(D, name, globals()[name])
