"""A sample upload pack for one fictional borrower, Ospreyline Packaging Private Limited, covering the ten
documents a private limited company's cash credit appraisal needs: constitution and KYC, financials, and
banking and operations. Every figure agrees across the documents (the balance sheet balances, the cash flow
ties to the change in cash, the tax return's income follows the accounts, each month's GST paid in cash is
the debit on the bank statement). Every name and number is fictional; each page carries only the
single-line footer.

    .venv/bin/python scripts/make_sample_pack.py OUT_DIR

Writes OUT_DIR/separate (one PDF per document, as the reader takes them today) and OUT_DIR/combined (one
PDF per checklist section, for trying merged files).
"""

from __future__ import annotations

import random
import sys
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

FOOTER = "Synthetic specimen for software testing. All names and numbers are fictional."
W, H = A4
LEFT, RIGHT = 50, W - 50
VALUE_X = 230

# --- The borrower -------------------------------------------------------------------------------

NAME = "Ospreyline Packaging Private Limited"
CIN = "U17021MH2018PTC309874"
PAN = "AADCO4821K"
TAN = "MUMO24817E"
INCORPORATED = date(2018, 3, 12)
OFFICE = "Plot B-14, MIDC Addl. Ambernath, Thane 421506, Maharashtra"
ACTIVITY = "corrugated boxes, printed cartons and protective packaging"


def _gstin(state: str, pan: str, entity: str = "1") -> str:
    """A GSTIN with its check character worked out as the GST network does."""
    alpha = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    body = f"{state}{pan}{entity}Z"
    total = 0
    for i, ch in enumerate(body):
        v = alpha.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return body + alpha[(36 - total % 36) % 36]


GSTIN = _gstin("27", PAN)

DIRECTORS = [
    {
        "name": "Nandini Gokhale", "title": "Smt.", "designation": "Managing Director", "din": "08754321",
        "relative": "Vasant Kelkar (father)", "dob": "14 August 1979", "gender": "Female",
        "pan": "BXXXX4417M", "aadhaar": "XXXX XXXX 5521", "passport": "Z4821736", "expiry": "23 July 2031",
        "address": "1102 Lakeview Residency, Vartak Nagar, Thane 400606, Maharashtra",
        "shares": 720_000,
    },
    {
        "name": "Aditya Gokhale", "title": "Sri.", "designation": "Director", "din": "08754339",
        "relative": "Madhav Gokhale (father)", "dob": "02 February 1976", "gender": "Male",
        "pan": "CXXXX2186L", "aadhaar": "XXXX XXXX 3094", "passport": "Y2179054", "expiry": "11 January 2030",
        "address": "1102 Lakeview Residency, Vartak Nagar, Thane 400606, Maharashtra",
        "shares": 480_000,
    },
]
SHARES = sum(d["shares"] for d in DIRECTORS)  # equity shares of Rs. 10 each
SHARE_CAPITAL = SHARES * 10
AUTHORISED = 2_00_00_000

LENDER = "RBL Bank Limited"
LIMIT = 5_00_00_000
BANK = "Meridian Commercial Bank"
BRANCH, IFSC, ACCOUNT = "Ambernath MIDC", "MCBL0002214", "50200018437612"
AUDITOR, FRN, PARTNER, MEMBERSHIP = "Dharap Kinikar & Associates", "127745W", "Prakash Dharap", "118204"

CUSTOMERS = ["KORVANI FOODS PVT LTD", "ELMIRA BEVERAGES PVT LTD", "SARVATI HOME CARE LLP",
             "PRAVELLO PHARMA PVT LTD", "DEVKANTA SNACKS PVT LTD"]
SUPPLIERS = ["NIRVEDA PAPER MILLS", "OKHRAN POLYFILMS", "SURYAKSH INKS", "TALWANE ADHESIVES"]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


def inr(n: int) -> str:
    """Indian digit grouping; a negative amount in brackets."""
    s = str(abs(int(n)))
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    out = ",".join(groups + [tail]) if groups else tail
    return f"({out})" if n < 0 else out


def long_date(d: date) -> str:
    return f"{d.day:02d} {FULL_MONTHS[d.month - 1]} {d.year}"


def short_date(d: date) -> str:
    return f"{d.day:02d} {MONTHS[d.month - 1]} {d.year}"


def month_add(y: int, m: int, k: int) -> tuple[int, int]:
    i = y * 12 + (m - 1) + k
    return i // 12, i % 12 + 1


def fy_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


# --- The accounts -------------------------------------------------------------------------------
# Years are keyed by the year the financial year ends (2026 = FY 2025-26).

REVENUE = {2024: 14_72_40_000, 2025: 16_38_75_000, 2026: 18_64_20_000}
OTHER_INCOME = {2024: 6_10_000, 2025: 7_25_000, 2026: 8_40_000}
BOOK_DEP = {2024: 58_40_000, 2025: 63_10_000, 2026: 69_80_000}
CAPEX = {2024: 72_00_000, 2025: 95_00_000, 2026: 1_10_00_000}
DIRECTOR_LOANS = {2023: 1_10_00_000, 2024: 1_00_00_000, 2025: 90_00_000, 2026: 75_00_000}
DISALLOWED = {2024: 24_000, 2025: 31_500, 2026: 38_500}  # interest on late statutory payments (s. 37)
TAX_RATE = (22, 10, 4)  # section 115BAA rate, surcharge, cess (per cent)


def r1000(x: float) -> int:
    return int(round(x / 1000.0)) * 1000


def tax_on(total_income: int) -> tuple[int, int, int, int]:
    base = round(total_income * TAX_RATE[0] / 100)
    surcharge = round(base * TAX_RATE[1] / 100)
    cess = round((base + surcharge) * TAX_RATE[2] / 100)
    return base, surcharge, cess, base + surcharge + cess


