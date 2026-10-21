"""Test document sets for the cross-checks, completeness and reading tests.

One fictional borrower (Kestrel Fabricators Private Limited, a fictional lender and a fictional bank) and a clean
baseline set of documents in the layouts the service reads, plus scenario sets that change one thing each. The
documents carry only a one-line footer; what each scenario plants is written to `manifest.md` beside the sets, never
into a document. Every name, number and date is fictional. Positioned-text PDFs, like docgen: the bytes are
deterministic.

    PYTHONPATH=. .venv/bin/python -m tests.docsets <output directory>
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

from .docgen import Cell, _escape, text_width

FOOTER = "Synthetic specimen for software testing. All names and numbers are fictional."
REFERENCE = "14 October 2026"   # the case date the baseline is written for (periods and ages follow from it)

_ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_with_check(first14: str) -> str:
    """A GSTIN whose last character is the right check character."""
    total = 0
    for i, ch in enumerate(first14):
        v = _ALPHA.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return first14 + _ALPHA[(36 - total % 36) % 36]


# --- the writer ---------------------------------------------------------------------------------------------

Row = list[Cell]
PER_PAGE = 46


def paginate(rows: list[Row], per_page: int = PER_PAGE) -> list[list[Row]]:
    return [rows[i:i + per_page] for i in range(0, max(len(rows), 1), per_page)]


def build(pages: list[list[Row]], *, size: float = 10.0, leading: float = 16.0) -> bytes:
    """Pages of rows from the top; the one-line footer is added at the foot of every page."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages))) + f"] /Count {len(pages)} >>").encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, rows in enumerate(pages):
        ops, y = [], 800.0
        for row in rows:
            for cell in row:
                x, text = float(cell[0]), str(cell[1])
                if len(cell) > 2 and cell[2] == "r":
                    x -= text_width(text, size)
                ops.append(f"BT /F1 {size:g} Tf {x:.2f} {y:.2f} Td ({_escape(text)}) Tj ET")
            y -= leading
        ops.append(f"BT /F1 7 Tf 50 24 Td ({_escape(FOOTER)}) Tj ET")
        stream = "\n".join(ops)
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                        f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>").encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream".encode("latin-1"))
    out = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def one_page(rows: list[Row]) -> bytes:
    return build([rows])


# --- the borrower -------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Person:
    name: str
    din: str
    designation: str
    dob: str
    pan_masked: str
    aadhaar_masked: str
    address: str


@dataclass(frozen=True)
class Entity:
    name: str = "Kestrel Fabricators Private Limited"
    pan: str = "AAACK1234F"
    cin: str = "U28999MH2015PTC123456"
    gstin: str = "27AAACK1234F1Z0"
    incorporated: str = "18 March 2015"
    office: str = "Plot 21, MIDC Industrial Area, Taloja, Navi Mumbai 410208, Maharashtra"
    state: str = "Maharashtra"
    roc: str = "Registrar of Companies, Mumbai"
    bank: str = "Harbour Commercial Bank"
    branch: str = "Taloja"
    ifsc: str = "HCBL0004417"
    account: str = "602010345567"
    lender: str = "Lotuscrest Finance Limited"
    persons: tuple[Person, ...] = (
        Person("Meera Sathe", "08123456", "Managing Director", "04 May 1976", "AXXXX4321K", "XXXX XXXX 7714",
               "Flat 12, Orchid Heights, Kharghar, Navi Mumbai 410210, Maharashtra"),
        Person("Rohan Sathe", "08123470", "Director", "19 November 1981", "BXXXX5678L", "XXXX XXXX 2290",
               "Flat 12, Orchid Heights, Kharghar, Navi Mumbai 410210, Maharashtra"),
    )

    @property
    def upper(self) -> str:
        return self.name.upper()


BASE = Entity()
OTHER_PAN = "AAACT7788M"                      # another company's PAN, same format
OTHER_GSTIN = gstin_with_check("27AAACT7788M1Z")
OTHER_CIN = "U28999MH2016PTC654321"

# Monthly outward taxable supplies, April 2025 to September 2026 (rupees).
MONTHS = [(2025, m) for m in range(4, 13)] + [(2026, m) for m in range(1, 10)]
OUTWARD = [18_400_000, 19_250_000, 20_100_000, 17_800_000, 19_900_000, 21_300_000, 22_050_000, 20_700_000, 19_600_000,
           18_950_000, 20_450_000, 23_100_000, 21_800_000, 20_900_000, 22_300_000, 23_450_000, 21_100_000, 22_700_000]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FULLMON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def inr(n: float) -> str:
    """Indian digit grouping: 12,34,56,789."""
    n = int(round(n))
    s = str(abs(n))
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    out = ",".join(parts + [tail]) if parts else tail
    return ("-" if n < 0 else "") + out


def kv(rows: list[Row], pairs: list[tuple[str, str]], x2: int = 200) -> None:
    for k, v in pairs:
        rows.append([(50, k), (x2, v)])


# --- identity documents ------------------------------------------------------------------------------------

def certificate_of_incorporation(e: Entity = BASE, *, cin: str | None = None, name: str | None = None, date: str | None = None) -> bytes:
    rows: list[Row] = [[(50, "CERTIFICATE OF INCORPORATION")], [(50, "Central Registration Centre")], []]
    kv(rows, [("Name of Company", name or e.name), ("Corporate Identity Number", cin or e.cin),
              ("Date of Incorporation", date or e.incorporated), ("Company Category", "Company limited by shares"),
              ("Registered Office", e.office)])
    rows += [[], [(50, f"Given under my hand at Mumbai on {date or e.incorporated}.")], [(50, f"Office of the {e.roc}")]]
    return one_page(rows)


