"""The annual report with audited financial statements, laid out as the real one (a scanned Word document, studied in
place): Times 12; the company's name (bold italic) and CIN at the head and its registered office (bold, two lines) at
the foot of every page; the cover; the notice; the directors' report with its results table; the independent auditor's
report on the audit firm's letterhead with the CARO annexure; the balance sheet and the profit and loss statement on
framed pages (heading block, hatched column heads, Notes column, two years, amounts in INR thousands, boxed totals,
the auditor's and directors' signature blocks); the notes to accounts as framed tables; the accounting policies; and
the lists of shareholders and directors.

Not drawn (CLAUDE.md rule 8): signatures, the audit firm's seal, the professional body's logo; their space is left
plain. Every name, number and address is fictional; the prose is written for the pack, not copied.

Deliberate deviation: the net block of fixed assets is also printed on the "(a) Fixed Assets" line, so the engine's
spread finds it (its rule reads that line); the real page prints it on "(iii) Net Block" only.
"""

from __future__ import annotations

import re

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import template_pages as TP
from tests import docsets as D

for _n, _f in (("TimesNewRoman-Italic", "LiberationSerif-Italic.ttf"),
               ("TimesNewRoman-BoldItalic", "LiberationSerif-BoldItalic.ttf")):
    if _n not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_n, str(TP.SYSTEM / "liberation" / _f)))

TR, TB, TI, TBI = "TimesNewRoman", "TimesNewRoman-Bold", "TimesNewRoman-Italic", "TimesNewRoman-BoldItalic"
PAGE_W, PAGE_H = 595.2, 841.68
CX = 286.0                         # the centre line of the template's text
LM, RM = 66.5, 505.0               # text margins of the report pages
TOP, BOTTOM = 92.0, 762.0          # body area below the running head and above the address
NAVY = "#34497A"
HATCH_BG, HATCH_LINE = "#DCDCDC", "#A9A9A9"
# What is particular to the company; a generator may set its own (scripts/make_instafinance_sets.py does).
PROFILE = {
    "business": "designing, fabricating, erecting and dealing in structural steel, pressure vessels and sheet metal "
                "components for industrial customers, and operates from its works at the registered office",
    "energy": "The company takes measures to conserve energy in its fabrication shop wherever possible.",
    "revenue_lines": [("Sale of Products (fabricated structures)", 1.0)],
    "inventory_lines": [("Raw Materials (steel sections and plates)", 0.6), ("Work-in-progress", 0.4)],
    "inventory_policy": "Raw materials are valued at the lower of cost and net realisable value; cost is determined on the "
                        "first-in, first-out basis. Work-in-progress is valued at cost, which includes materials, labour "
                        "and a proportion of manufacturing overheads.",
    "authorised_shares": 1_000_000,
    "shares": 500_000,
    "holders": [(0, 300_000), (1, 200_000)],          # (index into the entity's persons, shares held)
}
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII"]


def k(v: float) -> str:
    """An amount in thousands as the statements print it: 3,252; a dash for nil; a loss in brackets."""
    n = int(round(v))
    if n == 0:
        return "-"
    s = f"{abs(n):,}"
    return f"({s})" if n < 0 else s


def rs(v: float) -> str:
    """Rupees in the Indian grouping (the directors' report table)."""
    n = int(round(v))
    if n == 0:
        return "NIL"
    return ("-" if n < 0 else "") + D.inr(abs(n))


class Report:
    """A flowing report on TP.Sheet pages: running head, address foot, paragraphs that break across pages."""

    def __init__(self, co: str, idline: str, office: tuple[str, str]):
        self.s = TP.Sheet(PAGE_W, PAGE_H, footer_x=24.0, footer_y=10.0)
        self.co, self.idline, self.office = co, idline, office
        self.first = True
        self.y = TOP
        self.marks: dict[str, int] = {}

    # --- pages
    def page(self, *, head: bool = True, foot: bool = True, mark: str | None = None):
        if self.first:
            self.first = False
        else:
            self.s.page()
        if mark:
            self.marks[mark] = len(self.s.pages) - 1
        if head:
            self.s.text(CX, 28.0, self.co.upper(), TBI, 13, align="c")
            self.s.text(CX, 46.6, self.idline, TB, 11, align="c")
        if foot:
            self.s.text(CX, 781.2, self.office[0], TB, 11, align="c")
            self.s.text(CX, 794.2, self.office[1], TB, 11, align="c")
        self.y = TOP

    def need(self, h: float):
        if self.y + h > BOTTOM:
            self.page()

    # --- text
    def gap(self, h: float):
        self.y += h

    def title(self, text: str, *, size: float = 11, underline: bool = True, after: float = 26.0):
        self.need(size + after)
        self.s.text(CX, self.y, text, TB, size, align="c")
        if underline:
            w = TP.width(text, TB, size)
            self.s.line(CX - w / 2, self.y + size * 0.86, CX + w / 2, self.y + size * 0.86, 0.6)
        self.y += after

    def line(self, text: str, *, x: float = LM, font: str = TR, size: float = 11, lead: float = 13.2,
             underline: bool = False, align: str = "l"):
        self.need(lead)
        self.s.text(x, self.y, text, font, size, align=align)
        if underline:
            w = TP.width(text, font, size)
            x0 = x - w if align == "r" else x - w / 2 if align == "c" else x
            self.s.line(x0, self.y + size * 0.86, x0 + w, self.y + size * 0.86, 0.6)
        self.y += lead

    def heading(self, text: str, *, x: float = LM, before: float = 6.0, after: float = 18.0, underline: bool = False):
        self.gap(before)
        self.need(after + 30)
        self.s.text(x, self.y, text, TB, 11)
        if underline:
            self.s.line(x, self.y + 10.3, x + TP.width(text, TB, 11), self.y + 9.5, 0.6)
        self.y += after

    def para(self, text: str, *, x: float = LM, right: float = RM, font: str = TR, size: float = 11,
             lead: float = 13.0, after: float = 11.0, justify: bool = True, bold_words: set[str] | None = None):
        w = right - x
        words = text.split(" ")
        lines, cur = [], []
        fnt = lambda wd: TB if bold_words and wd.strip(",.") in bold_words else font  # noqa: E731
        width = lambda ws: sum(TP.width(wd, fnt(wd), size) for wd in ws) + TP.width(" ", font, size) * (len(ws) - 1)  # noqa: E731
        for wd in words:
            if cur and width(cur + [wd]) > w:
                # a line that starts with "company" reads to the engine as a "Company <name>" label: break earlier
                if wd.lower().startswith("compan") and len(cur) > 2:
                    lines.append(cur[:-1])
                    cur = [cur[-1], wd]
                else:
                    lines.append(cur)
                    cur = [wd]
            else:
                cur.append(wd)
        lines.append(cur)
        for i, ln in enumerate(lines):
            self.need(lead)
            gap = TP.width(" ", font, size)
            if justify and i < len(lines) - 1 and len(ln) > 1:
                gap += (w - width(ln)) / (len(ln) - 1)
            xx = x
            for wd in ln:
                self.s.text(xx, self.y, wd, fnt(wd), size)
                xx += TP.width(wd, fnt(wd), size) + gap
            self.y += lead
        self.y += after

    def numbered(self, no: str, head: str, body: str | list[str]):
        text = f"{no}.   {head}"
        if TP.width(text, TB, 11) > RM - LM:          # a long heading wraps under its first word
            words, first = head.split(" "), ""
            while words and TP.width(f"{no}.   {first} {words[0]}".strip(), TB, 11) < RM - LM - 4:
                first = f"{first} {words.pop(0)}".strip()
            self.heading(f"{no}.   {first}", x=LM - 1.0, before=2.0, after=13.0)
            self.heading(" ".join(words), x=LM + 16.5, before=0.0, after=19.0)
        else:
            self.heading(text, x=LM - 1.0, before=2.0, after=19.0)
        for b in [body] if isinstance(body, str) else body:
            self.para(b, x=LM + 16.5, after=10.0)

    def boxed_table(self, edges: list[float], rows: list[tuple], *, size: float = 11, row_h: float = 13.4,
                    head_rows: int = 1):
        """A ruled table: rows of (cells, bold); the first head_rows rows are its heading (bold, centred)."""
        h_total = sum(row_h * max(len(str(c).split("\n")) for c in cells) for cells, _ in rows)
        self.need(h_total + 6)
        top = self.y
        for r, (cells, bold) in enumerate(rows):
            n = max(len(str(c).split("\n")) for c in cells)
            h = row_h * n
            for i, c in enumerate(cells):
                x0, x1 = edges[i], edges[i + 1]
                for j, part in enumerate(str(c).split("\n")):
                    t = self.y + 1.8 + j * row_h
                    f = TB if bold or r < head_rows else TR
                    if r < head_rows:
                        self.s.text((x0 + x1) / 2, t, part, f, size, align="c")
                    elif i == 0:
                        self.s.text(x0 + 3.0, t, part, f, size)
                    else:
                        self.s.text((x0 + x1) / 2, t, part, f, size, align="c") if bold is None else \
                            self.s.text(x1 - 3.0, t, part, f, size, align="r")
            self.s.line(edges[0], self.y, edges[-1], self.y, 0.6)
            self.y += h
        self.s.line(edges[0], self.y, edges[-1], self.y, 0.6)
        for x in edges:
            self.s.line(x, top, x, self.y, 0.6)
        self.y += 10


