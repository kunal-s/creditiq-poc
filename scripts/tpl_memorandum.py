"""The Memorandum and Articles of Association as the registry's SPICe+ e-forms print them from the browser, filed as one
document: Form INC-33, the e-Memorandum (Table A, three pages), then Form INC-34, the e-Articles (Table F, ten pages).
Positions, faces, sizes, rules and fills are measured from printouts of the two forms; the articles are the statutory
Table F text, broken into lines exactly as the form's text box breaks them.

Faces: the forms set their labels in Calibri, their field values and the articles in Arial and their title boxes in
Times New Roman. Calibri is not installed, so a Calibri label is set in Noto Sans (OFL) at 90 per cent of the size
(Calibri's cap height) and narrowed to Calibri's own advance widths (CALIBRI below), so each line is as long as the
form's and wraps where the form wraps. Arial and Times are their Liberation metric twins.

Never drawn (CLAUDE.md rule 8): the digital signatures (the DSC columns stay blank) and the stylised logo letter of
the form titles, which is set as a plain italic letter. Every page carries the one-line footer.
"""

from __future__ import annotations

import datetime as dt
import re

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont

import template_pages as TP

for _name, _file in (("NotoSans-Regular", "noto/NotoSans-Regular.ttf"), ("NotoSans-Bold", "noto/NotoSans-Bold.ttf"),
                     ("NotoSans-BoldItalic", "noto/NotoSans-BoldItalic.ttf"),
                     ("Arial-BoldItalic", "liberation/LiberationSans-BoldItalic.ttf"),
                     ("DejaVuSans-Bold", "dejavu/DejaVuSans-Bold.ttf"),
                     ("TimesNewRoman-BoldItalic", "liberation/LiberationSerif-BoldItalic.ttf")):
    if _name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_name, str(TP.SYSTEM / _file)))

# Calibri advance widths (thousandths of an em; the same as Carlito's), regular, bold and bold italic.
_CAL = dict(zip(" !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
                (226, 326, 401, 498, 507, 715, 682, 221, 303, 303, 498, 498, 250, 306, 252, 386, 268, 268, 498, 498, 498,
                 463, 894, 307, 386, 307, 498, 498, 291, 314, 460, 314, 498)))
_CAL.update(dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (579, 544, 533, 615, 488, 459, 631, 623, 252, 319, 520, 420, 855, 646, 662,
                                                   517, 673, 543, 459, 487, 642, 567, 890, 519, 487, 468))))
_CAL.update(dict(zip("abcdefghijklmnopqrstuvwxyz", (479, 525, 423, 525, 498, 305, 471, 525, 230, 239, 455, 230, 799, 525, 527,
                                                   525, 525, 349, 391, 335, 525, 452, 715, 433, 453, 395))))
_CAL.update({d: 507 for d in "0123456789"})
_CALB = dict(_CAL)
_CALB.update(dict(zip(" !\"'(),-./:;?", (226, 326, 438, 233, 312, 312, 258, 306, 267, 430, 276, 276, 463))))
_CALB.update(dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (606, 561, 529, 630, 488, 459, 637, 631, 267, 331, 547, 423, 874, 659, 676,
                                                    532, 686, 563, 473, 495, 653, 591, 906, 551, 520, 478))))
_CALB.update(dict(zip("abcdefghijklmnopqrstuvwxyz", (494, 537, 418, 537, 503, 316, 474, 537, 246, 255, 480, 246, 813, 537, 538,
                                                    537, 537, 355, 399, 347, 537, 473, 745, 459, 474, 397))))
_CALBI = dict(_CALB)
_CALBI.update(dict(zip("abcdefghijklmnopqrstuvwxyz", (527, 527, 411, 527, 491, 316, 527, 527, 245, 255, 479, 245, 803, 527, 527,
                                                     527, 527, 352, 394, 346, 527, 469, 745, 459, 470, 397))))
_CALBI.update({"B": 560, "C": 518, "E": 487, "F": 458, "O": 668, "R": 562, "S": 465})
CALIBRI = {"cal": _CAL, "calb": _CALB, "calbi": _CALBI}

# face: (font drawn, the template face's baseline below a word's top per point, size factor)
FACES = {
    "cal": ("NotoSans-Regular", 0.732, 0.90), "calb": ("NotoSans-Bold", 0.732, 0.90),
    "calbi": ("NotoSans-BoldItalic", 0.732, 0.90),
    "arial": ("Arial", 0.789, 1.0), "arialb": ("Arial-Bold", 0.789, 1.0), "arialbi": ("Arial-BoldItalic", 0.789, 1.0),
    "times": ("TimesNewRoman", 0.784, 1.0), "timesb": ("TimesNewRoman-Bold", 0.784, 1.0),
    "logo": ("TimesNewRoman-BoldItalic", 0.784, 1.0), "verdana": ("DejaVuSans", 0.791, 0.93),
    "plus": ("DejaVuSans-Bold", 0.791, 1.0),
}
LIMIT = 788.3                       # the lowest a line of the printout may reach before the browser starts a new page
STATE_CODES = {"Maharashtra": "MH", "Karnataka": "KA", "Telangana": "TG", "Tamil Nadu": "TN", "Gujarat": "GJ",
               "Delhi": "DL", "West Bengal": "WB", "Uttar Pradesh": "UP", "Kerala": "KL", "Rajasthan": "RJ",
               "Haryana": "HR", "Punjab": "PB", "Andhra Pradesh": "AP", "Madhya Pradesh": "MP", "Goa": "GA"}
CAPITAL = 10_000_000              # the authorised capital in clause 5 (rupees); a generator may set its own
WITNESS = ("Rustom Daruwala", "402, Nariman Chambers, Fort, Mumbai - 400001")   # the witnessing CA's father; office

# The objects clause (fictional): 3(a) and 3(b), numbered paragraphs; "\t" puts the text at the form's tab stop.
OBJECTS_A = (
    "1. Designing, fabricating, machining and erecting structural steel work, pressure vessels, storage tanks and heavy "
    "sheet metal assemblies to the drawings and specifications of industrial customers in India and abroad.",
    "",
    "2. To carry on the business of manufacturers, fabricators, assemblers, repairers, processors, importers, exporters, "
    "buyers, sellers and dealers in all kinds of structural steel sections, plates, pipes, tubes, castings, forgings, "
    "fasteners and engineering components, and to undertake the design, detailing, cutting, bending, rolling, welding, "
    "machining, blasting, painting, galvanising, testing, inspection, packing, transport and erection of steel structures, "
    "process equipment, conveyors, material handling systems, ducting, chimneys, platforms, sheds and pre-engineered "
    "buildings for factories, warehouses, refineries, power plants, ports and infrastructure projects, either on its own "
    "account or on job work, sub-contract or turnkey basis, and to provide engineering, drafting, quality assurance, site "
    "supervision, maintenance and repair services connected with any of these activities, and to set up, acquire, run "
    "and manage workshops, yards, machine shops, paint shops and testing facilities for any of the said purposes.",
)
OBJECTS_B = (
    "1. To purchase, take on lease or licence, hire or otherwise acquire and to build, construct, maintain, alter and "
    "improve any land, buildings, sheds, workshops, cranes, plant, machinery, welding sets, machine tools, vehicles, "
    "equipment and other movable or immovable property which may be necessary or convenient for the business of the "
    "company, and to sell, lease, mortgage or otherwise dispose of the same or any part thereof when no longer required, "
    "and to apply for, purchase or otherwise acquire licences, approvals, designs, drawings, technical know-how and "
    "processes from any person in India or abroad and to grant licences in respect of the same, and to undertake "
    "research, development and testing of new designs, materials, welding procedures and methods of fabrication.",
    "",
    "2.\tTo borrow or raise money or secure the payment of money in such manner as the company may think fit and in "
    "particular by the issue of debentures, whether perpetual or otherwise, charged upon all or any of the company's "
    "property both present and future, including its uncalled capital, to open and operate current, cash credit, "
    "overdraft and other accounts with any bank or financial institution, to draw, make, accept, endorse, discount and "
    "negotiate cheques, bills of exchange, promissory notes, letters of credit and other negotiable or transferable "
    "instruments, and to give guarantees, indemnities and performance bonds for the due performance of contracts by the "
    "company, subject to the provisions of the Companies Act, 2013 and the directions of the Reserve Bank of India, and "
    "to invest and deal with the moneys of the company not immediately required in such manner as the Board may decide, "
    "and to lend or advance money or give credit to customers, suppliers and others having dealings with the company on "
    "such terms as may seem expedient.",
    "",
    "3.\tTo employ, train and remunerate engineers, draughtsmen, welders, fitters, machinists, supervisors, inspectors, "
    "consultants, agents and other staff, to establish provident fund, gratuity, welfare and other benefit schemes for "
    "them, and to enter into contracts, joint ventures, partnerships or other arrangements with any person, firm, "
    "company, government or authority for carrying on any business which the company is authorised to carry on, to "
    "tender for, undertake and execute contracts for the supply, fabrication and erection of steel structures and "
    "equipment, to appoint dealers, distributors and sub-contractors, to insure the property and undertaking of the "
    "company against any risk, to obtain any registration, certification or approval from any standards body, "
    "inspection agency, classification society or government department, to establish branches, workshops, depots and "
    "offices in any part of India or abroad, to purchase or acquire the whole or any part of the business, property and "
    "liabilities of any person or company carrying on any business which the company is authorised to carry on, to pay "
    "all costs and expenses incurred in the "
    "formation and registration of the company, to amalgamate with any other company having objects similar to those "
    "of the company, to distribute any of the property of the company among the members in specie in the event of "
    "winding up, and to do all such other lawful things as are incidental or conducive to the attainment of the above "
    "objects or any of them, and to carry out the same in any part of India or elsewhere.",
)