def company_pan(e: Entity = BASE, *, pan: str | None = None, name: str | None = None) -> bytes:
    rows: list[Row] = [[(50, "INTIMATION OF ALLOTMENT OF PERMANENT ACCOUNT NUMBER (PAN)")], [(50, "Date: 24 March 2015")], [],
                       [(50, "To,")], [(50, name or e.name)], [(50, e.office)], []]
    kv(rows, [("Permanent Account Number", pan or e.pan), ("Name", name or e.name), ("Status", "Company"),
              ("Date of Incorporation", e.incorporated)])
    rows += [[], [(50, "This is a computer-generated intimation letter. No signature is required.")]]
    return one_page(rows)


def memorandum(e: Entity = BASE, *, directors: tuple[str, ...] | None = None, cin: str | None = None) -> bytes:
    names = directors if directors is not None else tuple(p.name for p in e.persons)
    first = [
        [(50, "MEMORANDUM OF ASSOCIATION")], [],
        [(50, f"I. The name of the company is {e.upper}.")],
        [(50, f"II. The registered office of the company will be situated in the State of {e.state}.")],
        [(50, "III. The main objects to be pursued by the company on its incorporation are to manufacture and trade in")],
        [(50, "fabricated metal components and to carry on the business of precision engineering.")],
        [(50, "V. The authorised share capital of the company is Rs. 1,00,00,000 divided into 10,00,000 equity shares of Rs. 10 each.")],
        [(50, "The paid-up capital is Rs. 50,00,000 divided into 5,00,000 equity shares of Rs. 10 each.")],
        [(50, "The first directors of the company are " + " and ".join(f"Smt. {n}" if n.split()[0] in ("Meera",) else f"Sri. {n}" for n in names) + ".")],
        [(50, f"Corporate Identity Number {cin or e.cin}")],
    ]
    sub = [
        [(50, "SUBSCRIPTION CLAUSE")], [],
        [(50, "Name, address, description and occupation of subscriber"), (330, "No.", "r"), (400, "Signature")],
        [(50, "Name,"), (330, "No.", "r"), (400, "Signature")],
    ]
    shares = [300000, 200000]
    for i, n in enumerate(names[:2]):
        sub.append([(50, n), (330, inr(shares[i]), "r"), (400, "signed")])
    sub += [[(50, "Total"), (330, inr(sum(shares[:len(names[:2])])), "r")], [], [(50, "Dated this 12th day of March 2015")]]
    return build([first, sub])


def director_kyc(e: Entity = BASE, *, persons: tuple[Person, ...] | None = None) -> bytes:
    pages = []
    for p in persons if persons is not None else e.persons:
        rows: list[Row] = [[(50, e.name)], [(50, f"CIN: {e.cin} | PAN: {e.pan} | GSTIN: {e.gstin}")],
                           [(50, "DIRECTOR KYC SUMMARY SHEET")], []]
        kv(rows, [("Name of Director", p.name), ("Designation", p.designation), ("Director Identification Number", p.din),
                  ("Date of Birth", p.dob), ("Residential Address", p.address), ("Nationality", "Indian"),
                  ("PAN (masked)", p.pan_masked), ("Aadhaar (masked)", p.aadhaar_masked),
                  ("Relationship with company", "Promoter and Director")], x2=230)
        rows += [[], [(50, "Personal identifiers are shown in masked form.")]]
        pages.append(rows)
    return build(pages)


# --- authority and obligations ------------------------------------------------------------------------------

def board_resolution(e: Entity = BASE, *, amount: str = "4,25,00,000", amount_words: str = "Four Crore Twenty-Five Lakh",
                     lender: str = "Harbour Commercial Bank, Taloja Branch", date: str = "Monday, 12 October 2026",
                     signed: bool = True, signatories: tuple[Person, ...] | None = None) -> bytes:
    sig = signatories if signatories is not None else e.persons
    rows: list[Row] = [
        [(50, "CERTIFIED TRUE COPY OF THE RESOLUTION")], [],
        [(50, f"Certified true copy of the resolution passed at the meeting of the Board of Directors of {e.name}")],
        [(50, f"(CIN {e.cin}) held at the registered office of the company on {date} at 11:00 a.m.")], [],
        [(50, "RESOLVED THAT the consent of the Board of Directors be and is hereby accorded to borrow from " + lender + ",")],
        [(50, f"credit facilities by way of a Cash Credit limit and a Term Loan, aggregating to Rs. {amount}")],
        [(50, f"(Rupees {amount_words} only), on such terms and conditions as may be stipulated by the said bank.")], [],
        [(50, "RESOLVED FURTHER THAT " + " and ".join(
            f"{'Smt.' if p.name.startswith('Meera') else 'Sri.'} {p.name}, {p.designation} (DIN {p.din})" for p in sig)
          + ", be and are hereby severally authorised to execute all loan agreements and security documents.")], [],
        [(50, "For and on behalf of the Board of Directors")],
    ]
    if signed:
        rows += [[(50, f"Name: {sig[0].name}"), (330, f"Name: {sig[-1].name}")],
                 [(50, f"Designation: {sig[0].designation}"), (330, f"Designation: {sig[-1].designation}")],
                 [(50, "Signature: signed"), (330, "Signature: signed")],
                 [(50, f"Date: {date.split(', ')[-1]}"), (330, f"Date: {date.split(', ')[-1]}")]]
    else:
        rows += [[(50, "Name:"), (330, "Name:")], [(50, "Designation:"), (330, "Designation:")],
                 [(50, "Signature:"), (330, "Signature:")], [(50, "Date:"), (330, "Date:")]]
    return one_page(rows)


