"""The income tax return as banks receive it, drawn at the positions measured on real ones: the ITR-V acknowledgement
the e-filing portal issues (A4, DejaVu Sans, cell borders in pale blue-grey, the particulars table, the numbered
"Taxable Income and Tax Details" and "Accreted Income and Tax Detail" tables with their turned side labels, the
verification sentence with its underlined blanks and the red closing line), then the statement of income the tax
practitioner's software prints (Arial with Times New Roman, the boxed assessment year and title, the particulars
block, the heads of income with amounts in three rupee columns, the tax lines, Schedule 1 of tax deducted at source,
the bank accounts and the signing block).

Not drawn (CLAUDE.md rule 8): the national emblem behind the acknowledgement's tables, its barcode and the code
string printed under it, and the digital-signature serial number and issuer at the end of the verification sentence.
Their places are left plain.

The acknowledgement's item numbers follow the assessment year: 1 to 15 up to AY 2024-25, then 1, 1A, 2 to 14.
"""

from __future__ import annotations

import io
import re
from dataclasses import replace

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import template_pages as TP
from tests import docsets as D

if "DejaVuSans-Oblique" not in pdfmetrics.getRegisteredFontNames():   # stands in for Verdana Italic (Sch.No figures)
    pdfmetrics.registerFont(TTFont("DejaVuSans-Oblique", str(TP.SYSTEM / "dejavu/DejaVuSans-Oblique.ttf")))

# --- the acknowledgement (ITR-V)
DV, DVB = "DejaVuSans", "DejaVuSans-Bold"
EDGE = "#BAC0E0"                     # the cell borders
T = 0.58                             # their thickness
SZ = 7.87                            # the table text
DV_ASC = 0.764                       # baseline below a word's top, as the portal's DejaVu Sans reports it
ROW = 24.18                          # a one-line table row
LINE = 9.41                          # each further line in a cell
# The two customers who deduct tax at source (Schedule 1) and the section they deduct under; a generator may set
# its own: [(name, TAN prefix, TAN check letter), ...].
TDS_PAYERS: list[tuple[str, str, str]] | None = None
TDS_SECTION = "194C"

# --- the statement of income
AR, ARB, ARI, TNR, TNRB, VI = "Arial", "Arial-Bold", "Arial-Italic", "TimesNewRoman", "TimesNewRoman-Bold", "DejaVuSans-Oblique"
AZ = 8.95                            # the statement's body text
COL1, COL2, COL3, COL3B = 410.47, 485.46, 565.46, 564.72   # right edges of the three Rs. columns (COL3B: a ruled cell)
WRAP = 290.0                         # particulars wrap before the Sch.No column
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class _Pages(TP.Sheet):
    """A Sheet whose pages may differ in height (the acknowledgement is 842 pt tall, the statement 841)."""

    def __init__(self):
        self.heights: list[float] = []
        self.footer_xs: list[float] = []
        super().__init__(595.0, 842.0, footer_x=28.32, footer_y=14.0)

    def page(self, h: float = 842.0, footer_x: float = 28.32):
        super().page()
        self.heights.append(h)
        self.footer_xs.append(footer_x)
        return self

    # text placed by its baseline (the templates' fonts report other ascents than ours)
    def base(self, x, base, s, font, size, *, align="l", colour="#000000"):
        self.text(x, base - TP._asc(font) * size, s, font, size, align=align, colour=colour)

    def rect(self, x0, top, x1, bottom, colour="#000000"):
        self.fill(x0, top, x1, bottom, colour)

    def cell(self, x0, x1, top, bottom):
        """One cell's four borders, each a thin filled rectangle, as the portal draws them."""
        for r in ((x0, top, x1 + T, top + T), (x0, bottom, x1 + T, bottom + T), (x0, top, x0 + T, bottom + T),
                  (x1, top, x1 + T, bottom + T)):
            self.rect(*r, colour=EDGE)

    def render(self) -> bytes:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(self.w, self.heights[0]), invariant=1)
        c.setTitle("")
        for ops, h, fx in zip(self.pages, self.heights, self.footer_xs):
            c.setPageSize((self.w, h))
            for op in ops:
                kind = op[0]
                if kind == "f":
                    _, x0, t, x1, b, colour = op
                    c.setFillColorRGB(*colour)
                    c.rect(x0, h - b, x1 - x0, b - t, stroke=0, fill=1)
                elif kind == "l":
                    _, x0, t, x1, b, lw, colour = op
                    c.setStrokeColorRGB(*colour)
                    c.setLineWidth(lw)
                    c.line(x0, h - t, x1, h - b)
                elif kind == "t":
                    _, x, base, s, font, size, al, colour, _hs = op
                    c.setFillColorRGB(*colour)
                    c.setFont(font, size)
                    (c.drawRightString if al == "r" else c.drawCentredString if al == "c" else c.drawString)(x, h - base, s)
                elif kind == "rt":
                    _, x, t, s, font, size, angle, colour = op
                    c.saveState()
                    c.setFillColorRGB(*colour)
                    c.setFont(font, size)
                    c.translate(x, h - t)
                    c.rotate(angle)
                    c.drawString(0, 0, s)
                    c.restoreState()
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 6.5)
            c.drawString(fx, self.footer_y, D.FOOTER)
            c.showPage()
        c.save()
        return buf.getvalue()