def build_accounts() -> dict[int, dict]:
    acc: dict[int, dict] = {}
    reserves, dtl, ppe = 4_40_00_000, 18_00_000, 4_40_00_000
    prev_fg = r1000(REVENUE[2024] * 0.031)
    for y in (2024, 2025, 2026):
        rev, oi = REVENUE[y], OTHER_INCOME[y]
        fg = r1000(rev * 0.031)
        a = {"rev": rev, "oi": oi, "dep": BOOK_DEP[y]}
        a["materials"] = r1000(rev * 0.655)
        a["inv_change"] = prev_fg - fg  # opening less closing finished goods and work in progress
        a["employee"] = r1000(rev * 0.086)
        avg_loan = (DIRECTOR_LOANS[y - 1] + DIRECTOR_LOANS[y]) / 2
        a["finance"] = r1000(avg_loan * 0.09 + 1_10_000)
        a["other"] = r1000(rev * 0.103)
        a["total_income"] = rev + oi
        a["expenses"] = a["materials"] + a["inv_change"] + a["employee"] + a["finance"] + a["dep"] + a["other"]
        a["pbt"] = a["total_income"] - a["expenses"]
        # The return: depreciation as the Act allows, a small disallowance, interest income on its own head.
        a["tax_dep"] = r1000(BOOK_DEP[y] * 1.12)
        a["disallowed"] = DISALLOWED[y]
        a["business"] = a["pbt"] + a["dep"] + a["disallowed"] - a["tax_dep"] - oi
        a["gti"] = a["business"] + oi
        a["ti"] = int(round(a["gti"] / 10.0)) * 10
        a["tax_base"], a["surcharge"], a["cess"], a["current_tax"] = tax_on(a["ti"])
        a["deferred_tax"] = round((a["tax_dep"] - a["dep"]) * 0.25168)
        a["pat"] = a["pbt"] - a["current_tax"] - a["deferred_tax"]
        a["eps"] = a["pat"] / SHARES
        a["ebitda"] = a["pbt"] + a["finance"] + a["dep"] - oi
        # The balance sheet at the year end.
        reserves += a["pat"]
        dtl += a["deferred_tax"]
        ppe += CAPEX[y] - BOOK_DEP[y]
        bs = {
            "share_capital": SHARE_CAPITAL, "reserves": reserves, "lt_borrowings": DIRECTOR_LOANS[y], "dtl": dtl,
            "trade_payables": r1000(a["materials"] * 0.125), "other_cl": r1000(rev * 0.021),
            "st_provisions": r1000(rev * 0.004),
            "ppe": ppe, "lt_advances": 14_50_000, "inventories": r1000(rev * 0.079) + fg,
            "receivables": r1000(rev * 0.171), "st_advances": r1000(rev * 0.012), "other_ca": 3_20_000,
        }
        liabilities = sum(bs[k] for k in ("share_capital", "reserves", "lt_borrowings", "dtl", "trade_payables",
                                          "other_cl", "st_provisions"))
        others = sum(bs[k] for k in ("ppe", "lt_advances", "inventories", "receivables", "st_advances", "other_ca"))
        bs["cash"] = liabilities - others
        bs["total"] = liabilities
        assert bs["cash"] > 0, (y, bs["cash"])
        a["bs"] = bs
        acc[y] = a
        prev_fg = fg
    for y in (2025, 2026):
        a, b0, b1 = acc[y], acc[y - 1]["bs"], acc[y]["bs"]
        wc = {
            "inventories": -(b1["inventories"] - b0["inventories"]),
            "receivables": -(b1["receivables"] - b0["receivables"]),
            "advances": -((b1["st_advances"] + b1["other_ca"] + b1["lt_advances"])
                          - (b0["st_advances"] + b0["other_ca"] + b0["lt_advances"])),
            "payables": b1["trade_payables"] - b0["trade_payables"],
            "other_cl": (b1["other_cl"] + b1["st_provisions"]) - (b0["other_cl"] + b0["st_provisions"]),
        }
        op_before_wc = a["pbt"] + a["dep"] + a["finance"] - a["oi"]
        generated = op_before_wc + sum(wc.values())
        cfo = generated - a["current_tax"]
        cfi = -CAPEX[y] + a["oi"]
        cff = (DIRECTOR_LOANS[y] - DIRECTOR_LOANS[y - 1]) - a["finance"]
        assert cfo + cfi + cff == b1["cash"] - b0["cash"], y
        a["cf"] = {"wc": wc, "op": op_before_wc, "generated": generated, "cfo": cfo, "cfi": cfi, "cff": cff,
                   "open": b0["cash"], "close": b1["cash"]}
    return acc


ACC = build_accounts()
CASH_IN_HAND = 2_15_000

# --- Monthly sales, GST and the bank account ----------------------------------------------------