def facilities_declaration(e: Entity = BASE, *, facilities: list[tuple[str, str, str, str, str]] | None = None,
                           accounts: list[tuple[str, str, str]] | None = None, pan: str | None = None,
                           cin: str | None = None, gstin: str | None = None, signed: bool = True) -> bytes:
    facilities = facilities if facilities is not None else [(e.lender, "Term Loan", "2,50,00,000", "1,62,50,000", "1,25,000")]
    accounts = accounts if accounts is not None else [(e.bank, e.account, "Current Account")]
    rows: list[Row] = [
        [(50, "DECLARATION OF EXISTING CREDIT FACILITIES AND BANK ACCOUNTS")], [],
        [(50, "Name of Company"), (200, e.name)], [(50, "Date of Declaration"), (200, "12 October 2026")],
        [(50, "PAN"), (200, pan or e.pan)], [(50, "CIN"), (200, cin or e.cin)], [(50, "GSTIN"), (200, gstin or e.gstin)], [],
        [(50, "We hereby declare that the company has the following existing credit facilities as on this date:")], [],
        [(50, "Name of Lender"), (190, "Nature of Facility"), (390, "Sanctioned Limit", "r"), (470, "Outstanding", "r"), (540, "EMI", "r")],
    ]
    for lender, facility, limit, outstanding, emi in facilities:
        rows.append([(50, lender), (190, facility), (390, limit, "r"), (470, outstanding, "r"), (540, emi, "r")])
    rows += [[(50, "Total")], [], [(50, "We also declare that the company holds the following bank accounts:")], [],
             [(50, "Name of Bank"), (200, "Account Number"), (340, "Type of Account")]]
    for bank, number, kind in accounts:
        rows.append([(50, bank), (200, number), (340, kind)])
    rows += [[], [(50, f"For {e.name}")]]
    rows += [[(50, "Authorised Signatory: " + e.persons[0].name)]] if signed else [[(50, "Authorised Signatory")]]
    return one_page(rows)


def sanction_letter(e: Entity = BASE, *, lender: str | None = None, facility: str = "Term Loan", amount: str = "2,50,00,000",
                    rate: str = "10.75% p.a.", tenure: str = "72 months", emi: str = "1,25,000") -> bytes:
    lender = lender or e.lender
    rows: list[Row] = [
        [(50, lender.upper())], [(50, "SANCTION LETTER")], [],
        [(50, "Reference"), (200, "LCF/SL/2024/0457")], [(50, "Date of Sanction"), (200, "12 April 2024")],
        [(50, "Borrower"), (200, e.name)], [(50, "Lender"), (200, lender)], [],
        [(50, "We are pleased to sanction the following credit facility on the terms and conditions below.")], [],
        [(50, "Facility"), (250, "Sanctioned Amount", "r"), (270, "Rate of Interest"), (390, "Tenure"), (540, "EMI", "r")],
        [(50, facility), (250, amount, "r"), (270, rate), (390, tenure), (540, emi, "r")], [],
        [(50, "Terms and conditions")], [(50, "1. The facility is secured by hypothecation of the plant and machinery financed.")], [],
        [(50, f"For {lender}")], [(50, "Authorised Signatory")],
    ]
    return one_page(rows)


def bureau_report(e: Entity = BASE, *, facilities: list[tuple[str, str, str, str, str, str]] | None = None,
                  pan: str | None = None, cin: str | None = None, gstin: str | None = None,
                  parties: list[tuple[str, str, str]] | None = None) -> bytes:
    facilities = facilities if facilities is not None else [(e.lender, "Term Loan", "2,50,00,000", "1,62,50,000", "0", "Standard")]
    parties = parties if parties is not None else [(p.name, "Director", p.pan_masked) for p in e.persons]
    rows: list[Row] = [
        [(50, "COMMERCIAL CREDIT INFORMATION REPORT")], [],
        [(50, "Report Date"), (200, "13 October 2026")], [(50, "Company Name"), (200, e.name)],
        [(50, "PAN"), (200, pan or e.pan)], [(50, "CIN"), (200, cin or e.cin)], [(50, "GSTIN"), (200, gstin or e.gstin)],
        [(50, "Credit Rank"), (200, "4")], [],
        [(50, "CREDIT FACILITIES")],
        [(50, "Lender"), (190, "Facility"), (330, "Sanctioned", "r"), (410, "Outstanding", "r"), (470, "Overdue", "r"), (490, "Status")],
    ]
    for lender, facility, sanctioned, outstanding, overdue, status in facilities:
        rows.append([(50, lender), (190, facility), (330, sanctioned, "r"), (410, outstanding, "r"), (470, overdue, "r"), (490, status)])
    rows += [[], [(50, "RELATED PARTIES")], [(50, "Name"), (200, "Relationship"), (340, "PAN")]]
    for name, relationship, pan_ in parties:
        rows.append([(50, name), (200, relationship), (340, pan_)])
    rows += [[], [(50, "END OF REPORT")]]
    return one_page(rows)


# --- the bank statement -------------------------------------------------------------------------------------

@dataclass
class Txn:
    day: str            # "03 Oct 2025"
    narration: str
    ref: str
    debit: int = 0
    credit: int = 0


CUSTOMERS = ["BHARAT PUMPS LTD", "ORIENT GEARBOX CO", "VARDHAN AUTOMOTIVE", "SUNRISE HYDRAULICS", "PRAGATI TOOLING"]