def _mon(text: str) -> str:
    import realistic_docs as R
    d, m, y = R.parse_date(text)
    return f"{d:02d}-{MON[m - 1]}-{y}"


def _wrap(s: str, font: str, size: float, room: float) -> list[str]:
    out, cur = [], ""
    for word in s.split(" "):
        trial = f"{cur} {word}" if cur else word
        if cur and TP.width(trial, font, size) > room:
            out.append(cur)
            cur = word
        else:
            cur = trial
    return out + [cur]


def _place(office: str) -> tuple[list[str], str, str, str]:
    """The office address as (premises parts, town, PIN, state)."""
    parts = office.split(", ")
    m = re.search(r"^(.*?)\s*(\d{6})$", parts[-2])
    town, pin = (m[1], m[2]) if m else (parts[-2], "")
    return parts[:-2], town, pin, parts[-1]


# ------------------------------------------------------------------------------------------------ the acknowledgement
def _verification(s: _Pages, top: float, fields: list[tuple[str, float | None]]) -> int:
    """The verification sentence from `top` (its first line's top): text with underlined blanks (each value centred
    in its blank by fixed padding), justified between the margins except on its last line. The spaces inside a value
    do not break or stretch; a value may break after a hyphen (a date). Returns the number of lines."""
    x0, x1, pitch = 44.63, 550.33, 14.395
    sp = TP.width(" ", DV, SZ)
    atoms = []                          # [text, width, pad_l, pad_r, field no., space before]
    for k, (text, pad) in enumerate(fields):
        if pad is None:
            for w in text.split(" "):
                atoms.append([w, TP.width(w, DV, SZ), 0.0, 0.0, None, True])
            continue
        run = [[p, TP.width(p, DV, SZ), 0.0, 0.0, k, i == 0] for i, p in enumerate(re.findall(r"[^-]*-|[^-]+", text))]
        run[0][2], run[-1][3] = pad, pad
        atoms += run
    lines, cur, cur_w = [], [], 0.0
    for a in atoms:
        w = a[1] + a[2] + a[3]
        add = w + (sp if cur and a[5] else 0.0)
        if cur and cur_w + add > x1 - x0:
            lines.append(cur)
            cur, cur_w = [a], w
        else:
            cur.append(a)
            cur_w += add
    lines.append(cur)
    for n, ln in enumerate(lines):
        gaps = sum(1 for a in ln[1:] if a[5])
        natural = sum(a[1] + a[2] + a[3] for a in ln) + sp * gaps
        extra = (x1 - x0 - natural) / gaps if gaps and n < len(lines) - 1 else 0.0
        x, t = x0, top + n * pitch
        spans: dict[int, list[float]] = {}
        for i, a in enumerate(ln):
            if i and a[5]:
                x += sp + extra
            s.base(x + a[2], t + DV_ASC * SZ, a[0].rstrip(), DV, SZ)
            if a[4] is not None:
                sp_ = spans.setdefault(a[4], [x, x])
                sp_[1] = x + a[1] + a[2] + a[3]
            x += a[1] + a[2] + a[3]
        for a, b in spans.values():
            s.rect(a, t + 7.93, b, t + 7.93 + T)
    return len(lines)