def build_months() -> list[dict]:
    """Sep 2025 to Oct 2026: taxable sales, the GSTR-3B for each month, and what it paid in cash."""
    rng = random.Random(20261111)
    out = []
    for k in range(14):
        y, m = month_add(2025, 9, k)
        base = REVENUE[2026] / 12 if (y, m) <= (2026, 3) else REVENUE[2026] * 1.09 / 12
        season = {10: 1.07, 11: 1.05, 3: 1.06, 6: 0.94, 7: 0.95}.get(m, 1.0)
        sales = r1000(base * season * rng.uniform(0.96, 1.04))
        inter = r1000(sales * 0.3)
        intra = sales - inter
        out_tax = {"igst": round(inter * 0.18), "cgst": round(intra * 0.09), "sgst": round(intra * 0.09)}
        purchases = r1000(sales * 0.6 * rng.uniform(0.97, 1.03))
        p_inter = r1000(purchases * 0.4)
        p_intra = purchases - p_inter
        itc = {"igst": round(p_inter * 0.18), "cgst": round(p_intra * 0.09), "sgst": round(p_intra * 0.09)}
        # Credit is set off as the law orders it: integrated first against integrated, the rest
        # equally against central and state; central and state against their own heads.
        use_i = min(itc["igst"], out_tax["igst"])
        spare = itc["igst"] - use_i
        use_c = min(out_tax["cgst"], itc["cgst"] + spare // 2)
        use_s = min(out_tax["sgst"], itc["sgst"] + spare - spare // 2)
        paid_itc = {"igst": use_i, "cgst": use_c, "sgst": use_s}
        cash = {h: out_tax[h] - paid_itc[h] for h in out_tax}
        filed = date(*month_add(y, m, 1), 20) - timedelta(days=rng.choice([0, 1, 2, 3]))
        if (y, m) == (2026, 10):
            filed = date(2026, 11, 7)
        out.append({"y": y, "m": m, "sales": sales, "inter": inter, "intra": intra, "out": out_tax,
                    "purchases": purchases, "itc": itc, "paid_itc": paid_itc, "cash": cash, "filed": filed,
                    "arn": f"AA27{m:02d}{str(y)[2:]}{rng.randint(1_000_000, 9_999_999)}"})
    return out


MONTHS_DATA = build_months()
GST_MONTHS = MONTHS_DATA[1:]  # Oct 2025 to Oct 2026


def build_statement() -> tuple[int, list[tuple[date, str, str, int, int]]]:
    """(opening balance on 01 Oct 2025, rows) for the current account, Oct 2025 to Oct 2026. Each month:
    receipts for last month's invoices, supplier payments, salaries and dues, last month's GST paid in
    cash, and the surplus swept to a fixed deposit. The opening balance is set so the 31 March 2026
    balance is the current-account balance in the audited balance sheet."""
    rng = random.Random(4821)
    rows: list[tuple[date, str, str, int, int]] = []
    ref = 40_118_000
    by_month = {(d["y"], d["m"]): d for d in MONTHS_DATA}
    salaries = ACC[2026]["employee"] / 12
    for k in range(13):
        y, m = month_add(2025, 10, k)
        prev = by_month[month_add(y, m, -1)]
        month: list[tuple[date, str, str, int, int]] = []

        def add(day: int, text: str, kind: str, debit: int = 0, credit: int = 0) -> None:
            nonlocal ref
            ref += rng.randint(37, 911)
            month.append((date(y, m, day), text, f"{kind}/{ref}", debit, credit))

        receipts = prev["sales"] * 1.18 * rng.uniform(0.98, 1.02)
        shares = [0.31, 0.24, 0.19, 0.15, 0.11]
        for day, cust, share in zip((3, 8, 13, 19, 24), CUSTOMERS, shares):
            add(day, f"NEFT CR {cust}", "NEFT", credit=r1000(receipts * share))
        supplies = prev["purchases"] * 1.18 * rng.uniform(0.97, 1.01)
        for day, sup, share in zip((5, 11, 16, 22), SUPPLIERS, (0.46, 0.27, 0.15, 0.12)):
            add(day, f"RTGS DR {sup}", "UTR", debit=r1000(supplies * share))
        add(1, f"SALARY TRANSFER {MONTHS[m - 2].upper() if m > 1 else 'DEC'}", "BULK", debit=r1000(salaries * 0.86))
        add(7, "TDS PAYMENT CHALLAN 281", "TAX", debit=r1000(salaries * 0.06 + 85_000))
        add(15, "PF AND ESI CONTRIBUTION", "BULK", debit=r1000(salaries * 0.13))
        add(prev["filed"].day if prev["filed"].month == m else 20, f"GST PAYMENT {MONTHS[prev['m'] - 1].upper()} {prev['y']}",
            "CPIN", debit=sum(prev["cash"].values()))
        add(10, "ELECTRICITY BILL CONS 0218847", "BILL", debit=r1000(prev["sales"] * 0.017))
        add(4, "RENT WAREHOUSE GALA 4", "NEFT", debit=1_85_000)
        add(28, "BANK CHARGES", "CHG", debit=rng.choice([1_180, 1_475, 2_360]))
        if m in (1, 4, 7, 10):
            for d in DIRECTORS:
                add(27, f"INT ON UNSEC LOAN {d['name'][0]} {d['name'].split()[-1].upper()}", "NEFT",
                    debit=r1000(DIRECTOR_LOANS[2026] * 0.09 / 4 * d["shares"] / SHARES))
        if (y, m) in ((2025, 12), (2026, 3), (2026, 6), (2026, 9)):
            add(18, "RTGS DR VERAKSHA MACHINE TOOLS", "UTR", debit=r1000(CAPEX[2026] / 4))
        if (y, m) in ((2025, 11), (2026, 2)):
            add(26, "REPAY UNSEC LOAN A GOKHALE", "NEFT", debit=7_50_000)
        net = sum(c - d for _, _, _, d, c in month)
        if net > 2_00_000:
            add(29 if m != 2 else 27, "TRANSFER TO FIXED DEPOSIT", "TRF", debit=r1000(net - 2_00_000))
        rows += sorted(month, key=lambda r: r[0])
    upto_march = sum(c - d for when, _, _, d, c in rows if when <= date(2026, 3, 31))
    target = ACC[2026]["bs"]["cash"] - CASH_IN_HAND - fixed_deposits()
    return target - upto_march, rows


def fixed_deposits() -> int:
    """The part of the 31 March 2026 cash and bank balances held in fixed deposits: enough to leave a
    current-account balance near fifty lakh."""
    return r1000(ACC[2026]["bs"]["cash"] - CASH_IN_HAND - 48_00_000)


OPENING, STATEMENT = build_statement()

# --- Drawing ------------------------------------------------------------------------------------


class Writer:
    """Draws text pages top-down; every page gets the single-line footer."""

    def __init__(self, path: Path):
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.c.setTitle(path.stem)
        self.y = H - 56
        self.dirty = False

    def _font(self, size: float, bold: bool) -> None:
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)

    def at(self, text: str, x: float, size: float = 9.5, bold: bool = False, align: str = "left") -> None:
        self._font(size, bold)
        if align == "right":
            self.c.drawRightString(x, self.y, text)
        elif align == "center":
            self.c.drawCentredString(x, self.y, text)
        else:
            self.c.drawString(x, self.y, text)
        self.dirty = True

    def line(self, text: str = "", size: float = 9.5, bold: bool = False, x: float = LEFT, gap: float | None = None,
             align: str = "left") -> None:
        self.room(size * 1.5)
        if text:
            self.at(text, W / 2 if align == "center" else x, size, bold, align)
        self.y -= gap if gap is not None else size * 1.45

    def cells(self, items: list[tuple[str, float, str]], size: float = 9, bold: bool = False, gap: float | None = None) -> None:
        self.room(size * 1.5)
        for text, x, align in items:
            self.at(text, x, size, bold, align)
        self.y -= gap if gap is not None else size * 1.5

    def kv(self, label: str, value: str, size: float = 9.5, vx: float = VALUE_X) -> None:
        lines = self.wrap(value, RIGHT - vx, size)
        self.cells([(label, LEFT, "left"), (lines[0], vx, "left")], size)
        for more in lines[1:]:
            self.cells([(more, vx, "left")], size)

    def wrap(self, text: str, width: float, size: float, bold: bool = False) -> list[str]:
        font = "Helvetica-Bold" if bold else "Helvetica"
        words, out, cur = text.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if stringWidth(trial, font, size) <= width or not cur:
                cur = trial
            else:
                out.append(cur)
                cur = w
        return out + [cur] if cur else out or [""]

    def para(self, text: str, size: float = 9.5, bold: bool = False, x: float = LEFT, after: float = 4) -> None:
        for ln in self.wrap(text, RIGHT - x, size, bold):
            self.line(ln, size, bold, x=x)
        self.y -= after

    def room(self, need: float) -> None:
        if self.y - need < 64:
            self.page()

    def page(self) -> None:
        self._footer()
        self.c.showPage()
        self.y = H - 56
        self.dirty = False

    def new_document(self) -> None:
        if self.dirty:
            self.page()

    def _footer(self) -> None:
        self.c.setFont("Helvetica", 7)
        self.c.drawCentredString(W / 2, 30, FOOTER)

    def close(self) -> None:
        if self.dirty:
            self._footer()
        self.c.save()


def letterhead(w: Writer) -> None:
    w.line(NAME.upper(), 12, True, align="center", gap=14)
    w.line(f"CIN: {CIN}  |  PAN: {PAN}  |  GSTIN: {GSTIN}", 8, align="center", gap=11)
    w.line(f"Registered Office: {OFFICE}", 8, align="center", gap=20)


# --- Constitution and KYC -----------------------------------------------------------------------

def ordinal_words(d: date) -> str:
    days = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
            "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth",
            "Eighteenth", "Nineteenth", "Twentieth"]
    return f"{days[d.day - 1]} day of {FULL_MONTHS[d.month - 1]} Two thousand eighteen"


def certificate_of_incorporation(w: Writer) -> None:
    w.line("GOVERNMENT OF INDIA", 10, True, align="center", gap=13)
    w.line("MINISTRY OF CORPORATE AFFAIRS", 10, True, align="center", gap=13)
    w.line("Central Registration Centre", 9.5, align="center", gap=20)
    w.line("CERTIFICATE OF INCORPORATION", 15, True, align="center", gap=18)
    w.para("[Pursuant to sub-section (2) of section 7 and sub-section (1) of section 8 of the Companies Act, 2013 "
           "(18 of 2013) and rule 18 of the Companies (Incorporation) Rules, 2014]", 8.5, after=12)
    w.para(f"I hereby certify that {NAME.upper()} is incorporated on this {ordinal_words(INCORPORATED)} under "
           "the Companies Act, 2013 (18 of 2013) and that the company is limited by shares.", after=8)
    w.para(f"The Corporate Identity Number of the company is {CIN}.", after=4)
    w.para(f"The Permanent Account Number (PAN) of the company is {PAN}.", after=4)
    w.para(f"The Tax Deduction and Collection Account Number (TAN) of the company is {TAN}.", after=8)
    w.para(f"Given under my hand at Manesar this {ordinal_words(INCORPORATED)}.", after=18)
    w.line("Particulars of the company", 10, True, gap=16)
    w.kv("Name of Company", NAME)
    w.kv("Corporate Identity Number", CIN)
    w.kv("Date of Incorporation", long_date(INCORPORATED))
    w.kv("Company Category", "Company limited by shares")
    w.kv("Company Sub-category", "Non-government company")
    w.kv("Class of Company", "Private")
    w.kv("Registered Office", OFFICE)
    w.y -= 26
    w.line("Office of the Registrar of Companies, Central Registration Centre", 9.5, True, gap=14)
    w.line("Mailing address as per record available in the Registrar of Companies office:", 8.5, gap=12)
    w.line(f"{NAME.upper()}, {OFFICE}", 8.5)