class Form(TP.Sheet):
    """A Sheet that sets text in the template's faces (see FACES) and draws the e-forms' boxes and buttons."""

    def __init__(self):
        super().__init__(595.32, 841.92)

    def width(self, s: str, face: str, size: float) -> float:
        if face in CALIBRI:
            table = CALIBRI[face]
            return sum(table.get(ch, 500) for ch in s) * size / 1000
        font, _, k = FACES[face]
        return stringWidth(s, font, size * k)

    def t(self, x, top, s: str, face: str = "cal", size: float = 10.68, *, align: str = "l", colour: str = "#000000",
          fit: float | None = None):
        """Text whose top is the template word's top in the template's face; Calibri is narrowed to its own widths."""
        if not s:
            return
        font, asc, k = FACES[face]
        base = top + asc * size
        fsize = size * k
        fw = fit if fit is not None else (self.width(s, face, size) if face in CALIBRI else None)
        self.text(x, base - TP._asc(font) * fsize, s, font, fsize, align=align, colour=colour, fit_w=fw)

    def wrap(self, text: str, face: str, size: float, room: float, first: float | None = None) -> list[str]:
        """Words into lines no wider than room (the first line no wider than `first`)."""
        lines, cur = [], ""
        for w in text.split(" "):
            trial = f"{cur} {w}" if cur else w
            if cur and self.width(trial, face, size) > (first if first is not None and not lines else room):
                lines.append(cur)
                cur = w
            else:
                cur = trial
        return lines + [cur]

    def justified(self, x, top, room, lines: list[str], face: str, size: float, pitch: float):
        """Lines set flush to both edges (the last one flush left), as the form's text boxes set them."""
        for k, ln in enumerate(lines):
            words = ln.split()
            if k == len(lines) - 1 or len(words) < 2:
                self.t(x, top + k * pitch, ln, face, size)
                continue
            gap = (room - sum(self.width(w, face, size) for w in words)) / (len(words) - 1)
            xx = x
            for w in words:
                self.t(xx, top + k * pitch, w, face, size)
                xx += self.width(w, face, size) + gap

    def rect(self, x0, top, x1, bottom, lw: float = 0.6):
        self.box(x0, top, x1, bottom, lw)

    def cells(self, edges, top, bottom):
        for x0, x1 in zip(edges, edges[1:]):
            self.rect(x0, top, x1, bottom)

    def checkbox(self, x0, top, ticked: bool = False):
        self.fill(x0, top, x0 + 9.8, top + 9.8, "#FFFFFF")
        self.rect(x0, top, x0 + 9.8, top + 9.8)
        if ticked:
            self.line(x0 + 0.5, top + 0.5, x0 + 9.3, top + 9.3, 0.6)
            self.line(x0 + 0.5, top + 9.3, x0 + 9.3, top + 0.5, 0.6)

    def button(self, x0, top, x1, bottom, label: str, lx: float, ltop: float):
        """A grey push button with the browser's bevel: black frame, white light top and left, grey shade below."""
        self.fill(x0, top, x1, bottom, "#D4D0C8")
        self.line(x0, top + 0.72, x1, top + 0.72, 0.48, "#FFFFFF")
        self.line(x0 + 0.72, top, x0 + 0.72, bottom, 0.48, "#FFFFFF")
        self.line(x0, bottom - 0.84, x1, bottom - 0.84, 0.72, "#808080")
        self.line(x1 - 0.84, top, x1 - 0.84, bottom, 0.72, "#808080")
        for a in ((x0, top + 0.24, x1, top + 0.24), (x0, bottom - 0.24, x1, bottom - 0.24),
                  (x0 + 0.24, top, x0 + 0.24, bottom), (x1 - 0.24, top, x1 - 0.24, bottom)):
            self.line(*a, lw=0.48)
        self.t(lx, ltop, label, "arial", 9.72)

    def page_numbers(self, first: int, x: float, top: float):
        """'Page n of N' on the pages from index `first` to the last."""
        pages = self.pages[first:]
        keep = self.ops
        for n, ops in enumerate(pages, 1):
            self.ops = ops
            self.t(x, top, f"Page {n} of {len(pages)}", "arial", 8.76)
        self.ops = keep


# --- the subscribers --------------------------------------------------------------------------------------------

def _subscribers(e, names, R):
    """Each subscriber's particulars as the forms print them."""
    out = []
    for n in names:
        p = next((p for p in e.persons if p.name == n), None)
        rel, occ, shares = R.SUBSCRIBERS.get(n, ("", "business", 5_000))
        m = re.match(r"(son|daughter|wife) of (.+)", rel)
        kin = ({"son": "S/O", "daughter": "D/O", "wife": "W/O"}[m[1]], m[2]) if m else ("S/O", "-")
        addr = p.address if p else "Sector 7, Vashi, Navi Mumbai 400703, Maharashtra"
        din = p.din if p else f"0{R.num('DIN', n)}"
        dob = R.dmy(p.dob) if p else (f"{1 + int(R.num(n, 'd', digits=2)) % 28:02d}/"
                                      f"{1 + int(R.num(n, 'm', digits=2)) % 12:02d}/{1972 + int(R.num(n, 'y', digits=2)) % 12}")
        out.append({"name": n, "kin": kin, "addr": addr, "din": din, "dob": dob, "shares": shares,
                    "occ": {"business": "BUSINESS"}.get(occ, "PROFESSIONAL")})
    return out


def _signed(e, R) -> dt.date:
    """The day the subscribers signed: six days before the company was incorporated."""
    d, m, y = R.parse_date(e.incorporated)
    return dt.date(y, m, d) - dt.timedelta(days=6)


def _place(e) -> str:
    city = e.office.split(", ")[-2] if e.office.count(", ") >= 2 else e.state
    return re.sub(r"\s*\d{6}$", "", city)


# --- Form INC-33 ------------------------------------------------------------------------------------------------

def _objects_box(s: Form, top: float, paras, right: float) -> float:
    """A grey field box of the objects clause from `top`, running on to the next page where the printout breaks;
    returns the bottom of its last part."""
    room = 540.3
    lines = []
    for para in paras:
        if "\t" in para:
            no, text = para.split("\t")
            parts = s.wrap(text, "arial", 8.76, room, first=room - 35.04)
            lines.append(((18.48, no), (53.52, parts[0])))
            lines += [((18.48, x),) for x in parts[1:]]
        else:
            lines += [((18.48, x),) for x in s.wrap(para, "arial", 8.76, room)]

    def close(part_top, bottom):
        s.fill(17.4, part_top, right, bottom, "#F4F4F4")
        s.ops.insert(0, s.ops.pop())                  # under the text already set on this page
        s.rect(17.5, part_top + 0.1, right, bottom)

    part_top, y, first = top, top + 2.7, True
    for ln in lines:
        if y + 9.96 > LIMIT:
            close(part_top, y + 0.54)
            s.page()
            part_top, y, first = 53.2, 52.73, False
        for x, text in ln:
            s.t(x, y, text, "arial", 8.76)
        y += 9.96
    bottom = y - 9.96 + (9.5 if first else 9.83)
    close(part_top, bottom)
    return bottom