def _acknowledgement(s: _Pages, *, ack: str, filed: str, ay: str, pan: str, name: str, address: str, status: str,
                     form: str, loss: int, total: int, payable: int, paid: int, signer: tuple[str, str, str],
                     ip: str, when: str, place: str):
    new = int(ay[:4]) >= 2025                 # the item numbering changed with AY 2025-26
    b = lambda top, size: top + DV_ASC * size  # noqa: E731
    # --- the heading line and its rule
    s.base(28.32, b(30.01, 9.6), f"Acknowledgement Number:{ack}", DVB, 9.6)
    s.base(566.58, b(30.01, 9.6), f"Date of filing : {filed}", DVB, 9.6, align="r")
    s.rect(28.32, 45.78, 566.64, 45.78 + T)
    # --- the title box and the assessment year
    s.cell(28.32, 481.43, 50.2, 108.16)
    s.cell(481.43, 566.06, 50.2, 108.16)
    title = "INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT"
    s.base(255.31, b(59.64, 10.75), title, DVB, 10.75, align="c")
    tw = TP.width(title, DVB, 10.75)
    s.rect(255.31 - tw / 2 - 1.44, 70.54, 255.31 + tw / 2 + 1.34, 71.31)
    s.base(255.17, b(74.32, SZ), "[Where the data of the Return of Income in Form ITR-1(SAHAJ), ITR-2, ITR-3, ITR-4(SUGAM), "
           "ITR-5, ITR-6, ITR-7", DV, SZ, align="c")
    s.base(255.17, b(83.72, SZ), "filed and verified]", DV, SZ, align="c")
    s.base(255.17, b(93.12, SZ), "(Please see Rule 12 of the Income-tax Rules, 1962)", DV, SZ, align="c")
    s.base(524.04, b(61.87, 9.6), "Assessment", DV, 9.6, align="c")
    s.base(524.04, b(73.19, 9.6), "Year", DV, 9.6, align="c")
    s.base(524.04, b(89.12, 9.6), ay, DV, 9.6, align="c")
    # --- the particulars: PAN, name, address (wrapped), status and form, section and acknowledgement number
    top = 108.73
    lines = _wrap(address, DV, SZ, 559.34 - 125.24)
    rows = [("PAN", [pan], None), ("Name", [name], None), ("Address", lines, None),
            ("Status", [status], ("Form Number", form)), ("Filed u/s", ["139(1)-On or before due date"],
                                                          ("e-Filing Acknowledgement Number", ack))]
    for label, vals, pair in rows:
        h = ROW + LINE * (len(vals) - 1)
        s.cell(28.13, 117.56, top, top + h)
        first = b(top + 9.15, SZ)
        s.base(35.80, first + LINE * (len(vals) - 1) / 2 - 0.1, label, DV, SZ)
        if pair:
            s.cell(117.56, 296.42, top, top + h)
            s.cell(296.42, 476.06, top, top + h)
            s.cell(476.06, 566.45, top, top + h)
            s.base(304.10, first, pair[0], DV, SZ)
            s.base(483.73, first, pair[1], DV, SZ)
        else:
            s.cell(117.56, 566.45, top, top + h)
        for k, v in enumerate(vals):
            s.base(125.24, first + LINE * k, v, DV, SZ)
        top += h
    # --- the two numbered tables, each with its turned label
    top += T
    refund = paid - payable
    balance = "0" if refund == 0 else (f"(-) {D.inr(refund)}" if refund > 0 else D.inr(-refund))
    nums = (["1", "1A"] + [str(i) for i in range(2, 15)]) if new else [str(i) for i in range(1, 16)]
    a, c = ("6-7", "12-13") if new else ("7-8", "13-14")
    items = [("Current Year business loss, if any", D.inr(loss)), ("Total Income", D.inr(total)),
             ("Book Profit under MAT, where applicable", "0"), ("Adjusted Total Income under AMT, where applicable", "0"),
             ("Net tax payable", D.inr(payable)), ("Interest and Fee Payable", "0"),
             ("Total tax, interest and Fee payable", D.inr(payable)), ("Taxes Paid", D.inr(paid)),
             (f"(+) Tax Payable /(-) Refundable ({a})", balance),
             ("Accreted Income as per section 115TD", "0"), ("Additional Tax payable u/s 115TD", "0"),
             ("Interest payable u/s 115TE", "0"), ("Additional Tax and interest payable", "0"), ("Tax and interest paid", "0"),
             (f"(+) Tax Payable /(-) Refundable ({c})", "0")]
    nx = 427.12 if new else 427.50
    for side, rng in (("Taxable Income and Tax Details", range(0, 9)), ("Accreted Income and Tax Detail", range(9, 15))):
        start = top
        for i in rng:
            label, val = items[i]
            h = 32.63 if label.startswith("Interest payable u/s 115TE") else ROW
            s.cell(57.68, 416.18, top, top + h)
            s.cell(416.18, 461.66, top, top + h)
            s.cell(461.66, 566.06, top, top + h)
            s.base(69.01, b(top + (13.37 if h > ROW else 9.15), SZ), label, DV, SZ)
            s.base(nx, b(top + 9.15, SZ), nums[i], DV, SZ)
            s.base(558.92, b(top + 9.15, SZ), val, DV, SZ, align="r")
            top += h
        s.cell(28.32, 57.68, start, top)
        tw = TP.width(side, DVB, SZ)
        s.rotated(47.855, (start + top) / 2 + tw / 2 + 0.2, side, DVB, SZ, 90)
    # --- the verification, the system-generated block (its barcode not drawn) and the closing line
    top += T
    who, capacity, signer_pan = signer
    n = _verification(s, top + 10.68, [
        ("This return has been digitally signed by", None), (who, 46.7), ("in the capacity of", None), (capacity, 46.7),
        ("having PAN", None), (signer_pan, 23.25), ("from IP address", None), (ip, 23.25), ("on", None), (when, 23.25),
        ("at", None), (place, 23.25), ("(Place)", None)])
    # each box is as tall as its content; the signature serial's line, not printed, keeps its place
    bottom = top + 10.68 + 14.395 * n + 16.57
    s.cell(28.32, 566.06, top, bottom)
    top = bottom + 0.57
    s.cell(28.32, 566.06, top, top + 53.93)
    s.base(59.99, b(top + 14.53, SZ), "System Generated", DV, SZ)
    s.base(59.99, b(top + 33.33, SZ), "Barcode/QR Code", DV, SZ)
    top += 53.93 + 0.58
    s.cell(28.32, 566.06, top, top + 20.34)
    red = " DO NOT SEND THIS ACKNOWLEDGEMENT TO CPC, BENGALURU "
    s.base(155.94, b(top + 8.95, SZ), red, DVB, SZ, colour="#FF0000")
    s.rect(155.94, top + 16.89, 155.94 + TP.width(red, DVB, SZ) + 0.13, top + 17.66, colour="#FF0000")