def memorandum_and_articles(w: Writer) -> None:
    w.line("THE COMPANIES ACT, 2013", 10, True, align="center", gap=13)
    w.line("(COMPANY LIMITED BY SHARES)", 9.5, align="center", gap=16)
    w.line("MEMORANDUM OF ASSOCIATION", 14, True, align="center", gap=16)
    w.line(f"OF {NAME.upper()}", 10.5, True, align="center", gap=22)
    w.line(f"I. The name of the company is {NAME.upper()}.")
    w.y -= 4
    w.line("II. The registered office of the company will be situated in the State of Maharashtra.")
    w.y -= 4
    w.line("III. (A) THE MAIN OBJECTS TO BE PURSUED BY THE COMPANY ON ITS INCORPORATION ARE:", bold=True)
    w.line("To manufacture, print, buy, sell and deal in corrugated boxes, cartons and protective packaging.", x=LEFT + 18)
    w.line("(B) MATTERS WHICH ARE NECESSARY FOR FURTHERANCE OF THE OBJECTS SPECIFIED IN CLAUSE III(A) ARE:",
           bold=True, size=9)
    w.para("To acquire land, buildings, plant and machinery; to enter into contracts with suppliers and customers; "
           "and to borrow or raise money for the purposes of the company, subject to the provisions of the Act.",
           x=LEFT + 18)
    w.para("IV. The liability of the member(s) is limited and this liability is limited to the amount unpaid, if "
           "any, on the shares held by them.")
    w.line(f"V. The authorised share capital of the company is Rs. {inr(AUTHORISED)} divided into "
           f"{inr(AUTHORISED // 10)} equity shares of Rs. 10 each.", size=9.2)
    w.line(f"The paid-up capital is Rs. {inr(SHARE_CAPITAL)} divided into {inr(SHARES)} equity shares of Rs. 10 each.",
           size=9.2)
    w.y -= 4
    w.line(f"Corporate Identity Number {CIN}")
    w.page()
    w.line("SUBSCRIPTION CLAUSE", 11, True, gap=16)
    w.para("We, the several persons, whose names and addresses are subscribed, are desirous of being formed into a "
           "company in pursuance of this memorandum of association, and we agree to take the number of shares in "
           "the capital of the company set against our respective names.", after=10)
    w.cells([("Name, address, description and occupation of subscriber", LEFT, "left"), ("No.", 430, "right"),
             ("Signature", 470, "left")], bold=True)
    w.cells([("Name,", LEFT, "left"), ("No.", 430, "right"), ("Signature", 470, "left")], bold=True)
    for d in DIRECTORS:
        w.cells([(d["name"], LEFT, "left"), (inr(d["shares"]), 430, "right"), ("signed", 470, "left")])
    w.cells([("Total", LEFT, "left"), (inr(SHARES), 430, "right")], bold=True)
    w.line(f"Dated this 10th day of March 2018. Place: Thane", gap=24)
    w.line("ARTICLES OF ASSOCIATION", 13, True, align="center", gap=16)
    w.line(f"OF {NAME.upper()}", 10, True, align="center", gap=18)
    articles = [
        "1. Interpretation. In these regulations, \"the Act\" means the Companies Act, 2013, and \"the company\" "
        f"means {NAME.upper()}.",
        "2. Private company. The company is a private company within the meaning of section 2(68) of the Act: "
        "the right to transfer its shares is restricted, the number of its members is limited to two hundred, "
        "and no invitation shall be made to the public to subscribe for any securities of the company.",
        "3. Share capital. The authorised share capital of the company shall be as stated in clause V of the "
        "memorandum of association, with power to increase or reduce it in accordance with the Act.",
        "4. Borrowing powers. The Board may, from time to time, raise or borrow any sum of money for the purposes "
        "of the company, and may secure its repayment by mortgage, hypothecation or charge on the whole or any "
        "part of the property of the company, subject to section 180 of the Act.",
        "5. Directors. The number of directors shall not be less than two and not more than fifteen.",
    ]
    for a in articles:
        w.para(a, 9)
    w.line(f"The first directors of the company are {DIRECTORS[0]['title']} {DIRECTORS[0]['name']} and "
           f"{DIRECTORS[1]['title']} {DIRECTORS[1]['name']}.", size=9)
    w.y -= 4
    w.para("6. Meetings of the Board. The Board shall meet at least four times a year, with not more than one "
           "hundred and twenty days between two meetings. Two directors shall form the quorum.", 9)


def board_resolution(w: Writer) -> None:
    letterhead(w)
    w.line("CERTIFIED TRUE COPY OF THE RESOLUTION PASSED BY THE BOARD OF DIRECTORS", 10.5, True, align="center", gap=20)
    meeting = date(2026, 10, 22)
    w.para(f"Certified true copy of the resolution passed at the meeting of the Board of Directors of {NAME} "
           f"(CIN {CIN}) held at the registered office of the company on {meeting.strftime('%A')}, "
           f"{long_date(meeting)} at 11:00 a.m.", after=10)
    w.para(f"RESOLVED THAT pursuant to section 179(3)(d) and other applicable provisions of the Companies Act, "
           f"2013, the consent of the Board of Directors be and is hereby accorded to borrow from {LENDER}, "
           f"credit facilities by way of a Cash Credit limit for working capital, aggregating to Rs. {inr(LIMIT)} "
           "(Rupees Five Crore only), on such terms and conditions as may be stipulated by the said bank.", after=8)
    d1, d2 = DIRECTORS
    w.para(f"RESOLVED FURTHER THAT {d1['title']} {d1['name']}, {d1['designation']} (DIN {d1['din']}) and "
           f"{d2['title']} {d2['name']}, {d2['designation']} (DIN {d2['din']}) be and are hereby severally "
           "authorised to execute the loan agreement, hypothecation deed and other documents, and to do all acts "
           "necessary to give effect to this resolution.", after=8)
    w.para("RESOLVED FURTHER THAT the borrowing be secured by hypothecation of the company's stocks and book "
           "debts, present and future, in favour of the said bank.", after=18)
    w.line("Certified to be true", 9.5, True, gap=14)
    w.line(f"For and on behalf of the Board of Directors of {NAME}", 9.5, gap=26)
    w.cells([(f"Name: {d1['name']}", LEFT, "left"), (f"Name: {d2['name']}", 320, "left")])
    w.cells([(f"Designation: {d1['designation']}", LEFT, "left"), (f"Designation: {d2['designation']}", 320, "left")])
    w.cells([(f"DIN: {d1['din']}", LEFT, "left"), (f"DIN: {d2['din']}", 320, "left")])
    w.cells([("Signature: signed", LEFT, "left"), ("Signature: signed", 320, "left")])
    w.cells([(f"Date: {long_date(meeting)}", LEFT, "left"), (f"Date: {long_date(meeting)}", 320, "left")])
    w.cells([("Place: Thane", LEFT, "left"), ("Place: Thane", 320, "left")])