def hatch(s: TP.Sheet, x0: float, top: float, x1: float, bottom: float):
    """The fine diagonal pattern Word prints in shaded table cells."""
    s.fill(x0, top, x1, bottom, HATCH_BG)
    step, h = 1.6, bottom - top
    c = -h
    while c < x1 - x0:
        a0 = max(0.0, c)
        a1 = min(x1 - x0, c + h)
        if a1 > a0:
            s.line(x0 + a0, bottom - (a0 - c), x0 + a1, bottom - (a1 - c), 0.2, HATCH_LINE)
        c += step


def office_lines(e: D.Entity) -> tuple[str, str]:
    parts = e.office.split(", ")
    m = re.search(r"^(.*?)\s*(\d{6})$", parts[-2])
    city, pin = (m[1], m[2]) if m else (parts[-2], "")
    first = ", ".join(parts[:-2]) + ","
    return first, f"{city}, {parts[-1]} - {pin}, India."


def annual_report(e: D.Entity | None = None, *, revenue: int, profit_before_tax: int, fy_end: int = 2026,
                  name: str | None = None, cash: int | None = None, borrowings: int | None = None,
                  reserves: int | None = None, prev_reserves: int | None = None, signed_on: str = "27 August 2026",
                  page_numbers: bool = False, drop_page: int | None = None, pl_heading: str = "template",
                  figures: dict | None = None, report_number: int | None = None) -> bytes:
    """report_number is the annual report's number (3 prints "Third Annual Report"); by default it counts from
    FY2014-15, as the pack's reports always have. drop_page 2 leaves out the balance sheet and 3 the profit and loss
    statement; with page_numbers every page carries "Page n of N" and the remaining pages keep their numbers, so the
    gap shows. pl_heading "schedule_iii" prints
    the statutory "STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED ..." with "Year ended" column heads.

    figures gives the statements explicitly, in rupees: {"bs": {...}, "bs_prev": {...}, "pl": {...}, "pl_prev": {...}}.
    Balance sheet keys: sc, res, ltb, dtl, oltl, stb, tp, ocl, stp, ppe, cwip, ncinv, dta, onca, cinv, inv, tr, cash, stla,
    oca; profit and loss keys: rev, oi, mat, emp, fin, dep, pbt, tax, adj (after-tax adjustments, negative when they reduce
    profit). figures["notes"] may give a note's lines by its number: {"10": [(label, current, previous, style), ...]}, rupees;
    a heading line has None amounts. Without it the figures follow revenue and
    profit before tax as before."""
    import realistic_docs as R

    e = e or D.BASE
    co = name or e.name
    cy, py = fy_end, fy_end - 1
    company = R.kind(e) == "company"
    firm = R.kind(e) == "firm"
    p1 = e.persons[0]
    p2 = e.persons[1] if len(e.persons) > 1 else e.persons[0]
    ordinal = R.ORDINAL_WORDS[max(1, min(report_number or cy - 2014, 15))]
    fyw = f"{py}-{cy % 100:02d}"
    pyw = f"{py - 1}-{py % 100:02d}"
    dd = R.dmy(signed_on)
    a_name, a_desc, a_frn, a_partner, a_mno = R.AUDITOR
    udin = f"{cy % 100}{a_mno}BKDRAN{R.num(co, cy, digits=4)}"
    office = office_lines(e)
    idline = f"CIN: {e.cin}" if company else f"PAN: {e.pan}   GSTIN: {e.gstin}"

    # --- figures, in rupees, then in thousands for the statements (totals made from the rounded lines)
    prev_rev, prev_pbt = round(revenue * 0.91), round(profit_before_tax * 0.9)
    cur = R._bs_year(cy, reserves=reserves, cash=cash, borrowings=borrowings)
    prev = R._bs_year(py, reserves=prev_reserves)
    pat = lambda pbt: round(pbt * 0.75) if pbt > 0 else pbt  # noqa: E731

    ASSETS = ("ppe", "cwip", "ncinv", "dta", "onca", "cinv", "inv", "tr", "cash", "stla", "oca")
    LIABS = ("sc", "res", "ltb", "dtl", "oltl", "stb", "tp", "stp")             # other current liabilities balance the sheet

    def bs_k(b: dict) -> dict:
        t = {key: round(b.get(key, 0) / 1000) for key in ASSETS + LIABS}
        t["total"] = sum(t[key] for key in ASSETS)
        t["ocl"] = t["total"] - sum(t[key] for key in LIABS)
        t["gross"] = round(t["ppe"] * 1.38)
        t["dep_acc"] = t["gross"] - t["ppe"]
        return t

    def pl_k(rev: int, pbt: int) -> dict:
        r = round(rev / 1000)
        oi = round(r * 0.004)
        mat, emp, fin, dep = round(r * 0.62), round(r * 0.11), round(r * 0.012), round(r * 0.02)
        pb = round(pbt / 1000)
        other = r + oi - pb - mat - emp - fin - dep
        tax = pb - round(pat(pbt) / 1000) if pbt > 0 else 0
        return {"rev": r, "oi": oi, "ti": r + oi, "mat": mat, "emp": emp, "fin": fin, "dep": dep, "oth": other,
                "te": r + oi - pb, "pbt": pb, "tax": tax, "dtx": 0, "pat": pb - tax}

    def pl_given(f: dict) -> dict:
        t = {key: round(f[key] / 1000) for key in ("rev", "oi", "mat", "emp", "fin", "dep", "pbt", "tax")}
        t["ti"] = t["rev"] + t["oi"]
        t["te"] = t["ti"] - t["pbt"]
        t["oth"] = t["te"] - (t["mat"] + t["emp"] + t["fin"] + t["dep"])
        t["dtx"] = round(-f.get("adj", 0) / 1000)       # other adjustments after tax, shown as deferred tax
        t["pat"] = t["pbt"] - t["tax"] - t["dtx"]
        return t

    if figures:
        cur, prev = figures["bs"], figures["bs_prev"]
        bc, bp = bs_k(cur), bs_k(prev)
        a, b = pl_given(figures["pl"]), pl_given(figures["pl_prev"])
        revenue, prev_rev = figures["pl"]["rev"], figures["pl_prev"]["rev"]
        profit_before_tax, prev_pbt = figures["pl"]["pbt"], figures["pl_prev"]["pbt"]
    else:
        bc, bp = bs_k(cur), bs_k(prev)
        a, b = pl_k(revenue, profit_before_tax), pl_k(prev_rev, prev_pbt)
    shares = PROFILE["shares"]

    rp = Report(co, idline, office)
    s = rp.s

    # ================================================================ cover
    rp.page(mark="cover")
    s.text(CX, 238.0, co.upper(), TBI, 13, align="c")
    s.line(112.0, 260.0, 458.0, 260.0, 0.8)
    cover = f"{ordinal} ANNUAL REPORT - {fyw}" if company else f"FINANCIAL STATEMENTS - {fyw}"
    s.text(CX, 278.0, cover, TBI, 13, align="c")
    rp.y = 360.0
    rp.line("BOARD OF DIRECTORS" if company else ("PARTNERS" if firm else "PROPRIETOR"), font=TB, lead=22)
    for p in e.persons:
        rp.line(f"{p.name.upper()} - DIN {p.din}" if (company and p.din) else p.name.upper(), lead=12.6)
    rp.gap(34)
    rp.line("AUDITORS", font=TB, lead=22)
    rp.line(f"{a_name.upper()}.", font=TB, lead=12.4)
    rp.line(a_desc, font=TB, lead=12.4)
    for ln in ("402, Nariman Chambers,", "Ballard Estate, Fort,", "Mumbai - 400001."):
        rp.line(ln, lead=12.4)
    rp.gap(34)
    rp.line("REGISTERED OFFICE", font=TB, lead=22)
    if company:
        rp.line(e.cin, lead=12.4)
    for ln in (office[0], office[1]):
        rp.line(ln, lead=12.4)

    # ================================================================ notice of the annual general meeting
    if company:
        rp.page(mark="notice")
        rp.title("NOTICE")
        agm = ordinal.title()
        rp.para(f"NOTICE is hereby given that the {agm} Annual General Meeting of the members of {co.upper()} "
                f"({e.cin}) will be held on Wednesday, the 30th day of September, {cy} at 11.00 A.M. at the registered "
                "office of the company to transact the following business:", bold_words=set(co.upper().split()))
        rp.heading("ORDINARY BUSINESS", underline=True, before=0)
        rp.para(f"1.  To receive, consider and adopt the audited Balance Sheet as at 31st March, {cy}, the Statement of "
                "Profit and Loss for the year ended on that date and the Reports of the Board of Directors and the "
                "Auditors thereon.", x=LM + 16.5)
        rp.para(f"2.  To consider the re-appointment of {a_name}, Chartered Accountants (Firm Registration No. "
                f"{a_frn}), as statutory auditors of the company and to fix their remuneration.", x=LM + 16.5)
        rp.gap(14)
        rp.line("By Order of the Board", lead=13.2)
        rp.line(f"For {co.upper()}", font=TB, lead=46)
        s.text(LM, rp.y - 30, "Sd/-", TR, 11)
        s.text(LM + 230, rp.y - 30, "Sd/-", TR, 11)
        for left, right in ((p1.name.upper(), p2.name.upper()), (p1.designation, p2.designation),
                            (f"DIN: {p1.din}", f"DIN: {p2.din}")):
            s.text(LM, rp.y, left, TB if left.isupper() else TR, 11)
            s.text(LM + 230, rp.y, right, TB if right.isupper() else TR, 11)
            rp.y += 13.2
        rp.gap(16)
        rp.line(f"Place: {R.town(e.office)}", lead=13.2)
        rp.line(f"Date: {dd}", lead=26)
        rp.heading("NOTES:", before=0, after=16)
        for n, t in enumerate((
                "A member entitled to attend and vote at the meeting is entitled to appoint a proxy to attend and vote "
                "instead of himself, and the proxy need not be a member of the company.",
                "The instrument appointing a proxy, to be effective, should be deposited at the registered office of the "
                "company not less than forty-eight hours before the commencement of the meeting.",
                "Members are requested to notify any change in their address to the company at its registered office."), 1):
            rp.para(f"{n}.  {t}", x=LM + 16.5, after=8)

    # ================================================================ directors' report
    if company:
        rp.page(mark="directors_report")
        rp.title("DIRECTORS' REPORT", after=42)
        rp.line("To", lead=18.6)
        rp.line("The Members", lead=18.6)
        rp.line(co.upper(), font=TB, lead=31)
        rp.para(f"Your Directors have the pleasure in presenting the {ordinal.title()} Annual Report together with the "
                f"Audited Accounts for the year ended 31st March, {cy} and the Auditor's report thereon:")
        rp.heading("1.   FINANCIAL RESULTS", before=2, after=24)
        rp.line("The highlights of the financial results for the period are as under:", x=LM + 17.5, lead=18)
        pd = lambda v: v  # noqa: E731
        ra = {kk: v * 1000 for kk, v in a.items()}
        rb = {kk: v * 1000 for kk, v in b.items()}
        res_rows = [(("FINANCIAL RESULTS:", f"{fyw}\nAmount (In Rs.)", f"{pyw}\nAmount (In Rs.)"), None),
                    (("Net Sales/Income from Operations", rs(revenue), rs(prev_rev)), False),
                    (("Profit before Depreciation & Tax", rs(ra["pbt"] + ra["dep"]), rs(rb["pbt"] + rb["dep"])), False),
                    (("Depreciation", rs(ra["dep"]), rs(rb["dep"])), False),
                    (("Net Profit Before Tax", rs(ra["pbt"]), rs(rb["pbt"])), True),
                    (("Provision for Tax/Tax Paid", rs(ra["tax"]), rs(rb["tax"])), False),
                    (("Deferred tax (Asset)/Liability", "NIL", "NIL"), False),
                    (("Net Profit After Tax", rs(ra["pat"]), rs(rb["pat"])), True)]
        rp.y += 2
        top = rp.y
        rp.boxed_table([90.0, 300.0, 400.0, 479.5], [(c, bb) for c, bb in res_rows], size=11.5, row_h=12.6)
        _ = (top, pd)
        sections = [
            ("REVIEW OF OPERATIONS",
             f"We the Directors place before you the results of performance by our company {co.upper()}. The company "
             f"recorded revenue from operations of Rs. {rs(revenue)} during the year against Rs. {rs(prev_rev)} in the "
             "previous year. With the continued efforts of the working Directors the company expects to grow further."),
            ("DIVIDEND", "Your Directors have considered it prudent to conserve the resources of the company for its future "
                         "growth and as such have not recommended any dividend for the year."),
            ("DEPOSITS", "The company has not accepted any deposits within the meaning of section 73 of the Companies Act, "
                         "2013 read with the Companies (Acceptance of Deposits) Rules, 2014 during the period under review."),
            ("RESERVES", f"During the year under review the company has transferred an amount of Rs. {rs(ra['pat'])}/- to "
                         "reserves." if ra["pat"] > 0 else "No amount has been transferred to reserves during the year."),
            ("CHANGE IN THE NATURE OF BUSINESS, IF ANY",
             "During the year under review, there is no change in the nature of business of the company."),
            ("MATERIAL CHANGES AND COMMITMENTS",
             "There are no material changes and commitments affecting the financial position of the company which have "
             "occurred between the end of the financial year and the date of this report."),
            ("CORPORATE SOCIAL RESPONSIBILITY",
             "The provisions of section 135 of the Companies Act, 2013 regarding corporate social responsibility are not "
             "applicable to the company for the year under review."),
            ("CORPORATE GOVERNANCE", "The company is committed to good corporate governance and complies with the "
                                     "requirements applicable to a private company."),
            ("DIRECTORS", f"The Board of the company consists of {len(e.persons)} directors. There was no change in the "
                          "composition of the Board during the year."),
            ("MEETINGS OF THE BOARD", "The Board met at regular intervals during the year to transact business. The gap "
                                      "between two meetings did not exceed the period prescribed under the Act."),
            ("SUBSIDIARIES, JOINT VENTURES AND ASSOCIATE COMPANIES",
             "The company does not have any subsidiary, joint venture or associate company."),
            ("CONSERVATION OF ENERGY, TECHNOLOGY ABSORPTION AND FOREIGN EXCHANGE EARNINGS AND OUTGO",
             PROFILE["energy"] + " There were no foreign exchange earnings or outgo during the year."),
            ("PARTICULARS OF LOANS, GUARANTEES OR INVESTMENTS",
             "The company has not given any loans or guarantees or made any investments under section 186 of the Act "
             "during the year."),
            ("RELATED PARTY TRANSACTIONS",
             "All transactions with related parties during the year were in the ordinary course of business and on an "
             "arm's length basis, and are disclosed in the notes to the financial statements."),
            ("AUDITORS", f"{a_name}, Chartered Accountants (Firm Registration No. {a_frn}), continue as "
                                   "the auditors of the company. The auditor's report does not contain any "
                                   "qualification, reservation or adverse remark."),
            ("INTERNAL FINANCIAL CONTROLS", "The company has adequate internal financial controls commensurate with the "
                                            "size and nature of its business."),
            ("PREVENTION OF SEXUAL HARASSMENT AT WORKPLACE",
             "The company has a policy on the prevention of sexual harassment at the workplace. No complaints were "
             "received during the year."),
            ("DIRECTORS' RESPONSIBILITY STATEMENT",
             ["Pursuant to section 134(5) of the Companies Act, 2013, the Directors confirm that:",
              "(a) in the preparation of the annual accounts, the applicable accounting standards have been followed;",
              "(b) the Directors have selected accounting policies and applied them consistently, and made judgements "
              "and estimates that are reasonable and prudent, so as to give a true and fair view of the state of affairs "
              "of the company at the end of the financial year and of its profit or loss for that period;",
              "(c) the Directors have taken proper and sufficient care for the maintenance of adequate accounting records "
              "for safeguarding the assets of the company;",
              "(d) the Directors have prepared the annual accounts on a going concern basis; and",
              "(e) the Directors have devised proper systems to ensure compliance with the provisions of all applicable "
              "laws, and such systems are adequate and operating effectively."]),
            ("ACKNOWLEDGEMENTS", "Your Directors place on record their appreciation of the support received from the "
                                 "company's bankers, customers, suppliers and employees during the year."),
        ]
        for n, (h, body) in enumerate(sections, 2):
            rp.numbered(str(n), h, body)
        rp.gap(10)
        rp.need(110)
        rp.line("For and on behalf of the Board of Directors", lead=13.2)
        rp.line(f"For {co.upper()}", font=TB, lead=46)
        for left, right in ((p1.name.upper(), p2.name.upper()), ("Director", "Director"),
                            (f"DIN: {p1.din}", f"DIN: {p2.din}")):
            s.text(LM, rp.y, left, TB if left.isupper() else TR, 11)
            s.text(LM + 230, rp.y, right, TB if right.isupper() else TR, 11)
            rp.y += 13.2
        rp.gap(14)
        rp.line(f"Place: {R.town(e.office)}", lead=13.2)
        rp.line(f"Date: {dd}", lead=13.2)

    # ================================================================ independent auditor's report (letterhead)
    def letterhead():
        rp.page(head=False, foot=False, mark=None)
        s.fill(12.0, 0.0, 21.0, PAGE_H, NAVY)
        x = 60.0
        for ch in a_name.upper():
            s.text(x, 32.6, ch, "Arial", 19.5, colour="#2F4170")
            x += TP.width(ch, "Arial", 19.5) + 3.4
        x = 60.0
        for ch in a_desc.upper():
            s.text(x, 54.0, ch, "Arial", 9.0, colour="#181729")
            x += TP.width(ch, "Arial", 9.0) + 1.9
        s.gradient(24.0, 772.0, PAGE_W, 820.0, ["#72819C", "#3F557B", "#8B96AD"])
        for i, (left, right) in enumerate((("402, NARIMAN CHAMBERS", "+91-22-4002 7710"),
                                           ("BALLARD ESTATE, FORT, MUMBAI", "AUDIT@DARUWALARANE.EXAMPLE"),
                                           ("MAHARASHTRA, INDIA 400001", "OFFICE - 022 4002 7711"))):
            s.text(56.0, 778.0 + i * 12.6, left, "Arial", 9.0, colour="#FFFFFF")
            s.text(560.0, 778.0 + i * 12.6, right, "Arial", 9.0, colour="#FFFFFF", align="r")
        rp.y = 115.9

    ALM, ARM = 61.5, 519.8

    def apara(text: str, after: float = 12.0, x: float = ALM, bold_words=None):
        rp.para(text, x=x, right=ARM, size=11.0, lead=14.4, after=after, bold_words=bold_words)

    def ahead(text: str, before: float = 4.0):
        rp.gap(before)
        rp.need(50)
        s.text(ALM, rp.y, text, TB, 11)
        rp.y += 25.5

    def plain_page(mark=None):
        rp.page(head=False, foot=False, mark=mark)
        rp.y = 60.0

    letterhead()
    rp.marks["auditor"] = len(s.pages) - 1
    s.text(CX, rp.y, "INDEPENDENT AUDITOR'S REPORT", TB, 11.5, align="c")
    w = TP.width("INDEPENDENT AUDITOR'S REPORT", TB, 11)
    s.line(CX - w / 2, rp.y + 11.0, CX + w / 2, rp.y + 11.0, 0.6)
    rp.y += 29.5
    s.text(ALM + 2, rp.y, f"To the Members of M/s. {co.upper()}", TB, 11)
    rp.y += 26.0
    s.text(ALM + 1, rp.y, "Report on the Audit of the Financial Statements", TB, 11)
    rp.y += 26.0
    s.text(ALM, rp.y, "Opinion", TB, 11)
    rp.y += 25.2
    BOTTOM_SAVE = BOTTOM
    law = ("the Companies Act, 2013 (\"the Act\")" if company else
           "the Income-tax Act, 1961 and the partnership deed" if firm else "the Income-tax Act, 1961")
    names = set(co.upper().split())
    apara(f"We have audited the accompanying financial statements of M/s. {co.upper()} (\"the Company\") which comprise "
          f"the Balance Sheet as at 31st March, {cy} and the Statement of Profit and Loss for the year then ended and "
          "notes to the financial statements, including a summary of the significant accounting policies and other "
          "explanatory information.", bold_words=names)
    apara(f"In our opinion and to the best of our information and according to the explanations given to us, the "
          f"aforesaid financial statements give the information required by {law} in the manner so required and give a "
          "true and fair view in conformity with the accounting principles generally accepted in India, of the state "
          f"of affairs of the company as at March 31, {cy} and its {'profit' if profit_before_tax >= 0 else 'loss'} for "
          "the year ended on that date.")
    ahead("Basis for Opinion")
    apara("We conducted our audit in accordance with the Standards on Auditing (SAs) specified under section 143(10) of "
          "the Companies Act, 2013. Our responsibilities under those Standards are further described in the Auditor's "
          "Responsibilities section of our report. We are independent of the company in accordance with the Code of "
          "Ethics issued by the Institute of Chartered Accountants of India together with the ethical requirements that "
          "are relevant to our audit, and we have fulfilled our other ethical responsibilities. We believe that the audit "
          "evidence we have obtained is sufficient and appropriate to provide a basis for our opinion.")
    ahead("Key Audit Matters")
    apara("Key audit matters are those matters that, in our professional judgment, were of most significance in our audit "
          "of the financial statements of the current period. We have determined that there are no key audit matters to "
          "report for the year under audit.")
    ahead("Information Other than the Financial Statements and Auditor's Report Thereon")
    apara("The company's Board of Directors is responsible for the other information, which comprises the Directors' "
          "report. Our opinion on the financial statements does not cover the other information and we do not express "
          "any form of assurance conclusion thereon.")
    # continuation pages carry no letterhead
    global_bottom = 742.0

    def flow_check():
        if rp.y > global_bottom:
            plain_page()

    flow_check()
    for h, body in (
            ("Management's Responsibility for the Financial Statements",
             ["The company's Board of Directors is responsible for the matters stated in section 134(5) of the Act with "
              "respect to the preparation of these financial statements that give a true and fair view of the financial "
              "position and financial performance of the company in accordance with the accounting principles generally "
              "accepted in India, including the Accounting Standards specified under section 133 of the Act.",
              "This responsibility also includes maintenance of adequate accounting records, selection and application of "
              "appropriate accounting policies, making judgments and estimates that are reasonable and prudent, and the "
              "design, implementation and maintenance of adequate internal financial controls.",
              "In preparing the financial statements, management is responsible for assessing the company's ability to "
              "continue as a going concern, disclosing, as applicable, matters related to going concern and using the "
              "going concern basis of accounting unless management either intends to liquidate the company or to cease "
              "operations, or has no realistic alternative but to do so."]),
            ("Auditor's Responsibilities for the Audit of the Financial Statements",
             ["Our objectives are to obtain reasonable assurance about whether the financial statements as a whole are "
              "free from material misstatement, whether due to error or otherwise, and to issue an auditor's report that "
              "includes our opinion. Reasonable assurance is a high level of assurance, but is not a guarantee that an "
              "audit conducted in accordance with SAs will always detect a material misstatement when it exists.",
              "As part of an audit in accordance with SAs, we exercise professional judgment and maintain professional "
              "scepticism throughout the audit. We also:",
              "•  Identify and assess the risks of material misstatement of the financial statements, design and "
              "perform audit procedures responsive to those risks, and obtain audit evidence that is sufficient and "
              "appropriate to provide a basis for our opinion.",
              "•  Obtain an understanding of internal control relevant to the audit in order to design audit "
              "procedures that are appropriate in the circumstances.",
              "•  Evaluate the appropriateness of accounting policies used and the reasonableness of accounting "
              "estimates and related disclosures made by management.",
              "•  Conclude on the appropriateness of management's use of the going concern basis of accounting and, "
              "based on the audit evidence obtained, whether a material uncertainty exists related to events or "
              "conditions that may cast significant doubt on the company's ability to continue as a going concern.",
              "•  Evaluate the overall presentation, structure and content of the financial statements, including the "
              "disclosures, and whether the financial statements represent the underlying transactions and events in a "
              "manner that achieves fair presentation.",
              "We communicate with those charged with governance regarding, among other matters, the planned scope and "
              "timing of the audit and significant audit findings, including any significant deficiencies in internal "
              "control that we identify during our audit."]),
            ("Report on Other Legal and Regulatory Requirements",
             (["1.  As required by the Companies (Auditor's Report) Order, 2020 (\"the Order\") issued by the Central "
               "Government in terms of section 143(11) of the Act, we give in \"Annexure A\" a statement on the matters "
               "specified in paragraphs 3 and 4 of the Order, to the extent applicable.",
               "2.  As required by section 143(3) of the Act, we report that:",
               "(a) We have sought and obtained all the information and explanations which to the best of our knowledge "
               "and belief were necessary for the purposes of our audit.",
               "(b) In our opinion, proper books of account as required by law have been kept by the company so far as it "
               "appears from our examination of those books.",
               "(c) The Balance Sheet and the Statement of Profit and Loss dealt with by this report are in agreement with "
               "the books of account.",
               "(d) In our opinion, the aforesaid financial statements comply with the Accounting Standards specified under "
               "section 133 of the Act.",
               "(e) On the basis of the written representations received from the directors as on 31st March, "
               f"{cy}, none of the directors is disqualified as on 31st March, {cy} from being appointed as a director in "
               "terms of section 164(2) of the Act.",
               "(f) The company does not have any pending litigations which would impact its financial position.",
               "(g) There were no amounts which were required to be transferred to the Investor Education and Protection "
               "Fund by the company."] if company else
              ["We have obtained all the information and explanations required for our audit, and proper books of "
               "account have been kept. The report in Form 3CD under section 44AB of the Income-tax Act, 1961 is "
               "furnished separately."]))):
        ahead(h)
        for t in body:
            bullet = t.startswith("•")
            apara(t, after=8.0 if bullet else 12.0, x=ALM + (12 if bullet or t[:2] in ("(a", "(b", "(c", "(d", "(e", "(f", "(g") else 0))
            flow_check()
    rp.gap(10)
    if rp.y > 640:
        plain_page()
    for t, f in ((f"For {a_name}", TB), ("Chartered Accountants", TB), (f"Firm Registration No.: {a_frn}", TR),
                 ("", TR), ("", TR), (f"{a_partner}", TB), ("Partner", TR), (f"Membership No.: {a_mno}", TR),
                 (f"UDIN: {udin}", TR), (f"Place: Mumbai | Date: {R.date_words(signed_on) if False else signed_on}", TR)):
        if t:
            s.text(ALM, rp.y, t, f, 11)
        rp.y += 13.8

    if company:
        plain_page(mark="caro")
        s.text(CX, rp.y, "ANNEXURE \"A\" TO THE INDEPENDENT AUDITOR'S REPORT", TB, 11, align="c")
        rp.y += 18
        apara(f"(Referred to in paragraph 1 under 'Report on Other Legal and Regulatory Requirements' section of our "
              f"report to the Members of {co.upper()} of even date)", after=14)
        for t in (
                "(i) (a) The company has maintained proper records showing full particulars, including quantitative "
                "details and situation, of its property, plant and equipment. (b) The property, plant and equipment have "
                "been physically verified by the management at reasonable intervals and no material discrepancies were "
                "noticed on such verification. (c) The company does not hold any immovable property in its name.",
                "(ii) The inventory has been physically verified by the management at reasonable intervals during the "
                "year, and no discrepancies of 10% or more in the aggregate for each class of inventory were noticed. "
                "The quarterly returns or statements filed by the company with the bank are in agreement with the books "
                "of account.",
                "(iii) The company has not made investments in, provided any guarantee or security to, or granted any "
                "loans or advances in the nature of loans to companies, firms, limited liability partnerships or any "
                "other parties during the year.",
                "(iv) The company has not given any loans, made investments or provided guarantees or security to which "
                "the provisions of sections 185 and 186 of the Act apply.",
                "(v) The company has not accepted any deposits or amounts deemed to be deposits within the meaning of "
                "sections 73 to 76 of the Act.",
                "(vi) The maintenance of cost records has not been specified by the Central Government under section "
                "148(1) of the Act for the business activities carried out by the company.",
                "(vii) (a) The company has been generally regular in depositing undisputed statutory dues, including goods "
                "and services tax, provident fund, employees' state insurance, income tax and other material statutory "
                "dues, with the appropriate authorities. (b) There are no statutory dues which have not been deposited "
                "on account of any dispute.",
                "(viii) There were no transactions relating to previously unrecorded income that were surrendered or "
                "disclosed as income in the tax assessments under the Income-tax Act, 1961.",
                "(ix) The company has not defaulted in the repayment of loans or other borrowings or in the payment of "
                "interest thereon to any lender. Term loans were applied for the purpose for which they were obtained.",
                "(x) The company has not raised money by way of initial public offer or further public offer, and has "
                "not made any preferential allotment or private placement of shares during the year.",
                "(xi) No instance of misappropriation by or against the company has been noticed or reported during the "
                "year, and no whistle-blower complaints were received by the company during the year.",
                "(xii) The company is not a Nidhi company; clause 3(xii) of the Order is not applicable.",
                "(xiii) Transactions with the related parties are in compliance with section 188 of the Act where "
                "applicable, and the details have been disclosed in the financial statements.",
                "(xiv) The company is not required to have an internal audit system under section 138 of the Act.",
                "(xv) The company has not entered into any non-cash transactions with directors or persons connected "
                "with them.",
                "(xvi) The company is not required to be registered under section 45-IA of the Reserve Bank of India "
                "Act, 1934.",
                "(xvii) The company has not incurred cash losses in the financial year and in the immediately preceding "
                "financial year." if profit_before_tax > 0 else
                "(xvii) The company has incurred cash losses in the financial year under audit.",
                "(xviii) There has been no resignation of the statutory auditors during the year.",
                "(xix) On the basis of the financial ratios and the ageing and expected dates of realisation of financial "
                "assets and payment of financial liabilities, no material uncertainty exists as on the date of the audit "
                "report that the company is not capable of meeting its liabilities existing at the date of the balance "
                "sheet as and when they fall due within a period of one year from the balance sheet date.",
                "(xx) The provisions of section 135 of the Act are not applicable to the company.",
                "(xxi) The company does not prepare consolidated financial statements; clause 3(xxi) of the Order is "
                "not applicable."):
            apara(t, after=9.0)
            flow_check()
        rp.gap(8)
        if rp.y > 680:
            plain_page()
        for t, f in ((f"For {a_name}", TB), ("Chartered Accountants", TB), (f"Firm Registration No.: {a_frn}", TR),
                     ("", TR), (a_partner, TB), ("Partner", TR), (f"Membership No.: {a_mno}", TR),
                     (f"Place: Mumbai | Date: {signed_on}", TR)):
            if t:
                s.text(ALM, rp.y, t, f, 11)
            rp.y += 13.8
    _ = BOTTOM_SAVE

    # ================================================================ the framed statements
    def frame(x0: float, x1: float, title: str, *, top: float = 44.0, bottom: float = 795.0) -> float:
        s.line(x0, top, x1, top, 1.0)
        s.line(x0, bottom, x1, bottom, 1.0)
        s.line(x0, top, x0, bottom, 1.0)
        s.line(x1, top, x1, bottom, 1.0)
        cxx = (x0 + x1) / 2
        lines = [(co.upper(), 50.5), (idline, 62.0), (office[0], 74.0), (office[1], 86.0), (title, 98.0),
                 ("(All Amounts are in INR Thousands, unless otherwise stated)", 110.5)]
        for t, y in lines:
            s.text(cxx, y, t, TB, 9.6, align="c")
        return 130.0

    def sign_block(y0: float, x_left: float, x_right: float, x_right2: float):
        s.text(x_left, y0, "As per our report of even date", TB, 8.7)
        s.text(x_left, y0 + 12.0, f"For {a_name}", TB, 8.7)
        s.text(x_left, y0 + 24.0, "Chartered Accountants", TB, 8.7)
        for i, (t, f) in enumerate(((a_partner, TB), (f"M.No.: {a_mno}", TR), (f"FRN: {a_frn}", TR),
                                    (f"UDIN: {udin}", TR), ("Place: Mumbai", TR), (f"Date: {dd}", TR))):
            s.text(x_left, y0 + 70.0 + i * 12.0, t, f, 8.7)
        head = f"FOR {co.upper()}" if company else f"FOR {co.upper()}"
        words, ln1 = head.split(" "), ""
        while words and TP.width((ln1 + " " + words[0]).strip(), TB, 8.7) < 215:
            ln1 = (ln1 + " " + words.pop(0)).strip()
        s.text(x_right, y0 + 0.5, ln1, TB, 8.7)
        s.text(x_right, y0 + 12.0, " ".join(words), TB, 8.7)
        people = [p1, p2] if p2 is not p1 else [p1]
        for j, p in enumerate(people):
            x = x_right if j == 0 else x_right2
            s.text(x, y0 + 70.0, p.name, TB, 8.7)
            s.text(x, y0 + 82.0, "Director" if company else ("Partner" if firm else "Proprietor"), TR, 8.7)
            if company and p.din:
                s.text(x, y0 + 94.0, f"DIN: {p.din}", TR, 8.7)

    # --- balance sheet
    rp.page(head=False, foot=False, mark="balance_sheet")
    X0, X1 = 60.0, 527.0
    E = [X0, 258.0, 297.0, 402.0, X1]
    frame(X0, X1, f"BALANCE SHEET AS AT 31st MARCH, {cy}.")
    for i in range(4):
        hatch(s, E[i] + 0.5, 130.0, E[i + 1] - 0.5, 142.0)
    for i, t in enumerate(("Particulars", "Notes", f"As at 31.03.{cy}", f"As at 31.03.{py}")):
        s.text((E[i] + E[i + 1]) / 2, 130.6, t, TB, 8.7, align="c")
    s.line(X0, 130.0, X1, 130.0, 0.8)
    s.line(X0, 142.0, X1, 142.0, 0.8)
    LEAD = 12.1
    bold_rows = {"I. EQUITY AND LIABILITIES", "II.ASSETS"}
    cap_label = "(1) Shareholder's Funds" if company else "(1) Owners' Funds"
    bs = [("I. EQUITY AND LIABILITIES", "", None, None), (cap_label, "", "u", None),
          ("(a) Share Capital" if company else "(a) Capital Account", "1", "sc", None),
          ("(b) Reserves and Surplus", "2", "res", None), ("(c) Money received against share warrants", "", "0", None),
          ("(2) Non-Current Liabilities", "", "u", None), ("(a) Long-Term Borrowings", "3", "ltb", None),
          ("(b) Deferred Tax Liabilities (Net)", "", "dtl", None), ("(c) Other Long Term Liabilities", "", "oltl", None),
          ("(d) Long Term Provisions", "", "0", None), ("(3) Current Liabilities", "", "u", None),
          ("(a) Short-Term Borrowings", "4", "stb", None), ("(b) Trade Payables", "5", "tp", None),
          ("(c) Other Current Liabilities", "6", "ocl", None), ("(d) Short-Term Provisions", "7", "stp", None)]
    y = 156.0
    def bs_rows(rows, y):  # noqa: E306
        for label, note, key, _ in rows:
            if key == "u":
                s.text(X0 + 2.5, y, label, TB, 8.7)
                s.line(X0 + 2.5, y + 10.4, X0 + 2.5 + TP.width(label, TB, 8.7), y + 8.0, 0.6)
            else:
                f = TB if label in bold_rows or label == "(a) Fixed Assets" else TR
                indent = 14.0 if label.startswith("(i") else 0.0
                s.text(X0 + 2.5 + indent, y, label, f, 8.7 if f == TR else 9.0)
                if note:
                    s.text((E[1] + E[2]) / 2, y, note, TR, 8.7, align="c")
                if key:
                    cv = 0 if key == "0" else bc[key]
                    pv = 0 if key == "0" else bp[key]
                    s.text(E[3] - 2.0, y, k(cv), TR, 8.7, align="r")
                    s.text(E[4] - 2.0, y, k(pv), TR, 8.7, align="r")
            y += LEAD
        return y
    y = bs_rows(bs, y) + 2.0
    def total_row(y, label, kc, kp):  # noqa: E306
        top = y + 11.5
        for i in range(4):
            hatch(s, E[i] + 0.5, top, E[i + 1] - 0.5, top + 11.0)
        s.line(X0, top, X1, top, 0.8)
        s.line(X0, top + 11.0, X1, top + 11.0, 0.8)
        s.text((E[0] + E[1]) / 2, top + 0.2, label, TB, 8.7, align="c")
        s.text(E[3] - 2.0, top + 0.2, k(kc), TB, 8.7, align="r")
        s.text(E[4] - 2.0, top + 0.2, k(kp), TB, 8.7, align="r")
        return top + 11.0
    y = total_row(y, "Total Equity & Liabilities", bc["total"], bp["total"])
    assets = [("II.ASSETS", "", None, None), ("(1) Non-Current Assets", "", "u", None),
              ("(a) Fixed Assets", "8", "ppe", None), ("(i) Gross Block", "", "gross", None),
              ("(ii) Depreciation", "", "dep_acc", None), ("(iii) Net Block", "", "ppe", None),
              ("Capital Work in progress", "", "cwip", None), ("(b) Non-current investments", "", "ncinv", None),
              ("(c) Deferred tax assets (net)", "", "dta", None), ("(d) Other non-current assets", "", "onca", None),
              ("(2) Current Assets", "", "u", None), ("(a) Current investments", "", "cinv", None),
              ("(b) Inventories", "9", "inv", None), ("(c) Trade receivables", "10", "tr", None),
              ("(d) Cash and cash equivalents", "11", "cash", None), ("(e) Short-term loans and advances", "12", "stla", None),
              ("(f) Other current assets", "", "oca", None)]
    y = bs_rows(assets, y + 17.0) + 8.0
    yt = total_row(y, "Total Assets", bc["total"], bp["total"])
    for x in E:
        s.line(x, 130.0, x, yt, 0.8)
    s.text(X0 + 3.0, yt + 3.5, "NOTES TO ACCOUNTS", TB, 9.0)
    s.text(X0 + 3.0, yt + 16.5, "Notes referred to above and notes attached there to form an integral part of Balance Sheet",
           TR, 8.7)
    s.text(X0 + 3.0, yt + 28.5, "This is the Balance Sheet referred to in our Report of even date.", TR, 8.7)
    sign_block(max(yt + 52.0, 640.0), X0 + 3.0, 255.0, 400.0)

    # --- profit and loss
    rp.page(head=False, foot=False, mark="profit_and_loss")
    X0, X1 = 30.0, 538.0
    E = [X0, 63.0, 301.0, 340.0, 425.5, X1]
    if pl_heading == "template":
        frame(X0, X1, f"PROFIT & LOSS STATEMENT FOR THE PERIOD ENDED ON 31st MARCH, {cy}.")
        heads = (f"For the Period ended\n31.03.{cy}", f"For the Period ended\n31.03.{py}")
        closing = ("Notes referred to above and notes attached there to form an integral part of Profit & Loss Statement",
                   "This is the Profit & Loss Statement referred to in our Report of even date.")
    else:
        frame(X0, X1, f"STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED 31st MARCH, {cy}.")
        heads = (f"Year ended 31\nMarch {cy}", f"Year ended 31\nMarch {py}")
        closing = ("Notes referred to above and notes attached there to form an integral part of the Statement of Profit "
                   "and Loss", "This is the Statement of Profit and Loss referred to in our Report of even date.")
    for i in range(5):
        hatch(s, E[i] + 0.5, 123.0, E[i + 1] - 0.5, 145.5)
    s.line(X0, 123.0, X1, 123.0, 0.8)
    s.line(X0, 145.5, X1, 145.5, 0.8)
    s.text((E[0] + E[1]) / 2, 128.2, "Sl. No", TB, 8.7, align="c")
    s.text((E[1] + E[2]) / 2, 128.2, "Particulars", TB, 8.7, align="c")
    s.text((E[2] + E[3]) / 2, 128.2, "Notes", TB, 8.7, align="c")
    for j, hd in enumerate(heads):
        top_line, bottom_line = hd.split("\n")
        s.text((E[3 + j] + E[4 + j]) / 2, 124.0, top_line, TB, 8.5, align="c")
        s.text((E[3 + j] + E[4 + j]) / 2, 134.4, bottom_line, TB, 8.5, align="c")
    # rows: (sl, label, note, key or value pair, style) style: "" plain, "b" bold label, "box" boxed bold amounts
    pl = [(147.6, "I", "Revenue from Operations", "13", "rev", ""), (159.2, "II", "Other Income", "14", "oi", ""),
          (181.0, "III", "Total Revenue (I +II)", "", "ti", "box"), (204.0, "IV", "Expenses:", "", None, "u"),
          (215.6, "", "Cost of Materials Consumed", "15", "mat", ""), (227.6, "", "Employee Benefit Expense", "16", "emp", ""),
          (239.6, "", "Finance Costs", "17", "fin", ""), (251.6, "", "Depreciation and Amortization Expense", "8", "dep", ""),
          (263.6, "", "Other Expenses", "18", "oth", ""), (275.4, "", "Total Expenses (IV)", "", "te", "box"),
          (298.7, "V", "Profit before exceptional and extraordinary items and tax", "(III - IV)", "pbt", "boxn"),
          (321.7, "VI", "Exceptional Items", "", "0", ""),
          (338.4, "VII", "Profit before extraordinary items and tax (V - VI)", "", "pbt", "boxn"),
          (357.1, "VIII", "Extraordinary Items", "", "0", ""), (374.8, "IX", "Profit before tax (VII - VIII)", "", "pbt", "box"),
          (398.7, "X", "Tax expense:", "", None, "u"), (410.6, "", "(1) Current tax", "", "tax", ""),
          (422.6, "", " (2) Deferred tax Liability/(Asset)", "", "dtx", ""),
          (446.5, "XI", "Profit(Loss) from the period from continuing operations", "(IX-X)", "pat", "box"),
          (461.9, "XII", "Profit/(Loss) from discontinuing operations", "", "0", ""),
          (475.7, "XIII", "Tax expense of discounting operations", "", "0", ""),
          (489.6, "XIV", "Profit/(Loss) from Discontinuing operations (XII - XIII)", "", "0", "boxn"),
          (505.9, "XV", "Profit/(Loss) for the period (XI + XIV)", "", "pat", "box"),
          (528.8, "XVI", "Less: Distribution of Dividend", "", "0", ""), (540.4, "", "Less: Tax on Dividend Distributed", "", "0", ""),
          (551.8, "", "Profit Carried forwed to Balance sheet", "", "pat", "b"),
          (574.8, "XVII", "Earning per equity share:", "", None, ""), (586.3, "", "     (1) Basic", "", "eps", ""),
          (598.2, "", "     (2) Diluted", "", "eps", "")]
    for y, sl, label, note, key, style in pl:
        bold = style in ("box", "b")
        f = TB if bold else TR
        if sl:
            s.text((E[0] + E[1]) / 2, y, sl, TB, 8.7, align="c")
        s.text(E[1] + 2.5, y, label, TB if style == "u" else f, 8.7)
        if style == "u":
            s.line(E[1] + 2.5, y + 10.4, E[1] + 2.5 + TP.width(label, TB, 8.7), y + 8.0, 0.6)
        if note:
            s.text((E[2] + E[3]) / 2, y, note, TB if note.startswith("(") else TR, 8.7, align="c")
        if key:
            if key == "eps":
                vals = (f"{a['pat'] * 1000 / shares:.2f}", f"{b['pat'] * 1000 / shares:.2f}")
            elif key == "0":
                vals = ("-", "-")
            else:
                vals = (k(a[key]), k(b[key]))
            for j, v in enumerate(vals):
                s.text(E[4 + j] - 2.5, y, v, TB if bold else TR, 8.7, align="r")
        if style in ("box", "boxn"):
            for j in range(2):
                s.line(E[3 + j], y - 4.3, E[4 + j], y - 4.3, 0.8)
                s.line(E[3 + j], y + 12.0, E[4 + j], y + 12.0, 0.8)
    tb = 607.7
    s.line(X0, tb, X1, tb, 0.8)
    for x in E:
        s.line(x, 123.0, x, tb, 0.8)
    s.text(X0 + 2.5, 611.0, closing[0], TBI, 8.7)
    s.text(X0 + 2.5, 622.5, closing[1], TBI, 8.7)
    sign_block(645.5, X0 + 2.5, 297.5, 420.0)

    # ================================================================ notes to accounts (framed tables)
    def note_page(title: str, mark: str | None = None) -> float:
        rp.page(head=False, foot=False, mark=mark)
        x0, x1 = 47.0, 521.0
        s.line(x0, 40.0, x1, 40.0, 1.0)
        s.line(x0, 800.0, x1, 800.0, 1.0)
        s.line(x0, 40.0, x0, 800.0, 1.0)
        s.line(x1, 40.0, x1, 800.0, 1.0)
        cxx = (x0 + x1) / 2
        s.text(cxx, 46.0, co.upper(), TB, 8.7, align="c")
        s.text(cxx, 58.0, title, TB, 8.7, align="c")
        s.text(cxx, 70.0, "(All Amounts are in INR Thousands, unless otherwise stated)", TB, 8.7, align="c")
        return 92.0

    NE = [47.0, 72.0, 330.0, 425.0, 521.0]

    def note(y: float, title: str, rows: list[tuple], total: tuple | None) -> float:
        given = (figures or {}).get("notes", {}).get(title.split()[2])
        if given:                     # the note's lines as the data gives them: (label, current, previous, style) in rupees
            num = lambda t: 0 if t in (None, "-") else (-1 if t.startswith("(") else 1) * int(t.strip("()").replace(",", ""))  # noqa: E731
            want = (num(total[1]), num(total[2])) if total else None
            lines = [(lab, None if c is None else round(c / 1000), None if pv is None else round(pv / 1000), st)
                     for lab, c, pv, st in given]
            if want:                  # the lines add up to the statement's figure, to the thousand
                last = max(i for i, ln in enumerate(lines) if ln[1] is not None)
                lab, c, pv, st = lines[last]
                lines[last] = (lab, c + want[0] - sum(ln[1] or 0 for ln in lines), pv + want[1] - sum(ln[2] or 0 for ln in lines), st)
            sr, rows, under = 0, [], False
            for lab, c, pv, st in lines:
                if st == "b" or c is None:            # a heading takes the number; its lines go under it
                    sr += 1
                    under = True
                    rows.append((str(sr), lab, None, None, "b"))
                elif under:
                    rows.append(("", lab, k(c), k(pv), ""))
                else:
                    sr += 1
                    rows.append((str(sr), lab, k(c), k(pv), ""))
        s.text(NE[0] + 2.0, y, title, TB, 8.5)
        y += 13.0
        for i in range(4):
            hatch(s, NE[i] + 0.5, y, NE[i + 1] - 0.5, y + 20.0)
        s.line(NE[0], y, NE[-1], y, 0.8)
        s.text((NE[0] + NE[1]) / 2, y + 0.6, "Sr.", TB, 8.2, align="c")
        s.text((NE[0] + NE[1]) / 2, y + 9.8, "No", TB, 8.2, align="c")
        s.text((NE[1] + NE[2]) / 2, y + 4.8, "Particulars", TB, 8.5, align="c")
        s.text((NE[2] + NE[3]) / 2, y + 4.8, f"As at 31.03.{cy}", TR, 8.2, align="c")
        s.text((NE[3] + NE[4]) / 2, y + 4.8, f"As at 31.03.{py}", TR, 8.2, align="c")
        top = y
        y += 20.0
        s.line(NE[0], y, NE[-1], y, 0.8)
        y += 1.5
        for sr, label, cv, pv, style in rows:
            if sr:
                s.text((NE[0] + NE[1]) / 2, y, sr, TR, 8.5, align="c")
            f = TB if style == "b" else TR
            s.text(NE[1] + 3.0 + (60 if style == "sub" else 0), y, label, f, 8.5)
            if style == "b":
                s.line(NE[1] + 3.0, y + 10.0, NE[1] + 3.0 + TP.width(label, TB, 8.5), y + 7.8, 0.6)
            if cv is not None:
                s.text(NE[3] - 3.0, y, cv, TR, 8.5, align="r")
                s.text(NE[4] - 3.0, y, pv, TR, 8.5, align="r")
            y += 12.4
        y += 4.0
        if total:
            s.line(NE[0], y, NE[-1], y, 0.8)
            s.text(NE[1] + 3.0, y + 1.0, total[0], TB, 8.5)
            s.text(NE[3] - 3.0, y + 1.0, total[1], TB, 8.5, align="r")
            s.text(NE[4] - 3.0, y + 1.0, total[2], TB, 8.5, align="r")
            y += 13.0
        s.line(NE[0], y, NE[-1], y, 0.8)
        for x in NE:
            s.line(x, top, x, y, 0.8)
        return y + 16.0

    kk = lambda dct, key: k(dct[key])  # noqa: E731
    y = note_page(f"Notes to Balance Sheet as at 31st March, {cy}.", mark="notes")
    if company:
        y = note(y, "Note : 1 Share Capital", [
            ("1", "Authorised Share Capital", None, None, "b"),
            ("", f"{D.inr(PROFILE['authorised_shares'])} Equity Shares of Rs. 10/- each", k(PROFILE["authorised_shares"] / 100),
             k(PROFILE["authorised_shares"] / 100), ""),
            ("2", "Issued, Subscribed & Paid up Capital", None, None, "b"),
            ("", f"{D.inr(shares)} Equity Shares of Rs. 10/- each fully paid", kk(bc, "sc"), kk(bp, "sc"), "")],
            ("Total", kk(bc, "sc"), kk(bp, "sc")))
    else:
        y = note(y, "Note : 1 Capital Account", [
            (str(i + 1), p.name, k(bc["sc"] * (0.6 if i == 0 else 0.4)) if len(e.persons) > 1 else kk(bc, "sc"),
             k(bp["sc"] * (0.6 if i == 0 else 0.4)) if len(e.persons) > 1 else kk(bp, "sc"), "")
            for i, p in enumerate(e.persons)], ("Total", kk(bc, "sc"), kk(bp, "sc")))
    opening = bp["res"]
    y = note(y, "Note : 2 Reserves and Surplus", [
        ("1", "Surplus in Statement of Profit & Loss", None, None, "b"),
        ("", "Balance at the beginning of the year", k(opening), k(bp["res"] - b["pat"]), ""),
        ("", "Add: Profit/(Loss) for the year", k(a["pat"]), k(b["pat"]), ""),
        ("", "Transfers and adjustments", k(bc["res"] - opening - a["pat"]), "-", "")],
        ("Total", kk(bc, "res"), kk(bp, "res")))
    y = note(y, "Note : 3 Long-Term Borrowings", [
        ("1", "Secured", None, None, "b"),
        ("", f"Term Loan from {e.lender}", kk(bc, "ltb"), kk(bp, "ltb"), ""),
        ("", "(Secured by hypothecation of plant and machinery and personal guarantee of directors)", None, None, "")],
        ("Total", kk(bc, "ltb"), kk(bp, "ltb")))
    y = note(y, "Note : 4 Short-Term Borrowings", [
        ("1", "Secured", None, None, "b"),
        ("", f"Cash Credit from {e.bank}", kk(bc, "stb"), kk(bp, "stb"), ""),
        ("2", "Loans from Directors", "-", "-", "")], ("Total", kk(bc, "stb"), kk(bp, "stb")))
    y = note(y, "Note : 5 Trade Payables", [
        ("1", "Dues of micro and small enterprises", k(bc["tp"] * 0.2), k(bp["tp"] * 0.2), ""),
        ("2", "Dues of other creditors", k(bc["tp"] - round(bc["tp"] * 0.2)), k(bp["tp"] - round(bp["tp"] * 0.2)), "")],
        ("Total", kk(bc, "tp"), kk(bp, "tp")))
    y = note_page(f"Notes to Balance Sheet as at 31st March, {cy}.")
    cm = min(1500, bc["ocl"])
    y = note(y, "Note : 6 Other Current Liabilities", [
        ("1", "Current maturities of long-term debt", k(cm), k(min(1500, bp["ocl"])), ""),
        ("2", "Statutory dues payable", k(bc["ocl"] - cm), k(bp["ocl"] - min(1500, bp["ocl"])), "")],
        ("Total", kk(bc, "ocl"), kk(bp, "ocl")))
    y = note(y, "Note : 7 Short-Term Provisions", [("1", "Provision for Income Tax", kk(bc, "stp"), kk(bp, "stp"), "")],
             ("Total", kk(bc, "stp"), kk(bp, "stp")))
    y = note(y, "Note : 8 Fixed Assets (Property, Plant and Equipment)", [
        ("1", "Gross Block", kk(bc, "gross"), kk(bp, "gross"), ""),
        ("2", "Less: Accumulated Depreciation", kk(bc, "dep_acc"), kk(bp, "dep_acc"), ""),
        ("", "Depreciation for the year (charged to Profit & Loss)", k(a["dep"]), k(b["dep"]), "")],
        ("Net Block", kk(bc, "ppe"), kk(bp, "ppe")))
    inv_rows = []
    for i, (lab, share) in enumerate(PROFILE["inventory_lines"], 1):
        last = i == len(PROFILE["inventory_lines"])
        cv = bc["inv"] - sum(round(bc["inv"] * sh) for _, sh in PROFILE["inventory_lines"][:-1]) if last else round(bc["inv"] * share)
        pv = bp["inv"] - sum(round(bp["inv"] * sh) for _, sh in PROFILE["inventory_lines"][:-1]) if last else round(bp["inv"] * share)
        inv_rows.append((str(i), lab, k(cv), k(pv), ""))
    y = note(y, "Note : 9 Inventories", inv_rows, ("Total", kk(bc, "inv"), kk(bp, "inv")))
    over6 = round(bc["tr"] * 0.06)
    y = note(y, "Note : 10 Trade Receivables", [
        ("1", "Outstanding for more than six months", None, None, "b"),
        ("", "a) Unsecured, Considered Good :", k(over6), k(round(bp["tr"] * 0.06)), ""),
        ("2", "Others", None, None, "b"),
        ("", "a) Unsecured, Considered Good :", k(bc["tr"] - over6), k(bp["tr"] - round(bp["tr"] * 0.06)), "")],
        ("Total", kk(bc, "tr"), kk(bp, "tr")))
    y = note_page(f"Notes to Balance Sheet as at 31st March, {cy}.")
    y = note(y, "Note : 11 Cash & Cash Equivalents", [
        ("1", "Cash-in-Hand", None, None, "b"), ("", "Cash Balance", k(bc["cash"] * 0.02), k(bp["cash"] * 0.02), ""),
        ("2", "Bank Balance", None, None, "b"),
        ("", f"Current Account with {e.bank}", k(bc["cash"] - round(bc["cash"] * 0.02)),
         k(bp["cash"] - round(bp["cash"] * 0.02)), "")], ("Total [ A + B ]", kk(bc, "cash"), kk(bp, "cash")))
    y = note(y, "Note : 12 Short Terms Loans and Advances", [
        ("1", "Advances to suppliers", k(bc["stla"] * 0.7), k(bp["stla"] * 0.7), ""),
        ("2", "Balances with Government authorities", k(bc["stla"] - round(bc["stla"] * 0.7)),
         k(bp["stla"] - round(bp["stla"] * 0.7)), "")], ("Total", kk(bc, "stla"), kk(bp, "stla")))
    y = note_page(f"Notes to Profit & Loss Statement for the period ended 31st March, {cy}.")
    rev_rows = []
    for i, (lab, share) in enumerate(PROFILE["revenue_lines"], 1):
        last = i == len(PROFILE["revenue_lines"])
        cv = a["rev"] - sum(round(a["rev"] * sh) for _, sh in PROFILE["revenue_lines"][:-1]) if last else round(a["rev"] * share)
        pv = b["rev"] - sum(round(b["rev"] * sh) for _, sh in PROFILE["revenue_lines"][:-1]) if last else round(b["rev"] * share)
        rev_rows.append((str(i), lab, k(cv), k(pv), ""))
    y = note(y, "Note : 13 Revenue from Operations", rev_rows, ("Total", k(a["rev"]), k(b["rev"])))
    y = note(y, "Note : 14 Other Income", [("1", "Interest Income", k(a["oi"]), k(b["oi"]), "")],
             ("Total", k(a["oi"]), k(b["oi"])))
    y = note(y, "Note : 15 Cost of Materials Consumed", [
        ("1", "Opening Stock", k(bp["inv"] * 0.6), k(bp["inv"] * 0.55), ""),
        ("2", "Add: Purchases", k(a["mat"] + bc["inv"] * 0.6 - bp["inv"] * 0.6), k(b["mat"] + bp["inv"] * 0.05), ""),
        ("3", "Less: Closing Stock", k(bc["inv"] * 0.6), k(bp["inv"] * 0.6), "")], ("Total", k(a["mat"]), k(b["mat"])))
    y = note(y, "Note : 16 Employee Benefit Expense", [
        ("1", "Salaries and Wages", k(a["emp"] * 0.88), k(b["emp"] * 0.88), ""),
        ("2", "Contribution to Provident and Other Funds", k(a["emp"] - round(a["emp"] * 0.88)),
         k(b["emp"] - round(b["emp"] * 0.88)), "")], ("Total", k(a["emp"]), k(b["emp"])))
    y = note(y, "Note : 17 Finance Costs", [
        ("1", "Interest on Term Loans", k(a["fin"] * 0.55), k(b["fin"] * 0.55), ""),
        ("2", "Interest on Cash Credit", k(a["fin"] - round(a["fin"] * 0.55)), k(b["fin"] - round(b["fin"] * 0.55)), "")],
        ("Total", k(a["fin"]), k(b["fin"])))
    y = note(y, "Note : 18 Other Expenses", [
        ("1", "Power and Fuel", k(a["oth"] * 0.4), k(b["oth"] * 0.4), ""),
        ("2", "Rent, Rates and Taxes", k(a["oth"] * 0.15), k(b["oth"] * 0.15), ""),
        ("3", "Repairs and Maintenance", k(a["oth"] * 0.15), k(b["oth"] * 0.15), ""),
        ("4", "Audit Fees", "150", "150", ""),
        ("5", "Administrative and Other Expenses", k(a["oth"] - round(a["oth"] * 0.4) - 2 * round(a["oth"] * 0.15) - 150),
         k(b["oth"] - round(b["oth"] * 0.4) - 2 * round(b["oth"] * 0.15) - 150), "")], ("Total", k(a["oth"]), k(b["oth"])))

    # ================================================================ accounting policies
    rp.page(mark="policies")
    rp.gap(8)
    rp.line(co.upper(), font=TBI, align="c", x=CX, lead=24)
    rp.line("Notes forming part of the financial statements", font=TB, lead=20)
    rp.line("Corporate information", font=TB, lead=18)
    what = ("a private limited company incorporated in India under the Companies Act, 2013" if company else
            "a partnership firm formed in India" if firm else "a proprietorship concern established in India")
    rp.para(f"{co} is {what} on {e.incorporated}. The company is engaged in the business of {PROFILE['business']}.")
    for h, body in (
            ("1. Basis of accounting and preparation of financial statements",
             "The financial statements of the company have been prepared in accordance with the generally accepted "
             "accounting principles in India (Indian GAAP) to comply with the Accounting Standards specified under "
             "section 133 of the Companies Act, 2013 and the relevant provisions of the Act. The financial statements "
             "have been prepared on an accrual basis under the historical cost convention. The accounting policies "
             "adopted are consistent with those followed in the previous year."),
            ("2. Use of estimates",
             "The preparation of the financial statements requires the management to make estimates and assumptions "
             "considered in the reported amounts of assets and liabilities and the reported income and expenses during "
             "the year. Management believes that the estimates used are prudent and reasonable. Differences between the "
             "actual results and the estimates are recognised in the periods in which the results are known."),
            ("3. Revenue recognition",
             "Revenue from the sale of goods is recognised when the significant risks and rewards of ownership have "
             "passed to the buyer, which is generally on dispatch of the goods. Revenue is stated net of goods and "
             "services tax. Interest income is recognised on a time proportion basis."),
            ("4. Property, plant and equipment and depreciation",
             "Property, plant and equipment are stated at cost less accumulated depreciation. Cost includes freight, "
             "duties and other incidental expenses relating to acquisition and installation. Depreciation is provided on "
             "the written down value method over the useful lives prescribed in Schedule II to the Companies Act, 2013."),
            ("5. Inventories", PROFILE["inventory_policy"]),
            ("6. Employee benefits",
             "Contributions to the provident fund are charged to the Statement of Profit and Loss in the year in which "
             "they fall due. Gratuity is provided for on the basis of the amount payable as if all employees were to "
             "leave at the balance sheet date."),
            ("7. Borrowing costs",
             "Borrowing costs attributable to the acquisition of qualifying assets are capitalised as part of the cost of "
             "such assets. Other borrowing costs are recognised as an expense in the period in which they are incurred."),
            ("8. Taxes on income",
             "Current tax is determined on the taxable income for the year in accordance with the Income-tax Act, 1961. "
             "Deferred tax is recognised on timing differences between taxable and accounting income, subject to "
             "prudence; deferred tax assets are recognised only where there is reasonable certainty of realisation."),
            ("9. Provisions and contingent liabilities",
             "A provision is recognised when the company has a present obligation as a result of a past event and it is "
             "probable that an outflow of resources will be required to settle it. Contingent liabilities are disclosed "
             "by way of notes. There are no contingent liabilities as at the balance sheet date."),
            ("10. Earnings per share",
             "Basic earnings per share are computed by dividing the net profit after tax by the weighted average number "
             "of equity shares outstanding during the year. There are no dilutive potential equity shares."),
            ("11. Related party disclosures",
             "Key managerial personnel: " + ", ".join(f"{p.name} ({p.designation})" for p in e.persons) + ". Directors' "
             "remuneration and the balances with directors at the year end are included under employee benefit expense "
             "and other current liabilities respectively."),
            ("12. Previous year figures",
             "Previous year's figures have been regrouped and rearranged wherever necessary to make them comparable with "
             "the current year's figures.")):
        rp.heading(h, before=2, after=17)
        rp.para(body, after=12)
    rp.gap(8)
    rp.need(150)
    rp.line("As per our report of even date", lead=13.2)
    rp.line(f"For {a_name}", font=TB, lead=13.2)
    rp.line("Chartered Accountants", font=TB, lead=40)
    y0 = rp.y
    for i, (t, f) in enumerate(((a_partner, TB), (f"M.No.: {a_mno}", TR), (f"FRN: {a_frn}", TR), ("Place: Mumbai", TR),
                                (f"Date: {dd}", TR))):
        s.text(LM, y0 + i * 13.2, t, f, 11)
    for j, p in enumerate([p1, p2] if p2 is not p1 else [p1]):
        s.text(LM + 200 + j * 140, y0 - 53, f"For {co.upper()}" if j == 0 else "", TB, 10.5)
        s.text(LM + 200 + j * 140, y0, p.name, TB, 11)
        s.text(LM + 200 + j * 140, y0 + 13.2, "Director" if company else "Partner" if firm else "Proprietor", TR, 11)
        if company and p.din:
            s.text(LM + 200 + j * 140, y0 + 26.4, f"DIN: {p.din}", TR, 11)

    # ================================================================ lists of shareholders and directors
    if company:
        rp.page(mark="lists")
        rp.gap(30)
        rp.title("LIST OF SHAREHOLDERS", after=40)
        holders = [(e.persons[i], n) for i, n in PROFILE["holders"]]
        rows = [(("S.NO", "NAME OF THE\nSHARE HOLDER", "NUMBER\nOF\nSHARES\nHELD", "FACE\nVALUE\nOF THE\nSHARES\nHELD",
                  "TOTAL\nAMOUNT\nOF SHARE\nCAPITAL", "% OF\nSHARE\nCAPITAL"), None)]
        for i, (p, n) in enumerate(holders, 1):
            first, _, last = p.name.upper().rpartition(" ")
            rows.append(((str(i), f"{first}\n{last}" if first else last, D.inr(n), "10", D.inr(n * 10),
                          f"{round(n * 100 / shares)}%"), None))
        rp.boxed_table([60.0, 96.0, 186.0, 235.0, 284.0, 337.0, 392.0], rows, size=10.5, row_h=12.4)
        rp.gap(40)
        rp.line("Thanking you,", lead=24)
        rp.line("Yours truly,", lead=46)
        rp.line(f"FOR {co.upper()}", font=TB, lead=60)
        rp.line(p1.name.upper(), lead=12.4)
        rp.line("Director", lead=12.4)
        rp.line(f"DIN: {p1.din}", lead=60)
        rp.line(f"Date: {dd}", lead=12.4)
        rp.line(f"Place: {R.town(e.office)}", lead=12.4)

        rp.page()
        rp.gap(30)
        rp.title("LIST OF DIRECTORS", after=40)
        rows = [(("S.NO", "DIN", "NAME OF THE\nDIRECTOR", "DESIGNATION", "ADDRESS"), None)]
        for i, p in enumerate(e.persons, 1):
            first, _, last = p.name.upper().rpartition(" ")
            addr = "\n".join(R.halves(p.address)[0].split(", ")) + ",\n" + R.halves(p.address)[1].replace(", ", ",\n") + "."
            rows.append(((str(i), p.din, f"{first}\n{last}", "DIRECTOR", addr), None))
        rp.boxed_table([60.0, 92.0, 152.0, 240.0, 330.0, 455.0], rows, size=10.5, row_h=12.4)
        rp.gap(40)
        rp.line("Thanking you,", lead=24)
        rp.line("Yours truly,", lead=46)
        rp.line(f"FOR {co.upper()}", font=TB, lead=60)
        rp.line(p1.name.upper(), lead=12.4)
        rp.line("Director", lead=12.4)
        rp.line(f"DIN: {p1.din}", lead=60)
        rp.line(f"Date: {dd}", lead=12.4)
        rp.line(f"Place: {R.town(e.office)}", lead=12.4)

    pages = s.pages
    n = len(pages)
    if page_numbers:
        for i, ops in enumerate(pages, 1):
            ops.append(("t", 520.0, PAGE_H - 26.0, f"Page {i} of {n}", "Helvetica", 8, "r", (0, 0, 0), 1.0))
    gone = {2: "balance_sheet", 3: "profit_and_loss"}.get(drop_page or 0)
    if gone:
        del pages[rp.marks[gone]]
    return s.render()