# ------------------------------------------------------------------------------------------------ the statement
class _Flow:
    """The statement's rows from the top down: `t` is the top of the row's Arial text (as the template reports it);
    each kind of row advances by the template's own pitch."""

    def __init__(self, s: _Pages, t: float):
        self.s, self.t = s, t

    def at(self, size=AZ, asc=0.962) -> float:          # the baseline of Arial text on this row
        return self.t + asc * size

    def amount(self, val: str, right: float):
        self.s.base(right, self.at(), val, AR, AZ, align="r")

    def rule(self, dy: float, cols: list[tuple[float, float]], lw: float = 1.0):
        for a, b in cols:
            self.s.line(a, self.t + dy, b, self.t + dy, lw)

    def head(self, label: str, *, bullet: bool = True, underline: bool = True):
        """A heading of the statement in bold, with the square bullet and its underline."""
        if bullet:
            base = self.t + 0.05 + 0.962 * 8.9
            self.s.rect(36.45, base - 5.1, 41.55, base)
        self.s.base(49.75, self.t + 0.06 + 0.959 * 9.65, label, ARB, 9.65)
        if underline:
            self.s.line(49.75, self.t + 10.31, 49.75 + TP.width(label, ARB, 9.65) - 1.21, self.t + 10.31, 1.0)

    def total(self, label: str, val: str, *, above: bool = True, below: bool = True, step: float = 18.4):
        """A bold bulleted total in the last column, between rules."""
        if above:
            self.rule(-1.89, [(492.0, 564.75)])
        self.head(label, underline=False)
        self.amount(val, COL3B if below else COL3)
        if below:
            self.rule(12.51, [(492.0, 564.75)])
        self.t += step

    def line(self, label: str, val: str = "", *, x=49.75, font=AR, right=COL3, sch: str = "", below=False, step=18.0,
             underline=False, wrap: float | None = None, pitch: float = 11.56, grow: float = 8.1):
        """A row: its label (wrapped at `wrap`, each further line `pitch` lower and the row `grow` taller), an amount
        in a column, a Sch.No reference, a rule under the amount."""
        lines = _wrap(label, font, AZ, wrap - x) if wrap else [label]
        for k, ln in enumerate(lines):
            self.s.base(x, self.at() + pitch * k, ln, font, AZ)
        if underline:
            self.s.line(x, self.t + 9.56, x + TP.width(label, font, AZ) - 0.65, self.t + 9.56, 0.65)
        if sch:
            self.s.base(332.30, self.t + 7.86, sch, VI, 6.6)
        if val != "":
            self.amount(val, COL3B if below else right)
        if below:
            self.rule(12.51, [(492.0, 564.75)])
        self.t += step + grow * (len(lines) - 1)