def company_pan(w: Writer) -> None:
    w.line("INCOME TAX DEPARTMENT", 10, True, align="center", gap=18)
    w.line("INTIMATION OF ALLOTMENT OF PERMANENT ACCOUNT NUMBER (PAN)", 12, True, align="center", gap=24)
    w.line(f"Date: {long_date(date(2018, 3, 15))}", gap=18)
    w.line("To,")
    w.line(NAME)
    w.para(OFFICE, after=12)
    w.line("Subject: Allotment of Permanent Account Number (PAN)", bold=True, gap=16)
    w.para("Dear Taxpayer, with reference to the application for incorporation of the company, a Permanent Account "
           "Number (PAN) has been allotted as below. Please quote this PAN in all correspondence with the Income Tax "
           "Department and in all transactions where it is required.", after=12)
    w.kv("Permanent Account Number", PAN)
    w.kv("Name", NAME)
    w.kv("Status", "Company")
    w.kv("Date of Incorporation", long_date(INCORPORATED))
    w.kv("Jurisdiction", "Assessing Officer, Ward 3(1), Thane")
    w.y -= 16
    w.para("This is a computer-generated intimation letter. No signature is required.", 9)


def director_kyc(w: Writer) -> None:
    for i, d in enumerate(DIRECTORS):
        if i:
            w.page()
        letterhead(w)
        w.line("DIRECTOR KYC SUMMARY SHEET", 13, True, align="center", gap=22)
        w.kv("Name of Director", d["name"])
        w.kv("Designation", d["designation"])
        w.kv("Director Identification Number", d["din"])
        w.kv("Father's Name", d["relative"].split(" (")[0])
        w.kv("Date of Birth", d["dob"])
        w.kv("Gender", d["gender"])
        w.kv("Nationality", "Indian")
        w.kv("Residential Address", d["address"])
        w.kv("PAN (masked)", d["pan"])
        w.kv("Aadhaar (masked)", d["aadhaar"])
        w.kv("Address proof", "Passport")
        w.kv("Passport Number", d["passport"])
        w.kv("Date of Expiry", d["expiry"])
        w.kv("Relationship with company", "Promoter and Director")
        w.kv("Shareholding", f"{inr(d['shares'])} equity shares ({round(100 * d['shares'] / SHARES)}%)")
        w.y -= 10
        w.para("I confirm that the particulars above are true and that the copies of the documents furnished are "
               "self-attested copies of the originals.", 9)
        w.cells([("Signature of Director: signed", LEFT, "left"), ("Date: 20 October 2026", 380, "left")])
        w.y -= 8
        w.para("Personal identifiers are shown in masked form.", 8.5)


# --- Financials ---------------------------------------------------------------------------------

AMOUNTS = "(Amounts in INR)"
COL1, COL2 = 470, 548


def _fs_rows(w: Writer, rows: list[tuple[str, int | float | None, int | float | None, bool]]) -> None:
    for label, cur, prev, bold in rows:
        if cur is None:
            w.cells([(label, LEFT, "left")], 8.8, bold, gap=12.5)
            continue
        fmt = (lambda v: f"{v:.2f}") if isinstance(cur, float) else inr
        w.cells([(label, LEFT, "left"), (fmt(cur), COL1, "right")] + ([(fmt(prev), COL2, "right")] if prev is not None else []),
                8.8, bold, gap=12.5)