def _inc33(s: Form, e, subs, R, signed: dt.date):
    # page 1: the form's title box
    s.rect(24.5, 89.2, 555.1, 204.4)
    s.t(39.72, 106.54, "[Pursuant to Schedule I (see sections 4 and 5) to")
    s.t(39.72, 119.38, "the Companies Act, 2013] FORM NO. INC-33")
    s.t(379.57, 129.96, "SPIC", "timesb", 19.44)
    s.t(423.83, 117.74, "e", "logo", 35.04)
    s.t(438.48, 125.57, "+", "logo", 29.16)
    s.t(453.06, 129.96, "MOA", "timesb", 19.44)
    s.t(361.32, 154.30, "(e-Memorandum of Association)")
    s.t(27.96, 228.46, "*", "calb", colour="#FF0000")
    s.t(37.80, 227.02, "Table applicable to company as notified under schedule I of the companies Act, 2013", "calb")
    s.rect(430.2, 220.8, 561.6, 240.5)
    s.t(431.17, 227.09, "A", "arialb", 8.76)
    s.t(27.60, 263.86, "Table A", "calb")
    s.line(27.6, 272.9, 60.8, 272.9, 0.48)
    s.t(60.84, 263.86, "- MEMORANDUM OF ASSOCIATION OF A COMPANY LIMITED BY SHARES")
    s.t(20.52, 307.66, "1. The Name of the Company is")
    s.fill(183.8, 303.0, 551.6, 346.9, "#F4F4F4")
    s.rect(183.8, 303.1, 551.5, 346.9)
    s.t(184.80, 305.69, e.name.upper(), "arial", 8.76)
    s.t(18.84, 360.10, "2.The Registered office of the company will be situated in the state of")
    s.rect(351.0, 356.0, 560.8, 382.3)
    s.t(351.97, 365.57, f"{e.state}-{STATE_CODES.get(e.state, e.state[:2].upper())}", "arial", 8.76)
    s.t(18.84, 393.71, "3.(a)The objects to be pursued by the company on its incorporation are")
    y = _objects_box(s, 415.3, OBJECTS_A, 559.0)
    s.t(18.84, y + 4.44, "3.(b)Matters which are necessary for furtherance of the objects specified in clause 3(a) are")
    y = _objects_box(s, y + 26.1, OBJECTS_B, 558.0)

    # page 2: liability, capital and the subscription clause, placed from the end of the objects box
    if y + 230 > LIMIT:
        s.page()
        y = 49.0
    dy = y - 102.4
    s.t(18.84, 106.78 + dy, "4.The liability of the member(s) is limited and this liability is limited to the amount unpaid, "
                            "if any, on the shares held by")
    s.t(18.84, 119.62 + dy, "them.")
    capital = CAPITAL
    s.t(18.84, 150.58 + dy, "5.The share capital of the company is")
    s.rect(211.4, 146.4 + dy, 412.1, 171.1 + dy)
    s.t(212.5, 155.4 + dy, f"{capital:,.2f}", "arial", 8.76)
    s.t(430.34, 150.58 + dy, "rupees, divided into,")
    s.cells([17.5, 100.7, 179.3, 262.6, 350.9, 437.4, 518.2], 190.1 + dy, 225.0 + dy)
    s.t(18.48, 204.05 + dy, f"{capital // 10:,.2f}", "arial", 8.76)
    s.t(101.64, 204.05 + dy, "Equity", "arial", 8.76)
    s.t(180.72, 202.42 + dy, "shares of")
    s.t(263.6, 204.05 + dy, "10.00", "arial", 8.76)
    s.t(350.88, 202.45 + dy, "rupees each", "arial", 9.72)
    s.t(438.36, 204.05 + dy, ",and", "arial", 8.76)
    s.t(27.60, 241.78 + dy, "6")
    s.checkbox(62.1, 240.65 + dy, ticked=True)
    for k, ln in enumerate(("We, the several persons, whose names and addresses are subscribed, are desirous of being formed",
                            "into a company in pursuance of this memorandum of association, and we respectively agree to take",
                            "the number of shares in the capital of the company set against our respective names:")):
        s.t(78.84, 240.46 + dy + k * 12.84, ln)
    s.checkbox(62.1, 301.95 + dy)
    for k, ln in enumerate(("I, whose name and address is given below, am desirous of forming a company in pursuance of this",
                            "memorandum of association and agree to take all the shares in the capital of the company",
                            "(Applicable in case of one person company):")):
        s.t(78.84, 298.78 + dy + k * 12.6, ln)

    # page 3: the subscribers and the witness
    s.page()
    s.cells([17.5, 43.9, 576.2], 53.3, 80.4)
    s.t(18.84, 61.66, "S.No.")
    s.t(271.08, 61.66, "Subscriber Details")
    s.cells([17.5, 43.9, 266.6, 351.6, 433.4, 495.0, 576.2], 80.4, 152.4)
    s.t(45.24, 111.22, "Name, Address, Description and Occupation")
    s.t(268.08, 104.86, "DIN/PAN/Passport")
    s.t(268.08, 117.70, "Number")
    s.t(352.92, 104.86, "No. of shares")
    s.t(352.92, 117.70, "taken")
    s.t(434.88, 111.22, "DSC")
    s.t(496.44, 111.22, "Dated")
    y = 152.4
    for i, sub in enumerate(subs, 1):
        text = f"{sub['name'].upper()}   Address;{sub['addr'].upper()}  Occupation ; {sub['occ']}"
        lines = s.wrap(text, "cal", 9.72, 265.0 - 45.4)
        h = max(62.5, len(lines) * 11.86 + 3.0)
        s.cells([17.5, 43.9, 266.6, 351.6], y, y + h)
        s.cells([433.4, 495.0, 576.2], y, y + h)
        for x0, x1 in ((351.6, 386.8), (386.8, 433.4)):
            s.rect(x0, y, x1, y + 31.0)
            s.rect(x0, y + 31.0, x1, y + h)
        s.t(18.84, y + 0.73, str(i), "arial", 9.72)
        for k, ln in enumerate(lines):
            s.t(45.4, y - 0.1 + k * 11.86, ln, "cal", 9.72)
        s.t(268.2, y + 3.0, sub["din"], "cal", 9.72)
        s.t(352.1, y + 0.2, f"{sub['shares']:,}", "cal", 9.72)
        s.t(387.72, y + 2.57, "Equity", "arial", 8.76)
        s.t(387.72, y + 33.65, "Preference", "arial", 8.76)
        s.t(495.5, y + 0.4, signed.strftime("%d/%m/%y"), "cal", 9.72)
        y += h
    total = sum(sub["shares"] for sub in subs)
    shown = f"{total:,.2f}"
    while s.width(shown, "arial", 8.76) > 386.5 - 352.4:
        shown = shown[:-1]                           # wider than its cell: the form shows only what fits
    s.t(352.4, y + 0.4, shown, "arial", 8.76)
    s.cells([17.5, 351.5], y, y + 53.1)
    s.rect(433.1, y, 637.4, y + 53.1)
    for x0, x1 in ((351.5, 386.5), (386.5, 433.1)):
        s.rect(x0, y, x1, y + 26.4)
        s.rect(x0, y + 26.4, x1, y + 53.1)
    s.t(143.64, y + 21.39, "Total Shares taken", "arial", 9.72)
    s.t(387.48, y + 2.71, "Equity", "arial", 8.76)
    s.t(387.48, y + 28.99, "Preference", "arial", 8.76)
    y += 53.1 + 3.2
    s.rect(17.5, y, 578.5, y + 23.4)
    s.t(259.68, y + 6.61, "Signed before Me", "arial", 9.72)
    y += 23.4
    s.cells([17.5, 185.9, 356.0, 448.6, 504.5, 578.5], y, y + 72.1)
    s.t(18.84, y + 30.94, "Name")
    s.t(187.37, y + 30.94, "Address, Description and Occupation")
    for k, ln in enumerate(("DIN/PAN/Passport", "Number/", "Membership", "Number")):
        s.t(357.36, y + 11.62 + k * 12.84, ln)
    s.t(449.88, y + 30.94, "DSC")
    s.t(505.92, y + 30.94, "Dated")
    y += 72.1
    h = 86.8
    s.cells([17.5, 67.2, 185.9, 356.0, 448.6, 504.5, 578.5], y, y + h)
    ca = R.AUDITOR[3]
    s.t(18.48, y + 2.59, "ACA", "arial", 8.76)
    s.t(68.52, y + 0.75, ca.upper(), "arial", 9.72)
    witness = (f"{ca} S/o: {WITNESS[0]} Address: {WITNESS[1]},Occupation: Chartered Accountant I, witness to "
               f"subscriber(s), who have subscribed and signed in my presence on {signed.strftime('%d/%m/%Y')} at "
               f"{_place(e)}, further I have verified their identity details for their identification and satisfied "
               "myself of their identification particulars as filled in")
    for k, ln in enumerate(s.wrap(witness, "cal", 9.9, 163.0)):
        if 0.9 + k * 11.68 + 9.0 > h:
            break                                   # the box shows only what fits
        s.t(187.4, y + 0.9 + k * 11.68, ln, "cal", 9.9)
    s.t(357.5, y + 3.3, R.AUDITOR[4], "cal", 9.72)
    s.t(504.9, y + 0.5, signed.strftime("%d/%m/%y"), "cal", 9.72)
    y += h
    s.button(170.6, y + 16.7, 249.6, y + 42.0, "Modify", 195.72, y + 24.23)
    s.button(280.1, y + 16.7, 380.2, y + 41.1, "Check Form", 303.72, y + 23.75)


# --- Form INC-34 ------------------------------------------------------------------------------------------------

AOA_COLS = [17.5, 41.8, 66.1, 97.3, 577.3]


def _article_lines(s: Form, paras, directors: str) -> list[tuple[float, str]]:
    out = []
    for indent, text in paras:
        text = text.replace("{directors}", directors)
        x = 98.76 + indent
        for k, ln in enumerate(s.wrap(text, "arial", 9.72, 575.6 - 98.76, first=575.6 - x)):
            out.append((x if k == 0 else 98.76, ln))
    return out