def statement_transactions(months: list[tuple[int, int]], credits_by_month: dict[tuple[int, int], int], *, opening: int,
                           emi: int = 125_000, emi_party: str = "LOTUSCREST FIN", emi_months: set[tuple[int, int]] | None = None,
                           extra: list[tuple[tuple[int, int], Txn]] | None = None) -> list[Txn]:
    out: list[Txn] = []
    n = 0
    for (y, m) in months:
        total = credits_by_month[(y, m)]
        for d, share, cust in ((3, 0.35, CUSTOMERS[m % 5]), (11, 0.40, CUSTOMERS[(m + 1) % 5]), (19, 0.25, CUSTOMERS[(m + 2) % 5])):
            n += 1
            out.append(Txn(f"{d:02d} {MON[m - 1]} {y}", f"NEFT CR {cust}", f"NEFT/{40000000 + n * 7919}", credit=int(total * share)))
        for d, share, what in ((5, 0.62, "RTGS DR SUPPLIER PAYMENT"), (14, 0.10, "NEFT DR VENDOR PAYMENT"), (28, 0.14, "NEFT DR SALARY")):
            n += 1
            out.append(Txn(f"{d:02d} {MON[m - 1]} {y}", what, f"UTR/{50000000 + n * 6007}", debit=int(total * share)))
        if emi_months is None or (y, m) in emi_months:
            n += 1
            out.append(Txn(f"07 {MON[m - 1]} {y}", f"NACH DR {emi_party} 000123 EMI", f"ACH/{emi_party[:5]}/{n}", debit=emi))
        out.append(Txn(f"25 {MON[m - 1]} {y}", "NEFT DR GST CHALLAN PAYMENT", f"GST/{n}", debit=int(total * 0.03)))
        for (ym, t) in extra or []:
            if ym == (y, m):
                out.append(t)
    out.sort(key=lambda t: (int(t.day[-4:]), MON.index(t.day[3:6]), int(t.day[:2])))
    return out


def bank_statement(e: Entity = BASE, *, txns: list[Txn], opening: int, start: str, end: str, account: str | None = None,
                   holder: str | None = None, bank: str | None = None) -> bytes:
    account = account or e.account
    bal = opening
    body: list[Row] = []
    credits = debits = 0
    for t in txns:
        bal += t.credit - t.debit
        credits += t.credit
        debits += t.debit
        body.append([(50, t.day), (125, t.narration), (320, t.ref), (462, inr(t.debit) if t.debit else "", "r"),
                     (525, inr(t.credit) if t.credit else "", "r"), (588, inr(bal), "r")])
    head: list[Row] = [
        [(50, bank or e.bank)], [(50, f"{e.branch} Branch - Statement of Account")], [],
        [(50, "Account Name"), (200, holder or e.name)],
        [(50, "Account Number"), (200, account)],
        [(50, "Branch / IFSC"), (200, f"{e.branch} / {e.ifsc}")],
        [(50, "Statement"), (200, f"{start} to {end}")],
        [(50, "Currency"), (200, "INR")],
        [(50, f"Opening Balance ({start})"), (330, inr(opening))],
        [],
        [(50, "Date"), (125, "Particulars"), (320, "Reference"), (462, "Debit", "r"), (525, "Credit", "r"), (588, "Balance", "r")],
    ]
    summary: list[Row] = [
        [(50, "Statement Summary")], [(50, f"Account {account} - {start} to {end}")],
        [(50, f"Opening Balance ({start})"), (330, inr(opening))],
        [(50, f"Total Credits during period"), (330, inr(credits))],
        [(50, f"Total Debits during period"), (330, inr(debits))],
        [(50, f"Closing Balance ({end})"), (330, inr(bal))],
    ]
    rows = head + body
    pages = paginate(rows)
    pages[-1] = pages[-1] + [[]] + summary
    return build(pages)


# --- GST, tax and financial statements -----------------------------------------------------------------------

def gstr_3b(e: Entity = BASE, *, month: tuple[int, int], taxable: int, gstin: str | None = None, filed_on: str | None = None,
            name: str | None = None) -> bytes:
    y, m = month
    fy = f"{y}-{(y + 1) % 100:02d}" if m >= 4 else f"{y - 1}-{y % 100:02d}"
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    filed = filed_on or (f"20 {MON[nm - 1]} {ny}" if (ny, nm) <= (2026, 9) else "12 October 2026")   # never after the case date
    igst = int(taxable * 0.18)
    rows: list[Row] = [
        [(50, "FORM GSTR-3B")], [(50, "[See rule 61(5)]")], [],
        [(50, "Year"), (200, fy)], [(50, "Period"), (200, MON[m - 1])], [],
        [(50, "1. GSTIN"), (200, gstin or e.gstin)],
        [(50, "2(a). Legal name of the registered person"), (330, name or e.name)],
        [(50, "2(b). Trade name, if any"), (330, name or e.name)],
        [(50, "2(d). Date of ARN"), (330, filed)], [],
        [(50, "3.1 Details of Outward Supplies and inward supplies liable to reverse charge")],
        [(50, "Nature of Supplies"), (360, "Taxable", "r"), (430, "IGST", "r"), (490, "CGST", "r"), (555, "SGST", "r")],
        [(50, "(a) Outward taxable supplies"), (360, inr(taxable), "r"),
         (430, inr(igst), "r"), (490, "0", "r"), (555, "0", "r")],
        [(50, "(b) Zero rated supplies"), (360, "0", "r"), (430, "0", "r"), (490, "0", "r"), (555, "0", "r")],
        [(50, "(c) Nil rated and exempted"), (360, "0", "r"), (430, "0", "r"), (490, "0", "r"), (555, "0", "r")],
        [(50, "(d) Inward reverse charge"), (360, "0", "r"), (430, "0", "r"), (490, "0", "r"), (555, "0", "r")],
        [], [(50, "4. Eligible ITC")],
    ]
    return one_page(rows)