def afs(end_year: int) -> Callable[[Writer], None]:
    def draw(w: Writer) -> None:
        a, p = ACC[end_year], ACC[end_year - 1]
        b, pb = a["bs"], p["bs"]
        ye = f"31 MARCH {end_year}"
        signed = date(end_year, 9, 5 if end_year == 2026 else 2)
        # Cover.
        w.line(NAME.upper(), 14, True, align="center", gap=20)
        w.line("AUDITED FINANCIAL STATEMENTS", 13, True, align="center", gap=16)
        w.line(f"FOR THE YEAR ENDED {ye}", 11, True, align="center", gap=30)
        w.kv("Company", NAME)
        w.kv("Corporate Identity Number", CIN)
        w.kv("Registered Office", OFFICE)
        w.kv("Statutory Auditors", f"{AUDITOR}, Chartered Accountants (FRN {FRN})")
        w.kv("Directors", ", ".join(f"{d['name']} ({d['designation']})" for d in DIRECTORS))
        w.kv("Contents", "Independent auditor's report; balance sheet; statement of profit and loss; cash flow "
                         "statement; notes forming part of the financial statements")
        w.page()
        # Auditor's report.
        w.line("INDEPENDENT AUDITOR'S REPORT", 12, True, gap=16)
        w.line(f"To the Members of {NAME}", bold=True, gap=16)
        w.line("Report on the Audit of the Financial Statements", bold=True, gap=14)
        w.line("Opinion", bold=True)
        w.para(f"We have audited the accompanying financial statements of {NAME}, which comprise the Balance Sheet "
               f"as at 31 March {end_year}, the Statement of Profit and Loss and the Cash Flow Statement for the year "
               "then ended, and notes to the financial statements, including a summary of significant accounting "
               "policies.")
        w.para("In our opinion and to the best of our information and according to the explanations given to us, the "
               "aforesaid financial statements give the information required by the Companies Act, 2013 in the "
               "manner so required and give a true and fair view in conformity with the accounting principles "
               "generally accepted in India, of the state of affairs of the company as at 31 March "
               f"{end_year}, its profit and its cash flows for the year ended on that date.")
        w.line("Basis for Opinion", bold=True)
        w.para("We conducted our audit in accordance with the Standards on Auditing specified under section 143(10) "
               "of the Companies Act, 2013. We are independent of the company in accordance with the Code of Ethics "
               "issued by the Institute of Chartered Accountants of India, and we believe that the audit evidence we "
               "have obtained is sufficient and appropriate to provide a basis for our opinion.")
        w.line("Responsibilities of Management for the Financial Statements", bold=True)
        w.para("The Board of Directors is responsible for the preparation of these financial statements in accordance "
               "with the Accounting Standards specified under section 133 of the Act, and for such internal control "
               "as it determines is necessary.", after=16)
        w.line(f"For {AUDITOR}", bold=True)
        w.line("Chartered Accountants")
        w.line(f"Firm Registration No. {FRN}", gap=20)
        w.line("signed")
        w.line(f"{PARTNER}, Partner")
        w.line(f"Membership No. {MEMBERSHIP}")
        w.line(f"UDIN: {str(end_year)[2:]}{MEMBERSHIP}BMKQ{'RT' if end_year == 2026 else 'PL'}{7731 if end_year == 2026 else 4410}")
        w.line(f"Place: Thane | Date: {long_date(signed)}")
        w.page()
        # Balance sheet.
        w.line(NAME.upper(), 11, True, gap=13)
        w.line(f"CIN: {CIN}", 8.5, gap=13)
        w.line(f"BALANCE SHEET AS AT {ye}", 11, True, gap=13)
        w.line(AMOUNTS, 8.5, gap=16)
        w.cells([("As at 31 March", COL1, "right"), ("As at 31 March", COL2, "right")], 8.8, True, gap=11)
        w.cells([(str(end_year), COL1, "right"), (str(end_year - 1), COL2, "right")], 8.8, True, gap=13)
        w.cells([("Particulars", LEFT, "left")], 8.8, True, gap=14)
        _fs_rows(w, [
            ("I. EQUITY AND LIABILITIES", None, None, True),
            ("(1) Shareholders' funds", None, None, True),
            ("(a) Share capital", b["share_capital"], pb["share_capital"], False),
            ("(b) Reserves and surplus", b["reserves"], pb["reserves"], False),
            ("(2) Non-current liabilities", None, None, True),
            ("(a) Long-term borrowings", b["lt_borrowings"], pb["lt_borrowings"], False),
            ("(b) Deferred tax liabilities (net)", b["dtl"], pb["dtl"], False),
            ("(3) Current liabilities", None, None, True),
            ("(a) Short-term borrowings", 0, 0, False),
            ("(b) Trade payables", b["trade_payables"], pb["trade_payables"], False),
            ("(c) Other current liabilities", b["other_cl"], pb["other_cl"], False),
            ("(d) Short-term provisions", b["st_provisions"], pb["st_provisions"], False),
            ("TOTAL", b["total"], pb["total"], True),
            ("II. ASSETS", None, None, True),
            ("(1) Non-current assets", None, None, True),
            ("(a) Property, plant and equipment", b["ppe"], pb["ppe"], False),
            ("(b) Long-term loans and advances", b["lt_advances"], pb["lt_advances"], False),
            ("(2) Current assets", None, None, True),
            ("(a) Inventories", b["inventories"], pb["inventories"], False),
            ("(b) Trade receivables", b["receivables"], pb["receivables"], False),
            ("(c) Cash and bank balances", b["cash"], pb["cash"], False),
            ("(d) Short-term loans and advances", b["st_advances"], pb["st_advances"], False),
            ("(e) Other current assets", b["other_ca"], pb["other_ca"], False),
            ("TOTAL", b["total"], pb["total"], True),
            ("Net worth", b["share_capital"] + b["reserves"], pb["share_capital"] + pb["reserves"], True),
        ])
        w.page()
        # Statement of profit and loss.
        w.line(NAME.upper(), 11, True, gap=13)
        w.line(f"CIN: {CIN}", 8.5, gap=13)
        w.line(f"STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED {ye}", 11, True, gap=13)
        w.line(AMOUNTS, 8.5, gap=16)
        w.cells([("Year ended 31", COL1, "right"), ("Year ended 31", COL2, "right")], 8.8, True, gap=11)
        w.cells([(f"March {end_year}", COL1, "right"), (f"March {end_year - 1}", COL2, "right")], 8.8, True, gap=13)
        w.cells([("Particulars", LEFT, "left")], 8.8, True, gap=14)
        _fs_rows(w, [
            ("I. Revenue from operations", a["rev"], p["rev"], False),
            ("II. Other income", a["oi"], p["oi"], False),
            ("III. Total income (I + II)", a["total_income"], p["total_income"], True),
            ("IV. Expenses", None, None, True),
            ("(a) Cost of materials consumed", a["materials"], p["materials"], False),
            ("(b) Changes in inventories of finished goods and work-in-progress", a["inv_change"], p["inv_change"], False),
            ("(c) Employee benefits expense", a["employee"], p["employee"], False),
            ("(d) Finance costs", a["finance"], p["finance"], False),
            ("(e) Depreciation and amortisation expense", a["dep"], p["dep"], False),
            ("(f) Other expenses", a["other"], p["other"], False),
            ("Total expenses (IV)", a["expenses"], p["expenses"], True),
            ("V. Profit before tax (III - IV)", a["pbt"], p["pbt"], True),
            ("VI. Tax expense", None, None, True),
            ("(1) Current tax", a["current_tax"], p["current_tax"], False),
            ("(2) Deferred tax", a["deferred_tax"], p["deferred_tax"], False),
            ("VII. Profit for the year (V - VI)", a["pat"], p["pat"], True),
            ("VIII. Earnings per equity share of Rs. 10 each, basic and diluted", round(a["eps"], 2), round(p["eps"], 2), False),
            ("EBITDA", a["ebitda"], p["ebitda"], True),
        ])
        if "cf" in a:
            w.page()
            cf = a["cf"]
            w.line(NAME.upper(), 11, True, gap=13)
            w.line(f"CIN: {CIN}", 8.5, gap=13)
            w.line(f"CASH FLOW STATEMENT FOR THE YEAR ENDED {ye}", 11, True, gap=13)
            w.line(AMOUNTS, 8.5, gap=16)
            w.cells([("Year ended 31 March", COL2, "right")], 8.8, True, gap=11)
            w.cells([(str(end_year), COL2, "right")], 8.8, True, gap=13)
            w.cells([("Particulars", LEFT, "left")], 8.8, True, gap=14)
            rows = [
                ("A. Cash flow from operating activities", None, True),
                ("Profit before tax", a["pbt"], False),
                ("Add: Depreciation and amortisation expense", a["dep"], False),
                ("Add: Finance costs", a["finance"], False),
                ("Less: Interest income", -a["oi"], False),
                ("Operating profit before working capital changes", cf["op"], True),
                ("(Increase)/decrease in inventories", cf["wc"]["inventories"], False),
                ("(Increase)/decrease in trade receivables", cf["wc"]["receivables"], False),
                ("(Increase)/decrease in loans, advances and other assets", cf["wc"]["advances"], False),
                ("Increase/(decrease) in trade payables", cf["wc"]["payables"], False),
                ("Increase/(decrease) in other liabilities and provisions", cf["wc"]["other_cl"], False),
                ("Cash generated from operations", cf["generated"], True),
                ("Income tax paid", -a["current_tax"], False),
                ("Net cash from operating activities (A)", cf["cfo"], True),
                ("B. Cash flow from investing activities", None, True),
                ("Purchase of property, plant and equipment", -CAPEX[end_year], False),
                ("Interest received", a["oi"], False),
                ("Net cash used in investing activities (B)", cf["cfi"], True),
                ("C. Cash flow from financing activities", None, True),
                ("Repayment of long-term borrowings", DIRECTOR_LOANS[end_year] - DIRECTOR_LOANS[end_year - 1], False),
                ("Finance costs paid", -a["finance"], False),
                ("Net cash used in financing activities (C)", cf["cff"], True),
                ("Net increase in cash and bank balances (A + B + C)", cf["cfo"] + cf["cfi"] + cf["cff"], True),
                ("Cash and bank balances at the beginning of the year", cf["open"], False),
                ("Cash and bank balances at the end of the year", cf["close"], True),
            ]
            for label, v, bold in rows:
                w.cells([(label, LEFT, "left")] + ([(inr(v), COL2, "right")] if v is not None else []), 8.8, bold, gap=12.5)
        w.page()
        # Notes.
        fd = fixed_deposits() if end_year == 2026 else r1000(b["cash"] - CASH_IN_HAND - 41_00_000)
        w.line("NOTES FORMING PART OF THE FINANCIAL STATEMENTS", 11, True, gap=18)
        notes = [
            ("1. Corporate information", f"{NAME} is a private limited company incorporated in India on "
             f"{long_date(INCORPORATED)}. It manufactures {ACTIVITY} at its unit at MIDC Additional Ambernath."),
            ("2. Basis of preparation", "The financial statements are prepared under the historical cost convention on "
             "the accrual basis, in accordance with the Accounting Standards specified under section 133 of the "
             "Companies Act, 2013 (Indian GAAP)."),
            ("3. Long-term borrowings", f"Unsecured loans from directors, repayable after three years, carrying "
             f"interest at 9% a year: Rs. {inr(b['lt_borrowings'])} (previous year Rs. {inr(pb['lt_borrowings'])})."),
            ("4. Cash and bank balances", f"Cash on hand Rs. {inr(CASH_IN_HAND)}; balance in current account Rs. "
             f"{inr(b['cash'] - CASH_IN_HAND - fd)}; fixed deposits with banks Rs. {inr(fd)}."),
            ("5. Contingent liabilities", "None."),
            ("6. Related party transactions", "Remuneration and interest on unsecured loans paid to the directors are "
             "at arm's length and are included in employee benefits expense and finance costs."),
        ]
        for title, text in notes:
            w.line(title, bold=True)
            w.para(text)
        w.y -= 10
        w.cells([(f"For and on behalf of the Board of Directors", LEFT, "left"), (f"For {AUDITOR}", 330, "left")], 9)
        w.cells([(f"{DIRECTORS[0]['name']}, Managing Director (DIN {DIRECTORS[0]['din']})", LEFT, "left"),
                 ("Chartered Accountants", 330, "left")], 9)
        w.cells([(f"{DIRECTORS[1]['name']}, Director (DIN {DIRECTORS[1]['din']})", LEFT, "left"),
                 (f"{PARTNER}, Partner", 330, "left")], 9)
        w.cells([(f"Place: Thane | Date: {long_date(signed)}", LEFT, "left")], 9)
    return draw