def _inc34(s: Form, e, subs, R, signed: dt.date):
    first_page = len(s.pages) - 1
    s.rect(18.4, 58.0, 575.8, 114.0)
    s.t(23.19, 62.09, "[Pursuant to Schedule I (see Sections 4 and 5) to", "times", 13.56)
    s.t(23.19, 79.37, "the Companies Act, 2013)] FORM NO. INC-34", "times", 13.56)
    s.t(434.89, 65.52, "SPIC", "timesb", 19.44)
    s.t(479.16, 53.28, "e", "logo", 35.04)
    s.t(496.92, 63.86, "+", "plus", 15.6, fit=13.53)
    s.t(512.65, 65.52, "AOA", "timesb", 19.44)
    s.t(437.88, 92.78, "(e-Articles of Association)", "times", 10.68)
    s.t(21.00, 126.37, "*", "arial", 9.72, colour="#FF0000")
    s.t(24.84, 126.22, "Table")
    s.rect(55.65, 122.25, 78.75, 138.35, 0.5)
    s.t(57.36, 126.37, "F", "arial", 9.72)
    s.t(84.86, 126.22, "as notified under schedule I of the companies Act, 2013 is applicable")
    s.t(384.61, 127.11, "to the company", "verdana", 8.76, fit=68.86)
    s.rect(18.2, 156.4, 575.9, 181.2)
    s.t(297.0, 164.89, e.name.upper(), "arial", 9.72, align="c")
    s.rect(18.2, 183.1, 575.9, 205.2)
    s.t(297.0, 190.21, "A COMPANY LIMITED BY SHARES", "arial", 9.72, align="c")
    s.cells(AOA_COLS, 226.7, 293.9)
    for k, ln in enumerate(("Che", "ck if", "not", "appl", "icab", "le")):
        s.t(18.84, 227.41 + k * 11.09, ln, "arialb", 9.72)
    for k, ln in enumerate(("Che", "ck if", "alter", "ed")):
        s.t(43.20, 227.41 + k * 11.09, ln, "arialb", 9.72)
    s.t(81.7, 249.61, "Articl", "arialb", 9.72, align="c")
    s.t(81.7, 260.65, "e No", "arialb", 9.72, align="c")
    s.t(310.56, 255.13, "Description", "arialb", 9.72)

    names = [f"{sub['name'].upper()} (DIN: {sub['din']})" for sub in subs]
    directors = " & ".join(names) if len(names) < 3 else ", ".join(names[:-1]) + " & " + names[-1]
    y, headings = 293.9, 0
    for item in TABLE_F:
        if item[0] == "h":
            if y + 26.0 > LIMIT:
                s.page()
                y = 53.3
            s.cells(AOA_COLS, y, y + 26.0)
            face, size = ("arialbi", 9.72) if headings < 2 else ("calbi", 10.68)
            s.t(337.3, y + (7.9 if headings < 7 else 7.0), item[1], face, size, align="c")   # as the form sets them
            headings += 1
            y += 26.0
            continue
        _, num, altered, paras = item
        lines = _article_lines(s, paras, directors)
        n = len(lines)
        full = max(27.95, 11.073 * n + 0.78)
        if y + full > LIMIT:
            k = max(0, int((LIMIT - 1.3 - y) / 11.073))
            k = min(k, n - 2)
            if k < 3:                                # too little room for three lines: the whole article moves on
                s.page()
                y = 53.3
                parts = [(y, 0, n, full, 0.87)]
            else:
                parts = [(y, 0, k, 11.073 * k + 1.3, 0.87), (53.3, k, n, 11.073 * (n - k) - 0.6, -0.6)]
        else:
            parts = [(y, 0, n, full, 0.87)]
        nums = num.split()
        mid = full / 2 - 5.3 - (len(nums) - 1) * 11.04 / 2       # the number sits in the middle of the whole row
        spots = [(0, mid + q * 11.04) if len(parts) == 1 or mid + q * 11.04 + 5.3 < parts[0][3]
                 else (1, max(0.5, mid + q * 11.04 - parts[0][3])) for q in range(len(nums))]
        for j, (top, a, b, h, pad) in enumerate(parts):
            if j:
                s.page()
            s.cells(AOA_COLS, top, top + h)
            if j == 0:
                s.checkbox(24.0, top + 9.0)
                s.checkbox(49.4, top + 9.0, ticked=altered)
            for i, (x, ln) in enumerate(lines[a:b]):
                s.t(x, top + pad + i * 11.068, ln, "arial", 9.72)
            for nm, (part, off) in zip(nums, spots):
                if part == j:
                    s.t(83.1 if not nm.isdigit() or int(nm) < 27 else 81.75, top + off, nm, "arial", 9.72, align="c")
            y = top + h

    # the last page: the subscribers and the witness
    s.page()
    s.rect(17.5, 53.3, 575.6, 74.6)
    s.t(270.84, 58.78, "Subscriber Details")
    edges = [17.5, 44.0, 265.9, 357.4, 450.7, 506.9, 575.6]
    s.cells(edges, 74.6, 121.4)
    s.t(27.00, 86.50, "S.")
    s.t(23.76, 99.34, "NO")
    s.t(59.16, 92.86, "Name, Address, Description and Occupation")
    s.t(271.32, 86.50, "DIN/PAN/Passport")
    s.t(293.76, 99.34, "Number")
    s.t(392.64, 92.86, "Place")
    s.t(470.16, 92.86, "DSC")
    s.t(528.12, 92.86, "Dated")
    y = 121.4
    place = _place(e).upper()
    for i, sub in enumerate(subs, 1):
        kin, relname = sub["kin"]
        text = (f"{sub['name'].upper()} {kin};{relname.upper()} DOB:{sub['dob']} ADDRESS; : {sub['addr'].upper()} "
                f"OCCUPATION :{sub['occ']}")
        lines = s.wrap(text, "cal", 10.68, 219.2)
        h = max(27.0, len(lines) * 12.84 + 0.76)
        s.cells(edges, y, y + h)
        s.t(28.08, y + 0.89, str(i), "arial", 9.72)
        s.justified(45.36, y + 1.7, 219.2, lines, "cal", 10.68, 12.84)
        s.t(267.36, y + 0.89, sub["din"], "arial", 9.72)
        s.t(358.80, y + 0.89, place, "arial", 9.72)
        s.t(508.21, y + 0.89, signed.strftime("%d/%m/%Y"), "arial", 9.72)
        y += h
    s.rect(17.5, y, 575.0, y + 20.8)
    s.t(260.28, y + 5.3, "Signed Before Me")
    y += 20.8
    s.cells([17.5, 166.1, 344.9, 412.6, 457.9, 513.5, 575.0], y, y + 67.7)
    s.t(81.25, y + 28.78, "Name")
    s.t(175.08, y + 28.78, "Address, Description and Occupation")
    for k, ln in enumerate(("DIN/PAN/", "Passport", "Number/", "Membership", "Number")):
        s.t(378.75, y + 3.1 + k * 12.84, ln, align="c")
    s.t(423.72, y + 28.78, "Place")
    s.t(477.12, y + 28.78, "DSC")
    s.t(531.12, y + 28.78, "Dated")
    y += 67.7
    ca = R.AUDITOR[3]
    witness = (f"{ca.upper()} S/o:{WITNESS[0].upper()} Address: {WITNESS[1]} Occupation: Chartered Accountant I, "
               "witness to this AOA")
    lines = s.wrap(witness, "cal", 10.68, 176.0)
    h = max(61.7, len(lines) * 12.84 + 3.0)
    s.cells([17.5, 64.3, 166.1, 344.9, 412.6, 457.9, 513.5, 575.0], y, y + h)
    s.t(30.96, y + 18.24, "ACA", "arial", 9.72)
    s.rect(65.8, y + 1.4, 164.8, y + h - 1.5)
    s.t(66.72, y + 5.24, ca.upper())
    s.justified(167.52, y + 1.64, 176.0, lines, "cal", 10.68, 12.84)
    s.t(345.6, y + 1.64, R.AUDITOR[4])
    for k, ln in enumerate(s.wrap(place, "arial", 9.72, 43.5)):
        s.t(413.88, y + 0.84 + k * 11.04, ln, "arial", 9.72)
    s.t(514.80, y + 0.84, signed.strftime("%d/%m/%Y"), "arial", 9.72)
    y += h
    s.button(137.8, y + 14.0, 216.6, y + 37.6, "Checkform", 153.60, y + 20.74)
    s.button(356.8, y + 14.0, 435.6, y + 37.6, "Modify", 381.84, y + 20.74)
    s.page_numbers(first_page, 532.93, 792.90)


def memorandum(e=None, *, directors: tuple[str, ...] | None = None, cin: str | None = None) -> bytes:
    """The e-Memorandum (INC-33) and e-Articles (INC-34) of the company, as one document. `directors` names the
    subscribers, who are also the first directors (a third subscriber adds a row to each subscribers' table and a name
    to article 58). The SPICe+ forms are filed before the company has a Corporate Identity Number, so they print none:
    `cin` is accepted for the generator's common signature and not printed."""
    import realistic_docs as R
    from tests import docsets as D

    e = e or D.BASE
    names = directors or tuple(p.name for p in e.persons)
    subs = _subscribers(e, names, R)
    signed = _signed(e, R)
    s = Form()
    _inc33(s, e, subs, R, signed)
    s.page_numbers(0, 524.05, 793.14)
    s.page()
    _inc34(s, e, subs, R, signed)
    return s.render()