def income_tax_return(e: Entity = BASE, *, turnover: int, profit: int, pan: str | None = None, name: str | None = None,
                      ay: str = "2026-27", fy: str = "2025-26", filed: str = "28 September 2026",
                      gross: int | None = None, total: int | None = None) -> bytes:
    gross = gross if gross is not None else profit
    total = total if total is not None else profit
    rows: list[Row] = [
        [(50, "INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT")], [],
        [(50, "Acknowledgement Number"), (230, "262710009280926")], [(50, "Date of Filing"), (230, filed)],
        [(50, "Assessment Year"), (230, ay)], [(50, "Financial Year"), (230, fy)],
        [(50, "Name of Assessee"), (230, name or e.name)], [(50, "PAN"), (230, pan or e.pan)], [],
        [(50, "Gross Total Income"), (230, inr(gross))], [(50, "Total Income"), (230, inr(total))],
        [(50, "Total Tax Payable"), (230, inr(int(total * 0.25)))], [(50, "Taxes Paid"), (230, inr(int(total * 0.25)))],
        [(50, "Refund Due"), (230, "0")], [],
    ]
    comp: list[Row] = [
        [(50, "COMPUTATION OF TOTAL INCOME")], [],
        [(50, "Particulars"), (450, "Amount (INR)", "r")],
        [(50, "Revenue from operations"), (450, inr(turnover), "r")],
        [(50, "Net profit as per statement of profit and loss"), (450, inr(profit), "r")],
        [(50, "Total income"), (450, inr(total), "r")],
        [(50, "Reconciliation")],
    ]
    return build([rows, comp])


def audited_statements(e: Entity = BASE, *, revenue: int, profit_before_tax: int, fy_end: int = 2026, name: str | None = None,
                       cash: int = 9_500_000, borrowings: int = 16_250_000, auditor: str = "Daruwala and Rane, Chartered Accountants",
                       signed_on: str = "27 August 2026") -> bytes:
    cy, py = fy_end, fy_end - 1
    prev_rev, prev_pbt = int(revenue * 0.91), int(profit_before_tax * 0.9)
    co = name or e.name
    cover: list[Row] = [
        [(50, "INDEPENDENT AUDITOR'S REPORT")], [],
        [(50, f"To the Members of {co}")], [],
        [(50, f"We have audited the financial statements of {co}, which comprise the balance sheet as at 31 March {cy}")],
        [(50, "and the statement of profit and loss for the year then ended, in accordance with accounting principles")],
        [(50, "generally accepted in India including the Accounting Standards.")], [],
        [(50, f"For {auditor}")], [(50, f"Place: Mumbai | Date: {signed_on}")],
    ]
    bs: list[Row] = [
        [(50, f"BALANCE SHEET AS AT 31 MARCH {cy}")], [],
        [(400, "As at 31 March", "r"), (500, "As at 31 March", "r")],
        [(400, str(cy), "r"), (500, str(py), "r")],
        [(50, "Particulars")],
    ]
    lines = [("(a) Share capital", 5_000_000, 5_000_000), ("(b) Reserves and surplus", 41_200_000, 35_900_000),
             ("(a) Long-term borrowings", borrowings, 19_800_000), ("(a) Short-term borrowings", 12_000_000, 11_000_000),
             ("(a) Trade payables", 14_800_000, 13_900_000), ("(a) Other current liabilities", 3_400_000, 3_100_000),
             ("(a) Short-term provisions", 1_900_000, 1_700_000), ("(a) Inventories", 21_600_000, 20_100_000),
             ("(a) Trade receivables", 31_900_000, 29_400_000), ("(a) Cash and bank balances", cash, 8_200_000),
             ("(a) Short-term loans and advances", 2_100_000, 1_900_000)]
    for label, c, p in lines:
        bs.append([(50, label), (400, inr(c), "r"), (500, inr(p), "r")])
    bs.append([(50, "Net worth"), (400, inr(41_200_000 + 5_000_000), "r"), (500, inr(35_900_000 + 5_000_000), "r")])
    pl: list[Row] = [
        [(50, f"STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED 31 MARCH {cy}")], [],
        [(400, "Year ended 31", "r"), (500, "Year ended 31", "r")],
        [(400, f"March {cy}", "r"), (500, f"March {py}", "r")],
        [(50, "Particulars")],
        [(50, "I. Revenue from operations"), (400, inr(revenue), "r"), (500, inr(prev_rev), "r")],
        [(50, "II. Other income"), (400, inr(int(revenue * 0.004)), "r"), (500, inr(int(prev_rev * 0.004)), "r")],
        [(50, "Depreciation"), (400, inr(int(revenue * 0.02)), "r"), (500, inr(int(prev_rev * 0.02)), "r")],
        [(50, "Finance costs"), (400, inr(int(revenue * 0.012)), "r"), (500, inr(int(prev_rev * 0.012)), "r")],
        [(50, "V. Profit before tax"), (400, inr(profit_before_tax), "r"), (500, inr(prev_pbt), "r")],
        [(50, "VII. Profit for the year"), (400, inr(int(profit_before_tax * 0.75)), "r"), (500, inr(int(prev_pbt * 0.75)), "r")],
        [(50, "EBITDA"), (400, inr(profit_before_tax + int(revenue * 0.032)), "r"), (500, inr(prev_pbt + int(prev_rev * 0.032)), "r")],
    ]
    return build([cover, bs, pl])


# --- the sets ----------------------------------------------------------------------------------------------

STATEMENT_MONTHS = MONTHS                           # April 2025 to September 2026
GST_BY_MONTH = dict(zip(MONTHS, OUTWARD))


def _label(m: tuple[int, int]) -> str:
    return f"{MON[m[1] - 1]}{m[0]}"