def _statement(s: _Pages, e: D.Entity, *, k: str, name: str, pan: str, ay: str, fy: str, filed: str, profit: int,
               gross: int, total: int, rounded: int, tax: tuple[int, int, int], tds: int, advance: int, place: str):
    import realistic_docs as R
    new = int(ay[:4]) >= 2025
    y4 = lambda span: f"{span[:4]}-{int(span[:4]) + 1}"  # noqa: E731
    # --- the assessment year box
    s.box(252.0, 32.70, 362.25, 52.95)
    s.base(267.50, 44.70, "A.Y.", ARB, 8.7)
    s.base(306.05, 44.70, y4(ay), ARB, 8.75)
    # --- the assessee's particulars, two columns of label : value
    premises, town, pin, _state = _place(e.office)
    city = f"{town} - {pin[:3]} {pin[3:]}"
    if len(premises) > 4:                # four lines at most: door, premises, road, then locality, town and PIN
        premises = premises[:2] + [", ".join(premises[2:-1]), premises[-1]]
    addr = premises[:-1] + [f"{premises[-1]}, {city}"] if len(premises) > 1 else premises + [city]
    addr = [part for ln in addr for part in _wrap(ln, AR, AZ, 250.0)]   # clear of the right-hand column
    left = [("Name", [name]), ("", [""]), ("Address", addr)]
    born = {"company": ("Date of Incorporation", _mon(e.incorporated)), "firm": ("Date of Formation", _mon(e.incorporated)),
            "individual": ("Date of Birth", _mon(e.persons[0].dob))}[k]
    right = [(65.70, "Previous Year", y4(fy)), (83.70, "PAN", f"{pan[:5]} {pan[5:9]} {pan[9:]}"), (119.70, *born),
             (137.70, "Status", {"company": "Domestic Company", "firm": "Firm", "individual": "Individual"}[k])]
    base = 65.70
    for label, vals in left:
        if label:
            s.base(48.0, base, label, ARB, 8.35)
        s.base(120.0, base, ":", TNRB, 8.45)
        for i, v in enumerate(vals):
            s.base(126.0, base + 11.4 * i, v, AR, AZ)
        base += 18.0
    for bl, label, v in right:
        s.base(384.0, bl, label, ARB, 8.35)
        s.base(480.0, bl, ":", TNRB, 8.45)
        s.base(486.0, bl, v, AR, AZ)
    if k == "company":
        s.base(384.0, 173.70, "Opted Tax u/s 115BAA", AR, AZ)
    # --- the title box and the column heads
    s.box(36.75, 180.05, 564.0, 198.05)
    s.base(259.20, 190.81, "Statement of Income", ARB, 8.75)
    for x, h in ((318.25, "Sch.No"), (387.60, "Rs."), (465.60, "Rs."), (540.60, "Rs.")):
        s.base(x, 207.80, h, AR, 7.15)
    # --- income
    f = _Flow(s, 220.49)
    f.head("Profits and gains of Business or Profession")
    f.t += 17.96
    f.line("Business-1", font=ARI, underline=True)
    f.line("Net Profit Before Tax as per P & L a/c", D.inr(profit), x=63.50, right=COL2)
    head_income = profit if gross == max(profit, 0) else gross     # a loss shows under its head; the total is nil
    f.line('Income chargeable under the head "Business and Profession"', D.inr(head_income), font=ARI, wrap=WRAP)
    if gross != total:                    # the template prints Total Income alone when the two are the same
        f.total("Gross Total Income", D.inr(gross))
        if gross > total:
            f.line("Less: Deductions under Chapter VI-A", D.inr(gross - total), below=True)
        f.total("Total Income", D.inr(total), above=False)
    else:
        f.total("Total Income", D.inr(total))
    if rounded != total:
        f.line("Total income rounded off u/s 288A", D.inr(rounded))
    # --- tax
    on_income, sur, cess = tax
    payable = on_income + sur + cess
    f.line("Tax on total income", D.inr(on_income), font=ARI)
    f.line("Add: Surcharge", D.inr(sur), below=True)
    f.line("Tax with Surcharge", D.inr(on_income + sur))
    f.line("Add: Cess", D.inr(cess), below=True)
    f.line("Tax with surcharge and cess", D.inr(payable))
    if advance:
        f.line("Advance Tax", D.inr(advance))
    if tds:
        f.line("TDS / TCS", D.inr(tds), sch="1")
    due = payable - advance - tds
    f.total("Tax Payable" if due > 0 else "Refund Due", D.inr(abs(due)))
    f.t += 18.0

    def room(need: float):               # a section that would run into the signing block starts a new page
        if f.t + need > 728.0:
            s.page(841.0, footer_x=48.0)
            f.t = 57.09

    # --- Schedule 1: tax deducted at source by two customers (section 194C, contract work at 2 per cent)
    if tds:
        room(18.0 * 7 + 9.0)
        f.head("Schedule 1", bullet=False, underline=False)
        f.t += 18.0
        f.line("TDS as per Form 16A", font=ARI)
        s.base(410.45, f.at(), "TDS", AR, AZ, align="r")
        s.base(485.42, f.at(), "TDS claimed", AR, AZ, align="r")
        s.base(565.42, f.at(), "Gross receipt", AR, AZ, align="r")
        f.line("Deductor, TAN & Section" if new else "Deductor, TAN", underline=True)
        s.base(410.47, f.at(), "deducted", AR, AZ, align="r")
        s.base(485.35, f.at(), "in current year", AR, AZ, align="r")
        f.rule(12.51, [(338.5, 410.5), (413.5, 485.5), (492.0, 564.75)])
        s.base(564.71, f.at(), "offered", AR, AZ, align="r")
        f.t += 18.0
        first = round(tds * 0.6)
        names = TDS_PAYERS or [(D.CUSTOMERS[2].title(), "MUMV", "E"), (D.CUSTOMERS[3].title(), "PNES", "D")]
        payers = [(who, f"{pre}{R.num(pan, ay, pre, digits=5)}{suf}", amt)
                  for (who, pre, suf), amt in zip(names, (first, tds - first))]
        for who, tan, amt in payers:
            label = f"{who}, TAN- {tan}, Section- {TDS_SECTION}" if new else f"{who}, TAN- {tan}"
            s.base(COL1, f.at(), D.inr(amt), AR, AZ, align="r")
            s.base(485.47, f.at(), D.inr(amt), AR, AZ, align="r")
            f.line(label, D.inr(amt * 50), wrap=WRAP, pitch=11.4, grow=7.8)
        f.rule(-1.89, [(338.5, 410.5), (413.5, 485.5), (492.0, 564.75)])
        s.base(410.46, f.at(), D.inr(tds), AR, AZ, align="r")
        s.base(COL2, f.at(), D.inr(tds), AR, AZ, align="r")
        f.rule(12.51, [(338.5, 410.5), (413.5, 485.5)])
        f.line("Total", D.inr(tds * 50), font=ARI, below=True)
        f.t += 18.0
    # --- the bank accounts
    room(18.0 * 3 + 9.0)
    f.head("Bank A/cs", bullet=False, underline=False)
    f.t += 18.0
    f.line("Bank Accounts in India", x=63.50, underline=True)
    s.base(410.45, f.at(), "IFS Code", AR, AZ, align="r")
    s.base(485.42, f.at(), "Type of Account", AR, AZ, align="r")
    cols = [(338.5, 410.5), (413.5, 485.5)]
    if new:
        s.base(566.21, f.at(), "For refund?", AR, AZ, align="r")
        cols.append((493.5, 566.25))
    f.rule(12.51, cols)
    f.line("Bank Name and Account No.", x=63.50, underline=True)
    s.base(407.98, f.at(), e.ifsc, AR, AZ, align="r")
    s.base(485.99, f.at(), "Current", AR, AZ, align="r")
    if new:
        s.base(563.97, f.at(), "Yes", AR, AZ, align="r")
    f.line(f"{e.bank} - {e.account}", x=78.0)
    # --- the signing block, at the foot of the page
    s.base(575.46, 744.55, f"For {name}", ARB, 8.75, align="r")
    s.base(48.0, 756.55, "Date : ", AR, AZ)
    s.base(90.0, 757.30, filed, AR, 9.85)
    s.base(48.0, 768.55, "Place : ", AR, AZ)
    s.base(90.0, 769.30, place, AR, 9.85)
    s.base(488.75, 775.30, "Authorised Signatory", TNR, 9.6)