# Table F of Schedule I to the Companies Act, 2013, as the e-Articles form prints it: ("h", heading) or
# ("a", article number, altered, ((indent in points, hard line), ...)). The form's "?" for an apostrophe is kept.
TABLE_F = (
    ("h", 'Interpretation'),
    ("a", 'I', True, (
        (0, '(1) In these regulations-'),
        (35, '(a) "the Act" means the Companies Act, 2013,'),
        (35, '(b) "the seal" means the common seal of the company.'),
        (21.58, '(c) "Private Company" means a company having a minimum paid-up share capital * as may be prescribed, and which by its articles,'),
        (0, '(i) restricts the right to transfer its shares;'),
        (0, '(ii) except in case of One Person Company, limits the number of its members to two hundred:'),
        (0, 'Provided that where two or more persons hold one or more shares in a company jointly, they shall, for'),
        (0, 'the purposes of this clause, be treated as a single member:'),
        (0, 'Provided further that:'),
        (0, '(A) persons who are in the employment of the company; and'),
        (0, '(B) persons who, having been formerly in the employment of the company, were members of the'),
        (0, 'company while in that employment and have continued to be members after the employment ceased,'),
        (0, 'shall not be included in the number of members; and'),
        (0, '(iii) prohibits any invitation to the public to subscribe for any securities of the company.'),
        (0, '(2) Unless the context otherwise requires, words or expressions contained in these regulations shall bear the same meaning as in the Act or any statutory modification thereof in force at the date at which these regulations become binding on the company.'),
    )),
    ("h", 'Share capital and variation of rights'),
    ("a", 'II 1', False, (
        (0, 'Subject to the provisions of the Act and these Articles, the shares in the capital of the company shall be under the control of the Directors who may issue, allot or otherwise dispose of the same or any of them to such persons, in such proportion and on such terms and conditions and either at a premium or at par and at such time as they may from time to time think fit.'),
    )),
    ("a", '2', False, (
        (0, '(i) Every person whose name is entered as a member in the register of members shall be entitled to receive within two months after incorporation, in case of subscribers to the memorandum or after allotment or within one month after the application for the registration of transfer or transmission or within such other period as the conditions of issue shall be provided,-'),
        (35, '(a) one certificate for all his shares without payment of any charges; or'),
        (35, '(b) several certificates, each for one or more of his shares, upon payment of twenty rupees for each certificate after the first.'),
        (0, '(ii) Every certificate shall be under the seal and shall specify the shares to which it relates and the amount paid-up thereon.'),
        (0, '(iii) In respect of any share or shares held jointly by several persons, the company shall not be bound to issue more than one certificate, and delivery of a certificate for a share to one of several joint holders shall be sufficient delivery to all such holders'),
    )),
    ("a", '3', True, (
        (0, 'i) If any share certificate be worn out, defaced, mutilated or torn or if there be no further space on the back for endorsement of transfer, then upon production and surrender thereof to the company, a new certificate may be issued in lieu thereof, and if any certificate is lost or destroyed then upon proof thereof to the satisfaction of the company and on execution of such indemnity as the company deem adequate, a new certificate in lieu thereof shall be given. Every certificate under this Article shall be issued on payment of twenty rupees for each certificate.'),
    )),
    ("a", '4', False, (
        (0, 'Except as required by law, no person shall be recognised by the company as holding any share upon any trust, and the company shall not be bound by, or be compelled in any way to recognise (even when having notice thereof) any equitable, contingent, future or partial interest in any share, or any interest in any fractional part of a share, or (except only as by these regulations or by law otherwise provided) any other rights in respect of any share except an absolute right to the entirety thereof in the registered holder.'),
    )),
    ("a", '5', False, (
        (0, '(i) The company may exercise the powers of paying commissions conferred by sub-section (6) of section 40, provided that the rate per cent or the amount of the commission paid or agreed to be paid shall be disclosed in the manner required by that section and rules made thereunder.'),
        (0, '(ii) The rate or amount of the commission shall not exceed the rate or amount prescribed in rules made under sub-section (6) of section 40.'),
        (0, '(iii) The commission may be satisfied by the payment of cash or the allotment of fully or partly paid shares or partly in the one way and partly in the other.'),
    )),
    ("a", '6', False, (
        (0, '(i) If at any time the share capital is divided into different classes of shares, the rights attached to any class (unless otherwise provided by the terms of issue of the shares of that class) may, subject to the provisions of section 48, and whether or not the company is being wound up, be varied with the consent in writing of the holders of three-fourths of the issued shares of that class, or with the sanction of a special resolution passed at a separate meeting of the holders of the shares of that class.'),
        (0, '(ii) To every such separate meeting, the provisions of these regulations relating to general meetings shall mutatis mutandis apply, but so that the necessary quorum shall be at least two persons holding at least one- third of the issued shares of the class in question.'),
    )),
    ("a", '7', False, (
        (0, 'The rights conferred upon the holders of the shares of any class issued with preferred or other rights shall not, unless otherwise expressly provided by the terms of issue of the shares of that class, be deemed to be varied by the creation or issue of further shares ranking pari passu therewith.'),
    )),
    ("a", '8', False, (
        (0, 'Subject to the provisions of section 55, any preference shares may, with the sanction of an ordinary resolution, be issued on the terms that they are to be redeemed on such terms and in such manner as the company before the issue of the shares may, by special resolution, determine.'),
    )),
    ("h", 'Lien'),
    ("a", '9', False, (
        (0, '(i) The company shall have a first and paramount lien-'),
        (35, '(a) on every share (not being a fully paid share), for all monies (whether presently payable or not) called, or payable at a fixed time, in respect of that share; and'),
        (35, '(b) on all shares (not being fully paid shares) standing registered in the name of a single person, for all monies presently payable by him or his estate to the company:'),
        (0, 'Provided that the Board of directors may at any time declare any share to be wholly or in part exempt from the provisions of this clause.'),
        (0, '(ii) The company?s lien, if any, on a share shall extend to all dividends payable and bonuses declared from time to time in respect of such shares.'),
    )),
    ("a", '10', False, (
        (0, 'The company may sell, in such manner as the Board thinks fit, any shares on which the company has a lien: Provided that no sale shall be made-'),
        (35, '(a) unless a sum in respect of which the lien exists is presently payable; or'),
        (35, '(b) until the expiration of fourteen days after a notice in writing stating and demanding payment of such part of the amount in respect of which the lien exists as is presently payable, has been given to the registered holder for the time being of the share or the person entitled thereto by reason of his death or insolvency.'),
    )),
    ("a", '11', False, (
        (0, '(i) To give effect to any such sale, the Board may authorise some person to transfer the shares sold to the purchaser thereof.'),
        (0, '(ii) The purchaser shall be registered as the holder of the shares comprised in any such transfer.'),
        (0, '(iii) The purchaser shall not be bound to see to the application of the purchase money, nor shall his title to the shares be affected by any irregularity or invalidity in the proceedings in reference to the sale.'),
    )),
    ("a", '12', False, (
        (0, '(i) The proceeds of the sale shall be received by the company and applied in payment of such part of the amount in respect of which the lien exists as is presently payable.'),
        (0, '(ii) The residue, if any, shall, subject to a like lien for sums not presently payable as existed upon the shares before the sale, be paid to the person entitled to the shares at the date of the sale.'),
    )),
    ("h", 'Calls on shares'),
    ("a", '13', False, (
        (0, '(i) The Board may, from time to time, make calls upon the members in respect of any monies unpaid on their shares (whether on account of the nominal value of the shares or by way of premium) and not by the conditions of allotment thereof made payable at fixed times:'),
        (0, 'Provided that no call shall exceed one-fourth of the nominal value of the share or be payable at less than one month from the date fixed for the payment of the last preceding call.'),
        (0, '(ii) Each member shall, subject to receiving at least fourteen days? notice specifying the time or times and place of payment, pay to the company, at the time or times and place so specified, the amount called on his shares.'),
        (0, '(iii) A call may be revoked or postponed at the discretion of the Board.'),
    )),
    ("a", '14', False, (
        (0, 'A call shall be deemed to have been made at the time when the resolution of the Board authorizing the call was passed and may be required to be paid by instalments.'),
    )),
    ("a", '15', False, (
        (0, 'The joint holders of a share shall be jointly and severally liable to pay all calls in respect thereof.'),
    )),
    ("a", '16', False, (
        (0, '(i) If a sum called in respect of a share is not paid before or on the day appointed for payment thereof, the person from whom the sum is due shall pay interest thereon from the day appointed for payment thereof to the time of actual payment at ten per cent per annum or at such lower rate, if any, as the Board may determine.'),
        (0, '(ii) The Board shall be at liberty to waive payment of any such interest wholly or in part.'),
    )),
    ("a", '17', False, (
        (0, '(i) Any sum which by the terms of issue of a share becomes payable on allotment or at any fixed date, whether on account of the nominal value of the share or by way of premium, shall, for the purposes of these regulations, be deemed to be a call duly made and payable on the date on which by the terms of issue such sum becomes payable.'),
        (0, '(ii) In case of non-payment of such sum, all the relevant provisions of these regulations as to payment of interest and expenses, forfeiture or otherwise shall apply as if such sum had become payable by virtue of a call duly made and notified.'),
    )),
    ("a", '18', False, (
        (0, 'The Board-'),
        (0, '(a) may, if it thinks fit, receive from any member willing to advance the same, all or any part of the monies uncalled and unpaid upon any shares held by him; and'),
        (0, '(b) upon all or any of the monies so advanced, may (until the same would, but for such advance, become presently payable) pay interest at such rate not exceeding, unless the company in general meeting shall otherwise direct, twelve per cent per annum, as may be agreed upon between the Board and the member paying the sum in advance.'),
    )),
    ("h", 'Transfer of shares'),
    ("a", '19', False, (
        (0, '(i) The instrument of transfer of any share in the company shall be executed by or on behalf of both the transferor and transferee.'),
        (0, '(ii) The transferor shall be deemed to remain a holder of the share until the name of the transferee is entered in the register of members in respect thereof.'),
    )),
    ("a", '20', False, (
        (0, 'The Board may, subject to the right of appeal conferred by section 58 decline to register-'),
        (0, '(a) the transfer of a share, not being a fully paid share, to a person of whom they do not approve; or'),
        (0, '(b) any transfer of shares on which the company has a lien.'),
    )),
    ("a", '21', False, (
        (0, 'The Board may decline to recognise any instrument of transfer unless-'),
        (0, '(a) the instrument of transfer is in the form as prescribed in rules made under sub-section (1) of section 56;'),
        (0, '(b) the instrument of transfer is accompanied by the certificate of the shares to which it relates, and such other evidence as the Board may reasonably require to show the right of the transferor to make the transfer; and'),
        (0, '(c) the instrument of transfer is in respect of only one class of shares.'),
    )),
    ("a", '22', False, (
        (0, 'On giving not less than seven days? previous notice in accordance with section 91 and rules made thereunder, the registration of transfers may be suspended at such times and for such periods as the Board may from time to time determine:'),
        (0, 'Provided that such registration shall not be suspended for more than thirty days at any one time or for more than forty-five days in the aggregate in any year.'),
    )),
    ("h", 'Transmission of shares'),
    ("a", '23', False, (
        (0, '(i) On the death of a member, the survivor or survivors where the member was a joint holder, and his nominee or nominees or legal representatives where he was a sole holder, shall be the only persons recognised by the company as having any title to his interest in the shares'),
        (0, '(ii) Nothing in clause (i) shall release the estate of a deceased joint holder from any liability in respect of any share which had been jointly held by him with other persons.'),
    )),
    ("a", '24', False, (
        (0, '(i) Any person becoming entitled to a share in consequence of the death or insolvency of a member may, upon such evidence being produced as may from time to time properly be required by the Board and subject as hereinafter provided, elect, either-'),
        (35, '(a) to be registered himself as holder of the share; or'),
        (35, '(b) to make such transfer of the share as the deceased or insolvent member could have made.'),
        (0, '(ii) The Board shall, in either case, have the same right to decline or suspend registration as it would have had, if the deceased or insolvent member had transferred the share before his death or insolvency.'),
    )),
    ("a", '25', False, (
        (0, '(i) If the person so becoming entitled shall elect to be registered as holder of the share himself, he shall deliver or send to the company a notice in writing signed by him stating that he so elects.'),
        (0, '(ii) If the person aforesaid shall elect to transfer the share, he shall testify his election by executing a transfer of the share.'),
        (0, '(iii) All the limitations, restrictions and provisions of these regulations relating to the right to transfer and the registration of transfers of shares shall be applicable to any such notice or transfer as aforesaid as if the death or insolvency of the member had not occurred and the notice or transfer were a transfer signed by that member.'),
    )),
    ("a", '26', False, (
        (0, 'A person becoming entitled to a share by reason of the death or insolvency of the holder shall be entitled to the same dividends and other advantages to which he would be entitled if he were the registered holder of the share, except that he shall not, before being registered as a member in respect of the share, be entitled in respect of it to exercise any right conferred by membership in relation to meetings of the company:'),
        (0, 'Provided that the Board may, at any time, give notice requiring any such person to elect either to be registered himself or to transfer the share, and if the notice is not complied with within ninety days, the Board may thereafter withhold payment of all dividends, bonuses or other monies payable in respect of the share, until the requirements of the notice have been complied with.'),
    )),
    ("h", 'Forfeiture of shares'),
    ("a", '27', False, (
        (0, 'If a member fails to pay any call, or instalment of a call, on the day appointed for payment thereof, the Board may, at any time thereafter during such time as any part of the call or instalment remains unpaid, serve a notice on him requiring payment of so much of the call or instalment as is unpaid, together with any interest which may have accrued.'),
    )),
    ("a", '28', False, (
        (0, 'The notice aforesaid shall-'),
        (0, '(a) name a further day (not being earlier than the expiry of fourteen days from the date of service of the notice) on or before which the payment required by the notice is to be made; and'),
        (0, '(b) state that, in the event of non-payment on or before the day so named, the shares in respect of which the call was made shall be liable to be forfeited.'),
    )),
    ("a", '29', False, (
        (0, 'If the requirements of any such notice as aforesaid are not complied with, any share in respect of which the notice has been given may, at any time thereafter, before the payment required by the notice has been made, be forfeited by a resolution of the Board to that effect.'),
    )),
    ("a", '30', False, (
        (0, '(i) A forfeited share may be sold or otherwise disposed of on such terms and in such manner as the Board thinks fit.'),
        (0, '(ii) At any time before a sale or disposal as aforesaid, the Board may cancel the forfeiture on such terms as it thinks fit.'),
    )),
    ("a", '31', False, (
        (0, '(i) A person whose shares have been forfeited shall cease to be a member in respect of the forfeited shares, but shall, notwithstanding the forfeiture, remain liable to pay to the company all monies which, at the date of forfeiture, were presently payable by him to the company in respect of the shares.'),
        (0, '(ii) The liability of such person shall cease if and when the company shall have received payment in full of all such monies in respect of the shares.'),
    )),
    ("a", '32', False, (
        (0, '(i) A duly verified declaration in writing that the declarant is a director, the manager or the secretary, of the company, and that a share in the company has been duly forfeited on a date stated in the declaration, shall be conclusive evidence of the facts therein stated as against all persons claiming to be entitled to the share;'),
        (0, '(ii) The company may receive the consideration, if any, given for the share on any sale or disposal thereof and may execute a transfer of the share in favour of the person to whom the share is sold or disposed of;'),
        (0, '(iii) The transferee shall thereupon be registered as the holder of the share; and'),
        (0, '(iv) The transferee shall not be bound to see to the application of the purchase money, if any, nor shall his title to the share be affected by any irregularity or invalidity in the proceedings in reference to the forfeiture, sale or disposal of the share.'),
    )),
    ("a", '33', False, (
        (0, 'The provisions of these regulations as to forfeiture shall apply in the case of nonpayment of any sum which, by the terms of issue of a share, becomes payable at a fixed time, whether on account of the nominal value of the share or by way of premium, as if the same had been payable by virtue of a call duly made and notified.'),
    )),
    ("h", 'Alteration of capital'),
    ("a", '34', False, (
        (0, 'The company may, from time to time, by ordinary resolution increase the share capital by such sum, to be divided into shares of such amount, as may be specified in the resolution.'),
    )),
    ("a", '35', False, (
        (0, 'Subject to the provisions of section 61, the company may, by ordinary resolution,-'),
        (0, '(a) consolidate and divide all or any of its share capital into shares of larger amount than its existing shares;'),
        (0, '(b) convert all or any of its fully paid-up shares into stock, and reconvert that stock into fully paid-up shares of any denomination;'),
        (0, '(c) sub-divide its existing shares or any of them into shares of smaller amount than is fixed by the memorandum;'),
        (0, '(d) cancel any shares which, at the date of the passing of the resolution, have not been taken or agreed to be taken by any person.'),
    )),
    ("a", '36', False, (
        (0, 'Where shares are converted into stock,-'),
        (0, '(a) the holders of stock may transfer the same or any part thereof in the same manner as, and subject to the same regulations under which, the shares from which the stock arose might before the conversion have been transferred, or as near thereto as circumstances admit:'),
        (0, 'Provided that the Board may, from time to time, fix the minimum amount of stock transferable, so, however, that such minimum shall not exceed the nominal amount of the shares from which the stock arose.'),
        (0, '(b) the holders of stock shall, according to the amount of stock held by them, have the same rights, privileges and advantages as regards dividends, voting at meetings of the company, and other matters, as if they held the shares from which the stock arose; but no such privilege or advantage (except participation in the dividends and profits of the company and in the assets on winding up) shall be conferred by an amount of stock which would not, if existing in shares, have conferred that privilege or advantage.'),
        (0, '(c) such of the regulations of the company as are applicable to paid-up shares shall apply to stock and the words "share" and "shareholder" in those regulations shall include "stock" and "stock-holder" respectively.'),
    )),
    ("a", '37', False, (
        (0, 'The company may, by special resolution, reduce in any manner and with, and subject to, any incident authorised and consent required by law,-'),
        (0, '(a) its share capital;'),
        (0, '(b) any capital redemption reserve account; or'),
        (0, '(c) any share premium account.'),
    )),
    ("h", 'Capitalisation of profits'),
    ("a", '38', False, (
        (0, '(i) The company in general meeting may, upon the recommendation of the Board, resolve-'),
        (0, '(a) that it is desirable to capitalise any part of the amount for the time being standing to the credit of any of the company?s reserve accounts, or to the credit of the, profit and loss account, or otherwise available for distribution; and'),
        (0, '(b) that such sum be accordingly set free for distribution in the manner specified in clause (ii) amongst the members who would have been entitled thereto, if distributed by way of dividend and in the same proportions. (ii) The sum aforesaid shall not be paid in cash but shall be applied, subject to the provision contained in clause (iii), either in or towards-'),
        (0, '(A) paying up any amounts for the time being unpaid on any shares held by such members respectively;'),
        (0, '(B) paying up in full, unissued shares of the company to be allotted and distributed, credited as fully paid-up, to and amongst such members in the proportions aforesaid;'),
        (0, '(C) partly in the way specified in sub-clause (A) and partly in that specified in sub-clause (B);'),
        (0, '(D) A securities premium account and a capital redemption reserve account may, for the purposes of this regulation, be applied in the paying up of unissued shares to be issued to members of the company as fully paid bonus shares;'),
        (0, '(E) The Board shall give effect to the resolution passed by the company in pursuance of this regulation.'),
    )),
    ("a", '39', False, (
        (0, '(i) Whenever such a resolution as aforesaid shall have been passed, the Board shall-'),
        (0, '(a) make all appropriations and applications of the undivided profits resolved to be capitalised thereby, and all allotments and issues of fully paid shares if any; and'),
        (0, '(b) generally do all acts and things required to give effect thereto.'),
        (0, '(ii) The Board shall have power-'),
        (0, '(a) to make such provisions, by the issue of fractional certificates or by payment in cash or otherwise as it thinks fit, for the case of shares becoming distributable in fractions; and'),
        (0, '(b) to authorise any person to enter, on behalf of all the members entitled thereto, into an agreement with the company providing for the allotment to them respectively, credited as fully paid-up, of any further shares to which they may be entitled upon such capitalisation, or as the case may require, for the payment by the company on their behalf, by the application thereto of their respective proportions of profits resolved to be capitalised, of the amount or any part of the amounts remaining unpaid on their existing shares;'),
        (0, '(iii) Any agreement made under such authority shall be effective and binding on such members.'),
    )),
    ("h", 'Buy-back of shares'),
    ("a", '40', False, (
        (0, 'Notwithstanding anything contained in these articles but subject to the provisions of sections 68 to 70 and any other applicable provision of the Act or any other law for the time being in force, the company may purchase its own shares or other specified securities.'),
    )),
    ("h", 'General meetings'),
    ("a", '41', False, (
        (0, 'All general meetings other than annual general meeting shall be called extraordinary general meeting.'),
    )),
    ("a", '42', False, (
        (0, '(i) The Board may, whenever it thinks fit, call an extraordinary general meeting.'),
        (0, '(ii) If at any time directors capable of acting who are sufficient in number to form a quorum are not within India, any director or any two members of the company may call an extraordinary general meeting in the same manner, as nearly as possible, as that in which such a meeting may be called by the Board.'),
    )),
    ("h", 'Proceedings at general meetings'),
    ("a", '43', False, (
        (0, '(i) No business shall be transacted at any general meeting unless a quorum of members is present at the time when the meeting proceeds to business.'),
        (0, '(ii) Save as otherwise provided herein, the quorum for the general meetings shall be as provided in section 103.'),
    )),
    ("a", '44', False, (
        (0, 'The chairperson, if any, of the Board shall preside as Chairperson at every general meeting of the company.'),
    )),
    ("a", '45', False, (
        (0, 'If there is no such Chairperson, or if he is not present within fifteen minutes after the time appointed for holding the meeting, or is unwilling to act as chairperson of the meeting, the directors present shall elect one of their members to be Chairperson of the meeting.'),
    )),
    ("a", '46', False, (
        (0, 'If at any meeting no director is willing to act as Chairperson or if no director is present within fifteen minutes after the time appointed for holding the meeting, the members present shall choose one of their members to be Chairperson of the meeting.'),
    )),
    ("h", 'Adjournment of meeting'),
    ("a", '47', False, (
        (0, '(i) The Chairperson may, with the consent of any meeting at which a quorum is present, and shall, if so directed by the meeting, adjourn the meeting from time to time and from place to place.'),
        (0, '(ii) No business shall be transacted at any adjourned meeting other than the business left unfinished at the meeting from which the adjournment took place.'),
        (0, '(iii) When a meeting is adjourned for thirty days or more, notice of the adjourned meeting shall be given as in the case of an original meeting.'),
        (0, '(iv) Save as aforesaid, and as provided in section 103 of the Act, it shall not be necessary to give any notice of an adjournment or of the business to be transacted at an adjourned meeting.'),
    )),
    ("h", 'Voting rights'),
    ("a", '48', False, (
        (0, 'Subject to any rights or restrictions for the time being attached to any class or classes of shares,-'),
        (0, '(a) on a show of hands, every member present in person shall have one vote; and'),
        (0, '(b) on a poll, the voting rights of members shall be in proportion to his share in the paid-up equity share capital of the company.'),
    )),
    ("a", '49', False, (
        (0, 'A member may exercise his vote at a meeting by electronic means in accordance with section 108 and shall vote only once.'),
    )),
    ("a", '50', False, (
        (0, '(i) In the case of joint holders, the vote of the senior who tenders a vote, whether in person or by proxy, shall be accepted to the exclusion of the votes of the other joint holders.'),
        (0, '(ii) For this purpose, seniority shall be determined by the order in which the names stand in the register of members.'),
    )),
    ("a", '51', False, (
        (0, 'A member of unsound mind, or in respect of whom an order has been made by any court having jurisdiction in lunacy, may vote, whether on a show of hands or on a poll, by his committee or other legal guardian, and any such committee or guardian may, on a poll, vote by proxy.'),
    )),
    ("a", '52', False, (
        (0, 'Any business other than that upon which a poll has been demanded may be proceeded with, pending the taking of the poll.'),
    )),
    ("a", '53', False, (
        (0, 'No member shall be entitled to vote at any general meeting unless all calls or other sums presently payable by him in respect of shares in the company have been paid'),
    )),
    ("a", '54', False, (
        (0, '(i) No objection shall be raised to the qualification of any voter except at the meeting or adjourned meeting at which the vote objected to is given or tendered, and every vote not disallowed at such meeting shall be valid for all purposes.'),
        (0, '(ii) Any such objection made in due time shall be referred to the Chairperson of the meeting, whose decision shall be final and conclusive.'),
    )),
    ("h", 'Proxy'),
    ("a", '55', False, (
        (0, 'The instrument appointing a proxy and the power-of-attorney or other authority, if any, under which it is signed or a notarised copy of that power or authority, shall be deposited at the registered office of the company not less than 48 hours before the time for holding the meeting or adjourned meeting at which the person named in the instrument proposes to vote, or, in the case of a poll, not less than 24 hours before the time appointed for the taking of the poll; and in default the instrument of proxy shall not be treated as valid.'),
    )),
    ("a", '56', False, (
        (0, 'An instrument appointing a proxy shall be in the form as prescribed in the rules made under section 105.'),
    )),
    ("a", '57', False, (
        (0, 'A vote given in accordance with the terms of an instrument of proxy shall be valid, notwithstanding the previous death or insanity of the principal or the revocation of the proxy or of the authority under which the proxy was executed, or the transfer of the shares in respect of which the proxy is given:Provided that no intimation in writing of such death, insanity, revocation or transfer shall have been received by the company at its office before the commencement of the meeting or adjourned meeting at which the proxy is used.'),
    )),
    ("h", 'Board of Directors'),
    ("a", '58', True, (
        (0, 'The number of the directors and the names of the first directors shall be determined in writing by the subscribers of the memorandum or a majority of them.'),
        (0, 'The person hereinafter named shall be the first director of the Company {directors}'),
    )),
    ("a", '59', False, (
        (0, '(i) The remuneration of the directors shall, in so far as it consists of a monthly payment, be deemed to accrue from day-to-day.'),
        (0, '(ii) In addition to the remuneration payable to them in pursuance of the Act, the directors may be paid all travelling, hotel and other expenses properly incurred by them-'),
        (0, '(a) in attending and returning from meetings of the Board of Directors or any committee thereof or general meetings of the company; or'),
        (0, '(b) in connection with the business of the company.'),
    )),
    ("a", '60', False, (
        (0, 'The Board may pay all expenses incurred in getting up and registering the company.'),
    )),
    ("a", '61', False, (
        (0, 'The company may exercise the powers conferred on it by section 88 with regard to the keeping of a foreign register; and the Board may (subject to the provisions of that section) make and vary such regulations as it may thinks fit respecting the keeping of any such register.'),
    )),
    ("a", '62', False, (
        (0, 'All cheques, promissory notes, drafts, hundis, bills of exchange and other negotiable instruments, and all receipts for monies paid to the company, shall be signed, drawn, accepted, endorsed, or otherwise executed, as the case may be, by such person and in such manner as the Board shall from time to time by resolution determine.'),
    )),
    ("a", '63', False, (
        (0, 'Every director present at any meeting of the Board or of a committee thereof shall sign his name in a book to be kept for that purpose.'),
    )),
    ("a", '64', False, (
        (0, '(i) Subject to the provisions of section 149, the Board shall have power at any time, and from time to time, to appoint a person as an additional director, provided the number of the directors and additional directors together shall not at any time exceed the maximum strength fixed for the Board by the articles.'),
        (0, '(ii) Such person shall hold office only up to the date of the next annual general meeting of the company but shall be eligible for appointment by the company as a director at that meeting subject to the provisions of the Act.'),
    )),
    ("h", 'Proceedings of the Board'),
    ("a", '65', False, (
        (0, '(i) The Board of Directors may meet for the conduct of business, adjourn and otherwise regulate its meetings, as it thinks fit.'),
        (0, '(ii) A director may, and the manager or secretary on the requisition of a director shall, at any time, summon a meeting of the Board.'),
    )),
    ("a", '66', False, (
        (0, '(i) Save as otherwise expressly provided in the Act, questions arising at any meeting of the Board shall be decided by a majority of votes.'),
        (0, '(ii) In case of an equality of votes, the Chairperson of the Board, if any, shall have a second or casting vote.'),
    )),
    ("a", '67', False, (
        (0, 'The continuing directors may act notwithstanding any vacancy in the Board; but, if and so long as their number is reduced below the quorum fixed by the Act for a meeting of the Board, the continuing directors or director may act for the purpose of increasing the number of directors to that fixed for the quorum, or of summoning a general meeting of the company, but for no other purpose.'),
    )),
    ("a", '68', False, (
        (0, '(i) The Board may elect a Chairperson of its meetings and determine the period for which he is to hold office. (ii) If no such Chairperson is elected, or if at any meeting the Chairperson is not present within five minutes after the time appointed for holding the meeting, the directors present may choose one of their number to be Chairperson of the meeting.'),
    )),
    ("a", '69', False, (
        (0, '(i) The Board may, subject to the provisions of the Act, delegate any of its powers to committees consisting of such member or members of its body as it thinks fit.'),
        (0, '(ii) Any committee so formed shall, in the exercise of the powers so delegated, conform to any regulations that may be imposed on it by the Board.'),
    )),
    ("a", '70', False, (
        (0, '(i) A committee may elect a Chairperson of its meetings.'),
        (0, '(ii) If no such Chairperson is elected, or if at any meeting the Chairperson is not present within five minutes after the time appointed for holding the meeting, the members present may choose one of their members to be Chairperson of the meeting.'),
    )),
    ("a", '71', False, (
        (0, '(i) A committee may meet and adjourn as it thinks fit.'),
        (0, '(ii) Questions arising at any meeting of a committee shall be determined by a majority of votes of the members present, and in case of an equality of votes, the Chairperson shall have a second or casting vote.'),
    )),
    ("a", '72', False, (
        (0, 'All acts done in any meeting of the Board or of a committee thereof or by any person acting as a director, shall, notwithstanding that it may be afterwards discovered that there was some defect in the appointment of any one or more of such directors or of any person acting as aforesaid, or that they or any of them were disqualified, be as valid as if every such director or such person had been duly appointed and was qualified to be a director.'),
    )),
    ("a", '73', False, (
        (0, 'Save as otherwise expressly provided in the Act, a resolution in writing, signed by all the members of the Board or of a committee thereof, for the time being entitled to receive notice of a meeting of the Board or committee, shall be valid and effective as if it had been passed at a meeting of the Board or committee, duly convened and held.'),
    )),
    ("h", 'Chief Executive Officer, Manager, Company Secretary or Chief Financial Officer'),
    ("a", '74', False, (
        (0, 'Subject to the provisions of the Act,-'),
        (0, '(i) A chief executive officer, manager, company secretary or chief financial officer may be appointed by the Board for such term, at such remuneration and upon such conditions as it may thinks fit; and any chief executive officer, manager, company secretary or chief financial officer so appointed may be removed by means of a resolution of the Board;'),
        (0, '(ii) A director may be appointed as chief executive officer, manager, company secretary or chief financial officer'),
    )),
    ("a", '75', False, (
        (0, 'A provision of the Act or these regulations requiring or authorising a thing to be done by or to a director and chief executive officer, manager, company secretary or chief financial officer shall not be satisfied by its being done by or to the same person acting both as director and as, or in place of, chief executive officer, manager, company secretary or chief financial officer.'),
    )),
    ("h", 'The Seal'),
    ("a", '76', False, (
        (0, 'i) The Board shall provide for the safe custody of the seal.'),
        (0, '(ii) The seal of the company shall not be affixed to any instrument except by the authority of a resolution of the Board or of a committee of the Board authorised by it in that behalf, and except in the presence of at least two directors and of the secretary or such other person as the Board may appoint for the purpose; and those two directors and the secretary or other person aforesaid shall sign every instrument to which the seal of the company is so affixed in their presence.'),
    )),
    ("h", 'Dividends and Reserve'),
    ("a", '77', False, (
        (0, 'The company in general meeting may declare dividends, but no dividend shall exceed the amount recommended by the Board.'),
    )),
    ("a", '78', False, (
        (0, 'Subject to the provisions of section 123, the Board may from time to time pay to the members such interim dividends as appear to it to be justified by the profits of the company.'),
    )),
    ("a", '79', False, (
        (0, '(i) The Board may, before recommending any dividend, set aside out of the profits of the company such sums as it thinks fit as a reserve or reserves which shall, at the discretion of the Board, be applicable for any purpose to which the profits of the company may be properly applied, including provision for meeting contingencies or for equalizing dividends; and pending such application, may, at the like discretion, either be employed in the business of the company or be invested in such investments (other than shares of the company) as the Board may, from time to time, thinks fit.'),
        (0, '(ii) The Board may also carry forward any profits which it may consider necessary not to divide, without setting them aside as a reserve.'),
    )),
    ("a", '80', False, (
        (0, '(i) Subject to the rights of persons, if any, entitled to shares with special rights as to dividends, all dividends shall be declared and paid according to the amounts paid or credited as paid on the shares in respect whereof the dividend is paid, but if and so long as nothing is paid upon any of the shares in the company, dividends may be declared and paid according to the amounts of the shares.'),
        (0, '(ii) No amount paid or credited as paid on a share in advance of calls shall be treated for the purposes of this regulation as paid on the share.'),
        (0, '(iii) All dividends shall be apportioned and paid proportionately to the amounts paid or credited as paid on the shares during any portion or portions of the period in respect of which the dividend is paid; but if any share is issued on terms providing that it shall rank for dividend as from a particular date such share shall rank for dividend accordingly.'),
    )),
    ("a", '81', False, (
        (0, 'The Board may deduct from any dividend payable to any member all sums of money, if any, presently payable by him to the company on account of calls or otherwise in relation to the shares of the company.'),
    )),
    ("a", '82', False, (
        (0, '(i) Any dividend, interest or other monies payable in cash in respect of shares may be paid by cheque or warrant sent through the post directed to the registered address of the holder or, in the case of joint holders, to the registered address of that one of the joint holders who is first named on the register of members, or to such person and to such address as the holder or joint holders may in writing direct.'),
        (0, '(ii) Every such cheque or warrant shall be made payable to the order of the person to whom it is sent.'),
    )),
    ("a", '83', False, (
        (0, 'Any one of two or more joint holders of a share may give effective receipts for any dividends, bonuses or other monies payable in respect of such share.'),
    )),
    ("a", '84', False, (
        (0, 'Notice of any dividend that may have been declared shall be given to the persons entitled to share therein in the manner mentioned in the Act.'),
    )),
    ("a", '85', False, (
        (0, 'No dividend shall bear interest against the company.'),
    )),
    ("h", 'Accounts'),
    ("a", '86', False, (
        (0, '(i) The Board shall from time to time determine whether and to what extent and at what times and places and under what conditions or regulations, the accounts and books of the company, or any of them, shall be open to the inspection of members not being directors.'),
        (0, '(ii) No member (not being a director) shall have any right of inspecting any account or book or document of the company except as conferred by law or authorised by the Board or by the company in general meeting.'),
    )),
    ("h", 'Winding up'),
    ("a", '87', False, (
        (0, 'Subject to the provisions of Chapter XX of the Act and rules made thereunder-'),
        (0, '(i) If the company shall be wound up, the liquidator may, with the sanction of a special resolution of the company and any other sanction required by the Act, divide amongst the members, in specie or kind, the whole or any part of the assets of the company, whether they shall consist of property of the same kind or not. (ii) For the purpose aforesaid, the liquidator may set such value as he deems fair upon any property to be divided as aforesaid and may determine how such division shall be carried out as between the members or different classes of members.'),
        (0, '(iii) The liquidator may, with the like sanction, vest the whole or any part of such assets in trustees upon such trusts for the benefit of the contributories if he considers necessary, but so that no member shall be compelled to accept any shares or other securities whereon there is any liability.'),
    )),
    ("h", 'Indemnity'),
    ("a", '88', False, (
        (0, 'Every officer of the company shall be indemnified out of the assets of the company against any liability incurred by him in defending any proceedings, whether civil or criminal, in which judgment is given in his favour or in which he is acquitted or in which relief is granted to him by the court or the Tribunal.'),
    )),
)