def itr(end_year: int) -> Callable[[Writer], None]:
    ay = f"{end_year}-{str(end_year + 1)[2:]}"
    filed = date(2026, 10, 27) if end_year == 2026 else date(2025, 10, 29)
    ack = f"{(7 if end_year == 2026 else 6)}{str(end_year)[2:]}{filed.month:02d}{filed.day:02d}1018{4821 + end_year}"

    def draw(w: Writer) -> None:
        a = ACC[end_year]
        w.line("INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT", 12.5, True, align="center", gap=15)
        w.line("[Where the data of the Return of Income in Form ITR-6 is transmitted electronically]", 8.5,
               align="center", gap=11)
        w.line("(Please see Rule 12 of the Income-tax Rules, 1962)", 8.5, align="center", gap=20)
        w.kv("PAN", PAN)
        w.kv("Name of Assessee", NAME)
        w.kv("Address", OFFICE)
        w.kv("Status", "Domestic Company")
        w.kv("Financial Year", fy_label(end_year))
        w.kv("Assessment Year", ay)
        w.kv("Form Number", "ITR-6")
        w.kv("Filed under section", "139(1), on or before the due date")
        w.kv("Acknowledgement Number", ack)
        w.kv("Date of Filing", long_date(filed))
        w.y -= 8
        w.line("Taxable income and tax details (amounts in INR)", bold=True, gap=16)
        w.kv("Gross Total Income", inr(a["gti"]))
        w.kv("Deductions under Chapter VI-A", "0")
        w.kv("Total Income", inr(a["ti"]))
        w.kv("Total Tax Payable", inr(a["current_tax"]))
        w.kv("Interest and Fee Payable", "0")
        w.kv("Taxes Paid", inr(a["current_tax"]))
        w.kv("Refund Due", "0")
        w.y -= 12
        w.para(f"This return has been filed electronically and verified by {DIRECTORS[0]['name']}, "
               f"{DIRECTORS[0]['designation']}, on {long_date(filed)}.", 9)
        w.page()
        w.line("COMPUTATION OF TOTAL INCOME", 12, True, gap=16)
        w.line(f"{NAME}  |  PAN {PAN}  |  Assessment Year {ay} (Previous Year {fy_label(end_year)})", 8.5, gap=20)
        w.cells([("Particulars", LEFT, "left"), ("Amount (INR)", COL2, "right")], 9, True, gap=15)
        rows = [
            ("Revenue from operations (as per books)", a["rev"]),
            ("Net profit before tax as per statement of profit and loss", a["pbt"]),
            ("Add: Depreciation as per books", a["dep"]),
            ("Add: Interest on late statutory payments disallowed under section 37", a["disallowed"]),
            ("Less: Depreciation allowable under section 32", -a["tax_dep"]),
            ("Less: Interest income considered under other sources", -a["oi"]),
            ("Income from business or profession", a["business"]),
            ("Income from other sources (interest on deposits)", a["oi"]),
            ("Gross total income", a["gti"]),
            ("Less: Deductions under Chapter VI-A", 0),
            ("Total income (rounded off)", a["ti"]),
            ("Tax at 22% under section 115BAA", a["tax_base"]),
            ("Add: Surcharge at 10%", a["surcharge"]),
            ("Add: Health and education cess at 4%", a["cess"]),
            ("Total tax payable", a["current_tax"]),
            ("Less: Advance tax paid", -round(a["current_tax"] * 0.92)),
            ("Less: Tax deducted at source", -(a["current_tax"] - round(a["current_tax"] * 0.92))),
            ("Tax payable / (refundable)", 0),
        ]
        for label, v in rows:
            w.cells([(label, LEFT, "left"), (inr(v), COL2, "right")], 9, gap=13.5)
        w.y -= 8
        w.line("Reconciliation", bold=True)
        w.para("The total income above follows the audited statement of profit and loss for the previous year, "
               "adjusted for depreciation allowable under the Act and the amount disallowed under section 37.", 9)
    return draw


# --- Banking and operations ---------------------------------------------------------------------

STATEMENT_START, STATEMENT_END = date(2025, 10, 1), date(2026, 10, 31)


def bank_statement(w: Writer) -> None:
    def head(first: bool) -> None:
        if first:
            w.line(BANK, 13, True, gap=15)
            w.line(f"{BRANCH} Branch - Statement of Account", 10, gap=18)
            w.kv("Account Name", NAME, 9)
            w.kv("Account Number", ACCOUNT, 9)
            w.kv("Account Type", "Current Account", 9)
            w.kv("Branch / IFSC", f"{BRANCH} / {IFSC}", 9)
            w.kv("Statement", f"{short_date(STATEMENT_START)} to {short_date(STATEMENT_END)}", 9)
            w.kv("Currency", "INR", 9)
            w.cells([(f"Opening Balance ({short_date(STATEMENT_START)})", LEFT, "left"), (inr(OPENING), 548, "right")], 8,
                    gap=18)
        w.cells([("Date", LEFT, "left"), ("Particulars", 112, "left"), ("Reference", 292, "left"),
                 ("Debit", 418, "right"), ("Credit", 482, "right"), ("Balance", 548, "right")], 8, True, gap=13)

    head(True)
    bal = OPENING
    credits = debits = 0
    for when, text, ref, debit, credit in STATEMENT:
        if w.y < 80:
            w.page()
            w.cells([(f"Account Number {ACCOUNT} - {short_date(STATEMENT_START)} to {short_date(STATEMENT_END)} (continued)",
                      LEFT, "left")], 8, gap=16)
            head(False)
        bal += credit - debit
        assert bal > 0, (when, bal)
        credits += credit
        debits += debit
        w.cells([(short_date(when), LEFT, "left"), (text, 112, "left"), (ref, 292, "left"),
                 (inr(debit) if debit else "", 418, "right"), (inr(credit) if credit else "", 482, "right"),
                 (inr(bal), 548, "right")], 8, gap=12)
    w.y -= 10
    w.room(90)
    w.line("Statement Summary", 10, True, gap=14)
    w.line(f"Account {ACCOUNT} - {short_date(STATEMENT_START)} to {short_date(STATEMENT_END)}", 9, gap=14)
    for label, v in ((f"Opening Balance ({short_date(STATEMENT_START)})", OPENING),
                     ("Total Credits during period", credits), ("Total Debits during period", debits),
                     (f"Closing Balance ({short_date(STATEMENT_END)})", bal)):
        w.cells([(label, LEFT, "left"), (inr(v), 548, "right")], 8)
    w.y -= 8
    w.para("This is a computer-generated statement and does not require a signature.", 8.5)