def income_tax_return(e: D.Entity = D.BASE, *, turnover: int, profit: int, pan: str | None = None,
                      name: str | None = None, ay: str = "2026-27", fy: str = "2025-26", filed: str = "28 September 2026",
                      gross: int | None = None, total: int | None = None) -> bytes:
    """The return as banks receive it: the ITR-V acknowledgement (ITR-6 for a company, ITR-5 for a firm, ITR-3 for a
    proprietor, by the PAN's fourth character) and the statement of income from the practitioner's software. A loss
    year files a nil income, with the year's business loss on the acknowledgement. Tax is paid by tax deducted at
    source by two customers (Schedule 1: 2% of `turnover`, the receipts), and any shortfall as advance tax. Neither
    page prints the turnover, as the real ones do not."""
    import realistic_docs as R
    loss = max(-profit, 0)
    gross = gross if gross is not None else max(profit, 0)
    total = total if total is not None else max(profit, 0)
    p_pan, p_name = pan or e.pan, name or e.name
    k = R.kind(e if pan is None else replace(e, pan=pan))
    form, status, rate, sur_rate = {
        "company": ("ITR-6", "7-Private company", 0.22, 0.10),
        "firm": ("ITR-5", "5-Firm", 0.30, 0.12),
        "individual": ("ITR-3", "1-Individual", 0.30, 0.15)}[k]
    rounded = int(round(total / 10.0)) * 10        # section 288A
    on_income = round(max(rounded, 0) * rate)
    tax = (on_income, round(on_income * sur_rate), round(on_income * (1 + sur_rate) * 0.04))
    payable = sum(tax)
    tds = round(max(turnover, 0) * 0.02)          # TDS on receipts under section 194C (2% for a company's contracts)
    advance = max(payable - tds, 0)               # advance tax only where the TDS falls short, as the template shows
    ack = f"2627100{R.num(ay, p_pan, digits=8)}"
    premises, town, pin, state = _place(e.office)
    address = f"{', '.join(premises)}, {town} , {R.DISTRICT.get(town, town)} , {e.gstin[:2]}-{state}, 91-INDIA, {pin}"
    signer = e.persons[0]
    capacity = "Self" if k == "individual" else signer.designation
    seq = R.num(ay, p_pan, "ip", digits=6)
    ip = f"203.0.113.{int(seq[:3]) % 254 + 1}"                     # a documentation address (RFC 5737)
    when = f"{_mon(filed)}    {10 + int(seq[3]) % 9}:{int(seq[4:]) % 60:02d}:{(int(seq) * 7) % 60:02d}"

    s = _Pages()
    _acknowledgement(s, ack=ack, filed=_mon(filed), ay=ay, pan=p_pan, name=p_name.upper(), address=address, status=status,
                     form=form, loss=loss, total=rounded, payable=payable, paid=tds + advance,
                     signer=(signer.name.upper(), capacity, p_pan if k == "individual" else signer.pan_masked), ip=ip,
                     when=when, place=town.upper())
    s.page(841.0, footer_x=48.0)
    _statement(s, e, k=k, name=p_name, pan=p_pan, ay=ay, fy=fy, filed=_mon(filed), profit=profit, gross=gross, total=total,
               rounded=rounded, tax=tax, tds=tds, advance=advance, place=town)
    return s.render()