def baseline(e: Entity = BASE, *, credits: dict[tuple[int, int], int] | None = None, gst: dict[tuple[int, int], int] | None = None,
             audited_revenue: int | None = None, itr_turnover: int | None = None, emi_months: set | None = None,
             statement_end: tuple[int, int] = (2026, 9), extra_txns: list | None = None) -> dict[str, bytes]:
    """A complete, consistent application set. Keyword arguments change the figures; documents are changed afterwards."""
    gst = gst or GST_BY_MONTH
    months = [m for m in STATEMENT_MONTHS if m <= statement_end]
    credits = credits or {m: GST_BY_MONTH[m] for m in months}
    fy_total = sum(gst[m] for m in MONTHS[:12])
    revenue = audited_revenue if audited_revenue is not None else fy_total
    pbt = int(revenue * 0.09)
    opening = 25_000_000
    txns = statement_transactions(months, credits, opening=opening, emi_months=emi_months, extra=extra_txns)
    first = f"01 {MON[months[0][1] - 1]} {months[0][0]}"
    last_day = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}[months[-1][1]]
    last = f"{last_day} {MON[months[-1][1] - 1]} {months[-1][0]}"
    docs = {
        "01_Certificate_of_Incorporation.pdf": certificate_of_incorporation(e),
        "02_Company_PAN.pdf": company_pan(e),
        "03_Memorandum_of_Association.pdf": memorandum(e),
        "04_Director_KYC_Sathe.pdf": director_kyc(e),
        "05_Board_Resolution.pdf": board_resolution(e),
        "06_Existing_Facilities_Declaration.pdf": facilities_declaration(e),
        "07_Sanction_Letter_Lotuscrest.pdf": sanction_letter(e),
        "08_Commercial_Bureau_Report.pdf": bureau_report(e),
        "09_Bank_Statement_Harbour_CA.pdf": bank_statement(e, txns=txns, opening=opening, start=first, end=last),
        "10_ITR_AY2026-27.pdf": income_tax_return(e, turnover=itr_turnover if itr_turnover is not None else revenue, profit=pbt),
        "11_Audited_Financial_Statements_FY2025-26.pdf": audited_statements(e, revenue=revenue, profit_before_tax=pbt),
        "12_Audited_Financial_Statements_FY2024-25.pdf": audited_statements(e, revenue=int(revenue * 0.91), profit_before_tax=int(pbt * 0.9), fy_end=2025,
                                                                           signed_on="29 August 2025", cash=8_200_000, borrowings=19_800_000),
        "13_ITR_AY2025-26.pdf": income_tax_return(e, turnover=int(revenue * 0.91), profit=int(pbt * 0.9), ay="2025-26", fy="2024-25", filed="30 September 2025"),
    }
    for m in MONTHS:
        docs[f"GSTR3B_{_label(m)}.pdf"] = gstr_3b(e, month=m, taxable=gst[m])
    return docs


@dataclass
class Scenario:
    key: str
    title: str
    plants: str            # what is wrong, in words (kept out of the documents)
    tests: str             # the test-plan items it serves
    expect: str            # what the system should report
    build: object = field(repr=False, default=None)


def _drop(docs: dict[str, bytes], *prefixes: str) -> dict[str, bytes]:
    return {k: v for k, v in docs.items() if not k.startswith(prefixes)}


def s_clean() -> dict[str, bytes]:
    return baseline()


def s_pan() -> dict[str, bytes]:
    d = baseline()
    d["10_ITR_AY2026-27.pdf"] = income_tax_return(BASE, turnover=sum(OUTWARD[:12]), profit=int(sum(OUTWARD[:12]) * 0.09), pan=OTHER_PAN)
    d["08_Commercial_Bureau_Report.pdf"] = bureau_report(pan=OTHER_PAN)
    return d


def s_gstin() -> dict[str, bytes]:
    d = baseline()
    d["06_Existing_Facilities_Declaration.pdf"] = facilities_declaration(gstin=OTHER_GSTIN)
    bad = BASE.gstin[:-1] + ("1" if BASE.gstin[-1] != "1" else "2")
    d["08_Commercial_Bureau_Report.pdf"] = bureau_report(gstin=bad)
    return d


def s_names() -> dict[str, bytes]:
    d = baseline()
    d["02_Company_PAN.pdf"] = company_pan(name="KESTREL FABRICATORS PVT LTD")
    d["GSTR3B_Sep2026.pdf"] = gstr_3b(month=(2026, 9), taxable=GST_BY_MONTH[(2026, 9)], name="Kestrel Fabricators Pvt. Ltd.")
    d["10_ITR_AY2026-27.pdf"] = income_tax_return(turnover=sum(OUTWARD[:12]), profit=int(sum(OUTWARD[:12]) * 0.09), name="Kestrel Engineering Private Limited")
    return d


def s_promoters() -> dict[str, bytes]:
    d = baseline()
    d["04_Director_KYC_Sathe.pdf"] = director_kyc(persons=(BASE.persons[0],))
    d["03_Memorandum_of_Association.pdf"] = memorandum(directors=("Meera Sathe", "Rohan Sathe", "Anil Gokhale"))
    return d


def s_cin() -> dict[str, bytes]:
    d = baseline()
    d["01_Certificate_of_Incorporation.pdf"] = certificate_of_incorporation(cin=OTHER_CIN)
    d["06_Existing_Facilities_Declaration.pdf"] = facilities_declaration(cin=OTHER_CIN[:-1] + "7")
    return d


def s_mislabelled() -> dict[str, bytes]:
    d = baseline()
    fs = d.pop("11_Audited_Financial_Statements_FY2025-26.pdf")
    d["Bank_Statement_Harbour_March2026.pdf"] = fs
    kyc = d.pop("04_Director_KYC_Sathe.pdf")
    d["KYC_Meera_Sathe.pdf"] = director_kyc(persons=(BASE.persons[1],))
    d["KYC_Rohan_Sathe.pdf"] = director_kyc(persons=(BASE.persons[0],))
    return d