def gstr3b(month: dict) -> Callable[[Writer], None]:
    def draw(w: Writer) -> None:
        y, m = month["y"], month["m"]
        fy_end = y + 1 if m >= 4 else y
        o, itc, paid, cash = month["out"], month["itc"], month["paid_itc"], month["cash"]
        w.line("FORM GSTR-3B", 13, True, gap=14)
        w.line("[See rule 61(5)]", 8.5, gap=16)
        w.kv("Year", fy_label(fy_end), 9)
        w.kv("Period", MONTHS[m - 1], 9)
        w.kv("1. GSTIN", GSTIN, 9)
        w.cells([("2(a). Legal name of the registered person", LEFT, "left"), (NAME, 330, "left")], 9)
        w.cells([("2(b). Trade name, if any", LEFT, "left"), (NAME, 330, "left")], 9)
        w.cells([("2(c). ARN", LEFT, "left"), (month["arn"], 330, "left")], 9)
        w.cells([("2(d). Date of ARN", LEFT, "left"), (long_date(month["filed"]), 330, "left")], 9, gap=20)
        x = (395, 450, 505, 555)
        w.line("3.1 Details of Outward Supplies and inward supplies liable to reverse charge", 9, True, gap=14)
        w.cells([("Nature of Supplies", LEFT, "left"), ("Taxable", x[0], "right"), ("IGST", x[1], "right"),
                 ("CGST", x[2], "right"), ("SGST", x[3], "right")], 8.5, True, gap=13)
        for label, vals in (
            ("(a) Outward taxable supplies (other than zero rated, nil rated, exempted)",
             (month["sales"], o["igst"], o["cgst"], o["sgst"])),
            ("(b) Outward taxable supplies (zero rated)", (0, 0, 0, 0)),
            ("(c) Other outward supplies (nil rated, exempted)", (0, 0, 0, 0)),
            ("(d) Inward supplies (liable to reverse charge)", (0, 0, 0, 0)),
            ("(e) Non-GST outward supplies", (0, 0, 0, 0)),
        ):
            w.cells([(label, LEFT, "left")] + [(inr(v), xx, "right") for v, xx in zip(vals, x)], 8.2, gap=12.5)
        w.y -= 6
        w.line("4. Eligible ITC", 9, True, gap=14)
        w.cells([("Details", LEFT, "left"), ("IGST", x[1], "right"), ("CGST", x[2], "right"), ("SGST", x[3], "right")],
                8.5, True, gap=13)
        for label, vals in (
            ("(A) ITC Available (all other ITC)", (itc["igst"], itc["cgst"], itc["sgst"])),
            ("(B) ITC Reversed", (0, 0, 0)),
            ("(C) Net ITC Available (A) - (B)", (itc["igst"], itc["cgst"], itc["sgst"])),
            ("(D) Ineligible ITC", (0, 0, 0)),
        ):
            w.cells([(label, LEFT, "left")] + [(inr(v), xx, "right") for v, xx in zip(vals, x[1:])], 8.2, gap=12.5)
        w.y -= 6
        w.line("5. Values of exempt, nil-rated and non-GST inward supplies: Nil", 9, True, gap=14)
        w.line("5.1 Interest and late fee payable: Nil", 9, True, gap=18)
        w.line("6.1 Payment of tax", 9, True, gap=14)
        px = (330, 440, 548)
        w.cells([("Description", LEFT, "left"), ("Tax Payable", px[0], "right"), ("Paid through ITC", px[1], "right"),
                 ("Paid in cash", px[2], "right")], 8.5, True, gap=13)
        for label, head_ in (("Integrated Tax", "igst"), ("Central Tax", "cgst"), ("State/UT Tax", "sgst")):
            w.cells([(label, LEFT, "left"), (inr(o[head_]), px[0], "right"), (inr(paid[head_]), px[1], "right"),
                     (inr(cash[head_]), px[2], "right")], 8.2, gap=12.5)
        w.cells([("Cess", LEFT, "left"), ("0", px[0], "right"), ("0", px[1], "right"), ("0", px[2], "right")], 8.2,
                gap=18)
        w.para(f"Verified and filed by {DIRECTORS[0]['name']} (authorised signatory) on {long_date(month['filed'])}.", 8.5)
    return draw


# --- The pack -----------------------------------------------------------------------------------

SEPARATE: list[tuple[str, list[Callable[[Writer], None]]]] = [
    ("01 Certificate of Incorporation.pdf", [certificate_of_incorporation]),
    ("02 Memorandum and Articles of Association.pdf", [memorandum_and_articles]),
    ("03 Board Resolution for Borrowing.pdf", [board_resolution]),
    ("04 Company PAN.pdf", [company_pan]),
    ("05 Director KYC - Nandini and Aditya Gokhale.pdf", [director_kyc]),
    ("06 Audited Financial Statements FY 2025-26.pdf", [afs(2026)]),
    ("07 Audited Financial Statements FY 2024-25.pdf", [afs(2025)]),
    ("08 ITR-6 Acknowledgement and Computation AY 2026-27.pdf", [itr(2026)]),
    ("09 ITR-6 Acknowledgement and Computation AY 2025-26.pdf", [itr(2025)]),
    ("10 Bank Statement Current Account Oct 2025 to Oct 2026.pdf", [bank_statement]),
    ("11 GSTR-3B Oct 2025 to Oct 2026.pdf", [gstr3b(mo) for mo in GST_MONTHS]),
]

COMBINED = [
    ("1 Constitution and KYC.pdf", [f for _, fs in SEPARATE[:5] for f in fs]),
    ("2 Financials.pdf", [f for _, fs in SEPARATE[5:9] for f in fs]),
    ("3 Banking and operations.pdf", [f for _, fs in SEPARATE[9:] for f in fs]),
]


def write(path: Path, parts: list[Callable[[Writer], None]]) -> None:
    w = Writer(path)
    for draw in parts:
        w.new_document()
        draw(w)
    w.close()


def main() -> None:
    out = Path(sys.argv[1])
    for sub, files in (("separate", SEPARATE), ("combined", COMBINED)):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for name, parts in files:
            write(out / sub / name, parts)
    print(f"GSTIN {GSTIN}; opening balance {inr(OPENING)}; FY26 revenue {inr(REVENUE[2026])}, PBT {inr(ACC[2026]['pbt'])}")


if __name__ == "__main__":
    main()