def s_out_of_list() -> dict[str, bytes]:
    d = baseline()
    d["Vendor_Invoice_Steelcraft_0457.pdf"] = one_page([
        [(50, "TAX INVOICE")], [], [(50, "Invoice No"), (200, "SC/2026/0457")], [(50, "Date"), (200, "02 October 2026")],
        [(50, "Supplier"), (200, "Steelcraft Metals Private Limited")], [(50, "Bill to"), (200, BASE.name)], [],
        [(50, "Description"), (350, "Quantity", "r"), (450, "Amount", "r")],
        [(50, "Cold rolled steel coil, 2 mm"), (350, "18 MT", "r"), (450, inr(1_260_000), "r")],
        [(50, "Total payable"), (450, inr(1_260_000), "r")]])
    d["Property_Insurance_Schedule.pdf"] = one_page([
        [(50, "PROPERTY INSURANCE POLICY SCHEDULE")], [], [(50, "Policy number"), (200, "PIP/MH/2026/118822")],
        [(50, "Insured"), (200, BASE.name)], [(50, "Period"), (200, "01 July 2026 to 30 June 2027")],
        [(50, "Sum insured"), (200, "Rs. 6,50,00,000")], [(50, "Insurer"), (200, "Zenith General Insurance Limited")]])
    return d


def s_completeness() -> dict[str, bytes]:
    d = baseline(statement_end=(2026, 7))                                   # the statement ends 75 days before the case date
    d = _drop(d, "GSTR3B_Aug2026", "GSTR3B_Sep2026", "07_Sanction", "08_Commercial")   # missing returns, letter and report
    d["05_Board_Resolution.pdf"] = board_resolution(signed=False)           # not executed
    d["06_Existing_Facilities_Declaration.pdf"] = facilities_declaration(signed=False)
    return d


def s_turnover() -> dict[str, bytes]:
    credits = {m: GST_BY_MONTH[m] for m in STATEMENT_MONTHS}
    for m in ((2026, 1), (2026, 2), (2026, 3)):
        credits[m] = int(credits[m] * 0.62)                                 # bank credits well below the returns
    gst = dict(GST_BY_MONTH)
    for m in ((2026, 7), (2026, 8), (2026, 9)):
        gst[m] = int(gst[m] * 1.35)                                         # returns well above the bank
    return baseline(credits=credits, gst=gst, audited_revenue=int(sum(OUTWARD[:12]) * 1.22), itr_turnover=int(sum(OUTWARD[:12]) * 0.8))


def s_accounts() -> dict[str, bytes]:
    d = baseline()
    d["06_Existing_Facilities_Declaration.pdf"] = facilities_declaration(accounts=[
        (BASE.bank, BASE.account, "Current Account"), ("Orchid Cooperative Bank", "118820045511", "Current Account")])
    other = statement_transactions(STATEMENT_MONTHS[-6:], {m: int(GST_BY_MONTH[m] * 0.08) for m in STATEMENT_MONTHS[-6:]}, opening=900_000, emi_months=set())
    d["12_Bank_Statement_Undeclared_Account.pdf"] = bank_statement(
        txns=other, opening=900_000, start="01 Apr 2026", end="30 Sep 2026", account="740030091256", bank="Meridian Trust Bank")
    return d


def s_obligations() -> dict[str, bytes]:
    extra = [((y, m), Txn(f"12 {MON[m - 1]} {y}", "NACH DR VESTA CAPITAL 778811 EMI", f"ACH/VESTA/{m}", debit=96_500)) for (y, m) in STATEMENT_MONTHS]
    d = baseline(extra_txns=extra)
    d["07_Sanction_Letter_Lotuscrest.pdf"] = sanction_letter(emi="1,40,000", amount="2,75,00,000")
    d["08_Commercial_Bureau_Report.pdf"] = bureau_report(facilities=[
        (BASE.lender, "Term Loan", "2,50,00,000", "1,62,50,000", "0", "Standard"),
        ("Orchid Cooperative Bank", "Cash Credit", "75,00,000", "61,00,000", "4,20,000", "Overdue")])
    return d


def s_extraction() -> dict[str, bytes]:
    d = baseline()
    rev = sum(OUTWARD[:12])
    d["10_ITR_AY2026-27.pdf"] = income_tax_return(turnover=rev, profit=int(rev * 0.09), gross=int(rev * 0.07), total=int(rev * 0.09))
    d["GSTR3B_Sep2026.pdf"] = gstr_3b(month=(2026, 9), taxable=GST_BY_MONTH[(2026, 9)], gstin=BASE.gstin[:-1] + "9")
    d["04_Director_KYC_Sathe.pdf"] = director_kyc(persons=(replace(BASE.persons[0], din="0742168"), BASE.persons[1]))
    d["01_Certificate_of_Incorporation.pdf"] = certificate_of_incorporation(date="First day of March Two thousand fifteen")
    return d


def s_bank_mismatches() -> dict[str, bytes]:
    """Everything the cross-checks compare against the bank statements, wrong together."""
    credits = {m: GST_BY_MONTH[m] for m in STATEMENT_MONTHS}
    for m in ((2026, 1), (2026, 2), (2026, 3)):
        credits[m] = int(credits[m] * 0.60)                                 # bank credits far below the returns
    gst = dict(GST_BY_MONTH)
    for m in ((2026, 7), (2026, 8), (2026, 9)):
        gst[m] = int(gst[m] * 1.30)                                         # returns far above the bank
    extra = [((y, m), Txn(f"12 {MON[m - 1]} {y}", "NACH DR VESTA CAPITAL 778811 EMI", f"ACH/VESTA/{m}", debit=96_500)) for (y, m) in STATEMENT_MONTHS]
    d = baseline(credits=credits, gst=gst, audited_revenue=int(sum(OUTWARD[:12]) * 1.15), extra_txns=extra)
    d["06_Existing_Facilities_Declaration.pdf"] = facilities_declaration(accounts=[
        (BASE.bank, BASE.account, "Current Account"), ("Orchid Cooperative Bank", "118820045511", "Current Account")])
    other = statement_transactions(STATEMENT_MONTHS[-6:], {m: int(GST_BY_MONTH[m] * 0.08) for m in STATEMENT_MONTHS[-6:]}, opening=900_000, emi_months=set())
    d["12b_Bank_Statement_Meridian_Trust.pdf"] = bank_statement(
        txns=other, opening=900_000, start="01 Apr 2026", end="30 Sep 2026", account="740030091256", bank="Meridian Trust Bank")
    return d


SCENARIOS = [
    Scenario("K00_clean", "Clean application set", "Nothing: every figure and identifier agrees.",
             "TC-06, TC-11, TC-17, TC-18, TC-19, TC-20", "Every document is typed and filed; no mismatch; turnover agrees across sources; the file is ready for credit.", s_clean),
    Scenario("K01_pan_mismatch", "Entity PAN differs", "The tax return and the bureau report carry another company's PAN.", "TC-22 (ID-01)",
             "ID-01 fails and names the return and the report as the sources that differ.", s_pan),
    Scenario("K02_gstin_mismatch", "GSTIN differs and one is mistyped", "The declaration carries another valid GSTIN; the bureau report's GSTIN has a wrong check character.", "TC-22 (ID-02), TC-17",
             "ID-02 fails; the mistyped GSTIN fails its check-digit validator and goes to review.", s_gstin),
    Scenario("K03_name_variants", "Name spellings", "PVT LTD and Pvt. Ltd. variants (should match) and a different company name on the return.", "TC-22 (ID-03)",
             "The variants match within the name tolerance; the different name is flagged against the return.", s_names),
    Scenario("K04_promoter_set", "Promoter set differs", "KYC for one director only; the memorandum names a third person.", "TC-22 (ID-04, ID-08), TC-12",
             "ID-04 fails; ID-08 reports the director not accounted for; the missing KYC is requested.", s_promoters),
    Scenario("K05_cin", "CIN differs", "The certificate carries another CIN (its year disagrees with the incorporation date) and the declaration a third.", "TC-22 (ID-05, ID-07)",
             "ID-05 fails with all three values; the CIN-year check warns.", s_cin),
    Scenario("K06_mislabelled", "Names that do not match content", "The audited statements are filed as a bank statement; the two directors' KYC sheets are filed under each other's names.", "TC-06, TC-07, TC-08",
             "The statements are typed as audited statements with the mismatch reported; each KYC is attributed to the person it names and flagged.", s_mislabelled),
    Scenario("K07_out_of_list", "Documents outside the list", "A supplier invoice and an insurance schedule are added.", "TC-09",
             "Both are routed for review with suggested types and are not assigned to a checklist item.", s_out_of_list),
    Scenario("K08_completeness", "Missing, incomplete and outdated", "No sanction letter or bureau report; returns for August and September 2026 absent; resolution and declaration unsigned; the statement ends in July.", "TC-12, TC-13, TC-14",
             "Each missing item is requested; the unsigned documents are named as incomplete; the statement and returns are outdated with their dates and permitted age.", s_completeness),
    Scenario("K09_turnover", "Turnover disagrees", "Bank credits 38% below the returns for three months; returns 35% above the bank for three; audited revenue and the return's turnover differ from the returns.", "TC-23 (TO-01 to TO-05, TX-03 to TX-05)",
             "Variances beyond tolerance are flagged with both values and the months; coverage is stated.", s_turnover),
    Scenario("K10_accounts", "Accounts and statements", "A declared account has no statement; a statement is supplied for an account that is not declared.", "TC-24 (BA-01, BA-02)",
             "The declared account without a statement and the undeclared account are both identified.", s_accounts),
    Scenario("K11_obligations", "Obligations", "Instalments every month to a lender that is not declared; the sanction letter's amount and instalment differ from the declaration; the bureau shows a facility the declaration omits.", "TC-25 (OB-01, OB-02)",
             "The undeclared lender's instalments are identified; the declaration, sanction letter and bureau do not reconcile.", s_obligations),
    Scenario("K13_bank_mismatches", "Bank statements disagree on every count", "A declared account has no statement; a statement is supplied for an undeclared account; bank credits are 40% under the returns for three months and returns 30% over for three; audited revenue 15% over the returns; instalments every month to an undeclared lender.", "TC-23, TC-24, TC-25 together (BA-01, BA-02, TO-02, TO-03, TO-05, TX-05, OB-02, OB-03)",
             "Every bank-related check fails or is incomplete, each naming the accounts, months, values and lender.", s_bank_mismatches),
    Scenario("K12_extraction", "Extraction and validators", "Return with total income above gross total income; a GSTIN with a wrong check character; a seven-digit DIN; an incorporation date written in words.", "TC-17, F-15 validators",
             "The figures that fail a validator are marked and sent to review; the date in words is read or reported as unparseable.", s_extraction),
]


def write(out: Path) -> list[tuple[str, int]]:
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    lines = ["# Test document sets (fictional)", "",
             f"Borrower in every set: {BASE.name}. Written for a case date of {REFERENCE}. Nothing in this file is inside a document.", ""]
    for sc in SCENARIOS:
        folder = out / sc.key
        folder.mkdir(exist_ok=True)
        for f in folder.glob("*.pdf"):
            f.unlink()
        docs = sc.build()
        for name, data in docs.items():
            (folder / name).write_bytes(data)
        summary.append((sc.key, len(docs)))
        lines += [f"## {sc.key}: {sc.title}", f"- Files: {len(docs)}", f"- Planted: {sc.plants}", f"- Serves: {sc.tests}",
                  f"- Expect: {sc.expect}", ""]
    (out / "manifest.md").write_text("\n".join(lines))
    return summary


if __name__ == "__main__":
    for key, n in write(Path(sys.argv[1])):
        print(f"{key:24} {n:3} files")
