#!/usr/bin/env python3
"""The test pack for the test plan's sections B to F (TC-03 to TC-25): for each test case a folder holding
pass/ (the condition holds; the app should show the positive outcome) and fail/ (the condition is broken; the app
should flag it), with expected.md saying what the app should show and case.json the appraisal to create for each.

Built on the scenario generator (services/ingestion/tests/docsets.py): one fictional borrower, Kestrel Fabricators
Private Limited, a clean baseline and sets that change one thing each. Every document is drawn by
scripts/realistic_docs.py in the layout of a real document of its kind (the bank's sample documents, or a published
format), swapped into the generator, so the scenarios keep their figures. Written for
a case created in the second half of November 2026: the bank statement and the GST returns run to October 2026
(October's return filed early, on 12 November), so the ages hold until mid-December. Every name, number
and date is fictional; each page carries only the one-line footer; what a set plants is written in expected.md,
never in a document.

    cd services/ingestion && PYTHONPATH=.:<dir holding reportlab> .venv/bin/python ../../scripts/make_test_pack.py ../../workflow/test-pack

Needs reportlab (in the root .venv; the ingestion venv lacks it, so put a directory that holds only a link to the root
venv's reportlab package on PYTHONPATH) and pdftoppm (poppler-utils) for the scanned copies of TC-03 and TC-19.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import realistic_docs as R
from tests import docsets as D

# --- the case date ------------------------------------------------------------------------------------------
# The baseline is written for 14 October 2026; a case created now needs a statement that ends within 45 days.
STATEMENT_THROUGH = (2026, 10)
D.MONTHS = D.MONTHS + [STATEMENT_THROUGH]
D.STATEMENT_MONTHS = D.MONTHS
D.GST_BY_MONTH = {**D.GST_BY_MONTH, STATEMENT_THROUGH: 22_400_000}
D.baseline.__kwdefaults__["statement_end"] = STATEMENT_THROUGH
R.install()                                      # every document in the realistic layout
# The checklist asks, on a case in November, for the twelve returns ending October, though October's is not due until
# 20 November: the pack's October return is filed early, on 12 November, so it is on file and not dated in the future.
_gstr_3b = D.gstr_3b


def _gstr_3b_october_filed_early(e: D.Entity = D.BASE, *, month, taxable, gstin=None, filed_on=None, name=None):
    if month == STATEMENT_THROUGH and filed_on is None:
        filed_on = "12 November 2026"
    return _gstr_3b(e, month=month, taxable=taxable, gstin=gstin, filed_on=filed_on, name=name)


D.gstr_3b = _gstr_3b_october_filed_early
CASE_DATE = "second half of November 2026"

BASE = D.BASE
CASE = {"borrower": BASE.name, "constitution": "private_limited", "facilities": ["cash_credit", "term_loan"],
        "amount_inr": 42_500_000, "channel": "email", "collateral_present": False}
FY_TOTAL = sum(D.OUTWARD[:12])


# --- documents the scenario generator does not make -------------------------------------------------------

def audited(e: D.Entity = BASE, *, revenue: int, profit_before_tax: int, fy_end: int = 2026, reserves: int | None = None,
            prev_reserves: int | None = None, cash: int | None = None, borrowings: int | None = None,
            signed_on: str = "27 August 2026", page_numbers: bool = False, drop_page: int | None = None,
            pl_heading: str = "template") -> bytes:
    """The annual report with the audited statements, with the reserves and the profit free (a loss, a negative net
    worth), optional page numbers, and a page that can be left out (2: the balance sheet, 3: the profit and loss)."""
    return R.annual_report(e, revenue=revenue, profit_before_tax=profit_before_tax, fy_end=fy_end, reserves=reserves,
                           prev_reserves=prev_reserves, cash=cash, borrowings=borrowings, signed_on=signed_on,
                           page_numbers=page_numbers, drop_page=drop_page, pl_heading=pl_heading)


def bureau(e: D.Entity = BASE, *, rank: str = "4") -> bytes:
    """The commercial bureau report with another credit rank."""
    return R.bureau_report(e, rank=rank)


def firm_pan(e: D.Entity, status: str) -> bytes:
    return R.company_pan(e, status=status)


def person_kyc(e: D.Entity, role: str, persons: tuple) -> bytes:
    """KYC of a firm's partners or its proprietor: the bank's summary sheet and the Central KYC form for each, with no DIN."""
    return R.director_kyc(e, persons=persons, role=role)


def cover_letter() -> bytes:
    return R.covering_letter()


# --- the RM's sourcing message (the app's "Sourcing message" document type) ---------------------------------
ENTITIES: dict[str, D.Entity] = {BASE.name: BASE}


def crore(n: int) -> str:
    return f"Rs {n / 10_000_000:.2f} Cr"


def sourcing_message(case: dict) -> str:
    """The RM's email to credit that opens the case, as RMs write it: borrower, identifiers, promoters, declared
    turnover, the requirement, existing banking. The app reads it into the new-appraisal proposal and stores it as the
    case's first document. It states the true position, so a set's planted discrepancies show against it too."""
    e = ENTITIES[case["borrower"]]
    k = R.kind(e)
    amount, facilities = case["amount_inr"], case["facilities"]
    if facilities == ["cash_credit"]:
        need = f"cash credit {crore(amount)}"
    else:
        tl = 12_500_000
        need = f"{crore(amount)}, cash credit {crore(amount - tl)} and term loan {crore(tl)}"
    ids = f"PAN: {e.pan} | GSTIN: {e.gstin}" + (f" | CIN: {e.cin}" if e.cin else "")
    hon = lambda p: "Mrs." if p.name.startswith("Meera") else "Mr."  # noqa: E731
    if k == "company":
        people = f"Promoters: {hon(e.persons[0])} {e.persons[0].name} (MD) and {hon(e.persons[1])} {e.persons[1].name} (Director)"
    elif k == "firm":
        people = f"Partners: {' and '.join(f'{hon(p)} {p.name}' for p in e.persons)}"
    else:
        people = f"Proprietor: {hon(e.persons[0])} {e.persons[0].name}"
    return "\n".join([
        f"Subject: New proposal - {e.name}",
        "",
        "Dear Credit Team,",
        "",
        "Please find below a new proposal sourced at Taloja branch.",
        "",
        f"Borrower: {e.name} ({R.CONSTITUTION[k].lower()})",
        ids,
        people,
        "Business: structural steel fabrication at Taloja MIDC, in business since 2015",
        f"Turnover FY 2025-26: {crore(FY_TOTAL)} (audited)",
        f"Requirement: {need}",
        f"Existing: current account with {e.bank} a/c {e.account} and TL with {e.lender.replace(' Limited', '')}",
        "Collateral: none; primary security by hypothecation of stock, book debts and the machinery financed",
        "",
        "The customer's documents are attached. Request you to initiate the appraisal.",
        "",
        "Regards,",
        "Relationship Manager, Business Banking",
        "Taloja branch",
        "",
    ])


# --- scanned copies (TC-03, TC-19) --------------------------------------------------------------------------

def _pages(pdf: bytes, dpi: int = 300) -> list[Image.Image]:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.pdf"
        src.write_bytes(pdf)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(src), str(Path(tmp) / "p")], check=True)
        return [Image.open(p).convert("RGB") for p in sorted(Path(tmp).glob("p-*.png"))]


def _pdf(images: list[Image.Image], dpi: int) -> bytes:
    out = io.BytesIO()
    images[0].save(out, "PDF", resolution=dpi, save_all=True, append_images=images[1:])
    return out.getvalue()


def scan(pdf: bytes, how: str) -> bytes:
    """An image-only copy of a document: clean at 300 dpi, or damaged in one way the quality gate looks for."""
    pages = _pages(pdf)
    if how == "clean":
        return _pdf(pages, 300)
    if how == "low_resolution":                                   # a 96 dpi scan (the gate wants 150)
        return _pdf([p.resize((p.width * 96 // 300, p.height * 96 // 300), Image.LANCZOS) for p in pages], 96)
    if how == "blurred":
        return _pdf([p.filter(ImageFilter.GaussianBlur(radius=4)) for p in pages], 300)
    if how == "skewed":                                           # photographed at 6 degrees (the gate allows 1.5)
        return _pdf([p.rotate(6, expand=True, fillcolor="white") for p in pages], 300)
    if how == "shadowed":                                         # the left part of the page in shadow
        out = []
        for p in pages:
            shade = Image.new("L", p.size, 255)
            draw = ImageDraw.Draw(shade)
            for x in range(p.width):
                draw.line([(x, 0), (x, p.height)], fill=int(70 + 185 * min(1.0, x / (p.width * 0.6))))
            out.append(Image.composite(p, Image.new("RGB", p.size, "black"), shade))
        return _pdf(out, 300)
    if how == "blank_page":                                       # a blank page in the middle
        return _pdf(pages[:1] + [Image.new("RGB", pages[0].size, "white")] + pages[1:], 300)
    raise ValueError(how)


def damaged(pdf: bytes) -> bytes:
    return pdf[: len(pdf) // 2]                                   # cut off half way: no trailer, no cross-reference


_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")


def _rc4(key: bytes, data: bytes) -> bytes:
    s, j = list(range(256)), 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    out, i, j = bytearray(), 0, 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def password_protected(pages: list) -> bytes:
    """The generator's PDF of these pages, encrypted with the standard security handler (revision 2, 40-bit RC4):
    it opens only with its password. Written here because no PDF library in the environments can encrypt."""
    import hashlib

    user, owner, perms, file_id = b"open-fictional", b"owner-fictional", -44, hashlib.md5(b"kestrel-test-pack").digest()
    pad = lambda pw: (pw + _PAD)[:32]  # noqa: E731
    o = _rc4(hashlib.md5(pad(owner)).digest()[:5], pad(user))
    key = hashlib.md5(pad(user) + o + perms.to_bytes(4, "little", signed=True) + file_id).digest()[:5]
    u = _rc4(key, _PAD)
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
                    x -= D.text_width(text, 10.0)
                ops.append(f"BT /F1 10 Tf {x:.2f} {y:.2f} Td ({D._escape(text)}) Tj ET")
            y -= 16.0
        ops.append(f"BT /F1 7 Tf 50 24 Td ({D._escape(D.FOOTER)}) Tj ET")
        stream = "\n".join(ops).encode("latin-1")
        num = 5 + 2 * i
        stream = _rc4(hashlib.md5(key + num.to_bytes(3, "little") + (0).to_bytes(2, "little")).digest()[:10], stream)
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                        f"/Resources << /Font << /F1 3 0 R >> >> /Contents {num} 0 R >>").encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects.append(f"<< /Filter /Standard /V 1 /R 2 /O <{o.hex()}> /U <{u.hex()}> /P {perms} >>".encode())
    out = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o_:010d} 00000 n \n".encode() for o_ in offsets)
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Encrypt {len(objects)} 0 R "
            f"/ID [<{file_id.hex()}> <{file_id.hex()}>] >>\nstartxref\n{xref}\n%%EOF\n").encode()
    return out


# --- the sets -------------------------------------------------------------------------------------------------

def clean() -> dict[str, bytes]:
    """The baseline, with the third year of audited statements and returns the checklist and DOC-02 ask for."""
    d = D.baseline()
    d["14_Audited_Financial_Statements_FY2023-24.pdf"] = audited(revenue=int(FY_TOTAL * 0.83), profit_before_tax=int(FY_TOTAL * 0.83 * 0.08),
                                                               fy_end=2024, signed_on="30 August 2024")
    d["15_ITR_AY2024-25.pdf"] = D.income_tax_return(turnover=int(FY_TOTAL * 0.83), profit=int(FY_TOTAL * 0.83 * 0.08),
                                                     ay="2024-25", fy="2023-24", filed="30 September 2024")
    for m in D.MONTHS[-12:]:                         # the outward-supply returns for the same twelve months
        d[f"GSTR1_{D._label(m)}.pdf"] = R.gstr_1(month=m, taxable=D.GST_BY_MONTH[m])
    return d


def neutral_names(d: dict[str, bytes]) -> dict[str, bytes]:
    return {f"document-{i:02d}.pdf": v for i, (_, v) in enumerate(sorted(d.items()), 1)}


def scans(how: str) -> dict[str, bytes]:
    return {"Company_PAN.pdf": scan(D.company_pan(), how), "Director_KYC.pdf": scan(D.director_kyc(), how),
            "GSTR3B_Sep2026.pdf": scan(D.gstr_3b(month=(2026, 9), taxable=D.GST_BY_MONTH[(2026, 9)]), how)}


def mislabelled() -> dict[str, bytes]:
    d = clean()
    d["Bank_Statement_Harbour_March2026.pdf"] = d.pop("11_Audited_Financial_Statements_FY2025-26.pdf")
    d["GST_Certificate.pdf"] = d.pop("02_Company_PAN.pdf")
    return d


def kyc_by_person(swapped: bool) -> dict[str, bytes]:
    d = clean()
    d.pop("04_Director_KYC_Sathe.pdf")
    meera, rohan = BASE.persons
    d["KYC_Meera_Sathe.pdf"] = D.director_kyc(persons=(rohan if swapped else meera,))
    d["KYC_Rohan_Sathe.pdf"] = D.director_kyc(persons=(meera if swapped else rohan,))
    return d


def out_of_list() -> dict[str, bytes]:
    d = clean()
    d["Vendor_Invoice_Steelcraft_0457.pdf"] = R.tax_invoice()
    d["Property_Insurance_Schedule.pdf"] = R.insurance_schedule()
    return d


def missing() -> dict[str, bytes]:
    d = clean()
    for k in ("07_Sanction_Letter_Lotuscrest.pdf", "08_Commercial_Bureau_Report.pdf", "04_Director_KYC_Sathe.pdf",
              "12_Audited_Financial_Statements_FY2024-25.pdf", "13_ITR_AY2025-26.pdf"):
        d.pop(k)
    return d


def incomplete() -> dict[str, bytes]:
    d = clean()
    for k in ("GSTR3B_Jul2026.pdf", "GSTR3B_Aug2026.pdf"):                    # two months of returns not given
        d.pop(k)
    d["05_Board_Resolution.pdf"] = D.board_resolution(signed=False)          # not signed
    d["06_Existing_Facilities_Declaration.pdf"] = D.facilities_declaration(signed=False)
    d["11_Audited_Financial_Statements_FY2025-26.pdf"] = audited(revenue=FY_TOTAL, profit_before_tax=int(FY_TOTAL * 0.09),
                                                                page_numbers=True, drop_page=2)   # "Page 2 of 3" absent
    return d


def outdated() -> dict[str, bytes]:
    d = D.baseline(statement_end=(2026, 7))                                  # the statement ends in July (over 45 days)
    for m in ((2026, 6), (2026, 7), (2026, 8), (2026, 9), (2026, 10)):
        d.pop(f"GSTR3B_{D._label(m)}.pdf")                                   # the last return is for May (over 120 days)
    d["05_Board_Resolution.pdf"] = D.board_resolution(date="Thursday, 9 October 2025")   # over a year old
    return d


def firm(constitution: str) -> tuple[D.Entity, dict[str, bytes]]:
    """A partnership firm or a proprietorship: no certificate, memorandum or board resolution; the firm's PAN and
    the partners' or proprietor's KYC; the same financials, returns and statement."""
    if constitution == "partnership":
        e = replace(BASE, name="Kestrel Trading Company", pan="AAAFK1234F", cin="", gstin=D.gstin_with_check("27AAAFK1234F1Z"),
                    incorporated="18 March 2015", persons=(replace(BASE.persons[0], designation="Partner", din=""),
                                                           replace(BASE.persons[1], designation="Partner", din="")))
        status, role = "Firm", "Partner"
    else:
        e = replace(BASE, name="Kestrel Enterprises", pan="ABBPS4321K", cin="",
                    gstin=D.gstin_with_check("27ABBPS4321K1Z"), incorporated="18 March 2015",
                    persons=(replace(BASE.persons[0], designation="Proprietor", din=""),))
        status, role = "Individual", "Proprietor"
    ENTITIES[e.name] = e
    d = {k: v for k, v in D.baseline(e).items() if not k.startswith(("01_", "03_", "04_", "05_", "02_"))}
    d["02_PAN.pdf"] = firm_pan(e, status)
    d[f"04_KYC_{role}s.pdf"] = person_kyc(e, role, e.persons)
    return e, d


def with_third_year(build) -> dict[str, bytes]:
    """A scenario set with the third year of audited statements and returns the clean set has, so that only what the
    scenario plants differs."""
    d = build()
    for k, v in clean().items():
        if k.startswith(("14_", "15_")):
            d.setdefault(k, v)
    return d


def accounts_fail() -> dict[str, bytes]:
    """A declared account with no statement, and a statement for an account that is not declared."""
    d = clean()
    d["06_Existing_Facilities_Declaration.pdf"] = D.facilities_declaration(accounts=[
        (BASE.bank, BASE.account, "Current Account"), ("Orchid Cooperative Bank", "118820045511", "Current Account")])
    other = D.statement_transactions(D.STATEMENT_MONTHS[-12:], {m: int(D.GST_BY_MONTH[m] * 0.08) for m in D.STATEMENT_MONTHS[-12:]},
                                     opening=900_000, emi_months=set())
    d["16_Bank_Statement_Undeclared_Account.pdf"] = D.bank_statement(txns=other, opening=900_000, start="01 Nov 2025",
                                                                     end="31 Oct 2026", account="740030091256",
                                                                     bank="Meridian Trust Bank")
    return d


def gst_fail() -> dict[str, bytes]:
    d = clean()
    for m in ((2026, 2), (2026, 3)):
        d.pop(f"GSTR3B_{D._label(m)}.pdf")                                   # February and March 2026 not given
        d.pop(f"GSTR1_{D._label(m)}.pdf")
    d["GSTR3B_May2026.pdf"] = D.gstr_3b(month=(2026, 5), taxable=D.GST_BY_MONTH[(2026, 5)], filed_on="18 September 2026")  # late
    return d


def two_accounts(declared: bool = True) -> dict[str, bytes]:
    d = clean()
    other = D.statement_transactions(D.STATEMENT_MONTHS[-12:], {m: int(D.GST_BY_MONTH[m] * 0.08) for m in D.STATEMENT_MONTHS[-12:]},
                                     opening=900_000, emi_months=set())
    d["16_Bank_Statement_Orchid_CA.pdf"] = D.bank_statement(txns=other, opening=900_000, start="01 Nov 2025", end="31 Oct 2026",
                                                            account="118820045511", bank="Orchid Cooperative Bank")
    if declared:
        d["06_Existing_Facilities_Declaration.pdf"] = D.facilities_declaration(accounts=[
            (BASE.bank, BASE.account, "Current Account"), ("Orchid Cooperative Bank", "118820045511", "Current Account")])
    return d


def banking_events() -> dict[str, bytes]:
    """Cheque returns, a month heavy in cash and instalments to a lender not declared."""
    extra = []
    for (y, m) in D.STATEMENT_MONTHS[-6:]:
        extra.append(((y, m), D.Txn(f"14 {D.MON[m - 1]} {y}", "NACH DR VESTA CAPITAL 778811 EMI", f"ACH/VESTA/{m}", debit=96_500)))
    for day, amt in ((3, 1_850_000), (9, 1_950_000), (17, 1_900_000)):
        extra.append(((2026, 8), D.Txn(f"{day:02d} Aug 2026", "CASH DEPOSIT BY SELF TALOJA", f"CSH/{day}", credit=amt)))
    for (y, m, day) in ((2026, 6, 21), (2026, 9, 11)):
        extra.append(((y, m), D.Txn(f"{day} {D.MON[m - 1]} {y}", "CHQ RETURN INSUFFICIENT FUNDS 004512", f"RTN/{day}", debit=245_000)))
    d = D.baseline(extra_txns=extra)
    d.update({k: v for k, v in clean().items() if k.startswith(("14_", "15_"))})
    return d


def partner_reports() -> dict[str, bytes]:
    """The partner outputs the bank receives for a case: the commercial bureau report, a GST analytics report and a bank
    statement analysis report (the analytics firm is fictional; the layouts follow published vendor samples)."""
    return {"Commercial_Bureau_Report.pdf": D.bureau_report(), "GST_Analytics_Report_Arcadia.pdf": R.gst_analytics_report(),
            "Bank_Statement_Analysis_Report_Arcadia.pdf": R.bank_statement_analysis()}


def with_collateral_documents(stale: bool) -> dict[str, bytes]:
    """The clean set with the cash credit's stock statement and the works' valuation report, current or stale."""
    d = clean()
    d["17_Stock_Statement.pdf"] = R.stock_statement(as_on="31 July 2026" if stale else "31 October 2026")
    d["18_Valuation_Report_Taloja_Works.pdf"] = R.valuation_report(inspected_on="06 October 2023" if stale else "06 October 2026")
    return d


def firm_with_constitution_documents(constitution: str) -> tuple[D.Entity, dict[str, bytes]]:
    """A firm's set with the documents of its constitution: the partnership deed and the registration of the firm
    (Form A), or the proprietor's business proof (Udyam registration and the shops and establishments certificate)."""
    e, d = firm(constitution)
    d = dict(d)
    if constitution == "partnership":
        d["16_Partnership_Deed.pdf"] = R.partnership_deed(e)
        d["17_Registration_of_Firm_Form_A.pdf"] = R.form_a(e)
    else:
        d["16_Udyam_Registration_Certificate.pdf"] = R.udyam_certificate(e, owner=e.persons[0].name, urn="UDYAM-MH-33-0067812")
        d["17_Shop_and_Establishment_Certificate.pdf"] = R.shop_establishment_certificate(e)
    return e, d


def with_registration_certificates() -> dict[str, bytes]:
    d = clean()
    d["16_GST_Registration_Certificate.pdf"] = R.gst_registration_certificate()
    d["17_Udyam_Registration_Certificate.pdf"] = R.udyam_certificate()
    return d


def with_provisional_statements() -> dict[str, bytes]:
    d = clean()
    d["16_Provisional_Financial_Statements_H1_FY2026-27.pdf"] = R.provisional_financials(revenue=FY_TOTAL, profit_before_tax=int(FY_TOTAL * 0.09))
    return d


def with_statutory_headings() -> dict[str, bytes]:
    """The clean set with the latest statements under the statutory Schedule III headings ("Statement of Profit and Loss
    for the year ended ...") instead of the template's ("Profit & Loss Statement for the period ended ...")."""
    d = clean()
    d["11_Audited_Financial_Statements_FY2025-26.pdf"] = audited(revenue=FY_TOTAL, profit_before_tax=int(FY_TOTAL * 0.09),
                                                                pl_heading="schedule_iii")
    return d


def policy(variant: str) -> tuple[dict, dict[str, bytes]]:
    d = clean()
    case = dict(CASE)
    if variant == "young_company":                                          # EL-01: under three years in business
        e = replace(BASE, incorporated="14 June 2024", cin="U28999MH2024PTC345678")
        d["01_Certificate_of_Incorporation.pdf"] = D.certificate_of_incorporation(e)
        d["02_Company_PAN.pdf"] = D.company_pan(e)
    elif variant == "bureau_rank":                                          # EL-02: a rank worse than 6
        d["08_Commercial_Bureau_Report.pdf"] = bureau(rank="8")
    elif variant == "negative_net_worth":                                   # EL-03
        d["11_Audited_Financial_Statements_FY2025-26.pdf"] = audited(revenue=FY_TOTAL, profit_before_tax=int(FY_TOTAL * 0.09),
                                                                    reserves=-9_800_000)
    elif variant == "loss_latest_year":                                     # EL-04
        d["11_Audited_Financial_Statements_FY2025-26.pdf"] = audited(revenue=FY_TOTAL, profit_before_tax=-6_400_000)
        d["10_ITR_AY2026-27.pdf"] = D.income_tax_return(turnover=FY_TOTAL, profit=-6_400_000)
    elif variant == "request_above_turnover_share":                         # EL-05: over 20% of turnover
        case["amount_inr"] = 49_500_000      # above 20% of 24.16 crore, within the turnover method's 5 crore
    elif variant == "two_years_of_statements":                              # DOC-02: fewer than three years
        d.pop("14_Audited_Financial_Statements_FY2023-24.pdf")
    return case, d


# --- the test cases -------------------------------------------------------------------------------------------
# Each: id, section, folder name, title, {subfolder: (case, documents)}, and what the app should show.

def tc(id_, section, slug, title, sets, expect, gaps=""):
    return {"id": id_, "section": section, "slug": slug, "title": title, "sets": sets, "expect": expect, "gaps": gaps}


def build_cases() -> list[dict]:
    partnership, proprietorship = firm("partnership"), firm("proprietorship")
    partnership_docs, proprietorship_docs = (firm_with_constitution_documents("partnership"),
                                             firm_with_constitution_documents("proprietorship"))
    cases = [
        tc("TC-03", "B", "poor-quality-documents", "Poor quality documents",
           {"pass": (CASE, scans("clean")),
            "fail": (CASE, {**{f"LowResolution_{k}": v for k, v in scans("low_resolution").items() if k.startswith("Company")},
                            **{f"Blurred_{k}": v for k, v in scans("blurred").items() if k.startswith("Director")},
                            **{f"Skewed_{k}": v for k, v in scans("skewed").items() if k.startswith("GSTR")},
                            "Shadowed_Company_PAN.pdf": scan(D.company_pan(), "shadowed"),
                            "BlankPage_Director_KYC.pdf": scan(D.director_kyc(), "blank_page"),
                            "Damaged_Sanction_Letter.pdf": damaged(D.sanction_letter()),
                            "Password_Cover_Letter.pdf": password_protected([[[(50, "Covering letter")], [(50, "Please find enclosed the documents asked for.")]]])})},
           {"pass": "Three clean 300 dpi scans (image only): read by OCR, no quality flag.",
            "fail": "Each file flagged with its reason and a re-scan request: low resolution, blurred, skewed, in shadow, a blank "
                    "page, damaged, password-protected."}),
        tc("TC-04", "B", "classification-by-content", "Classification by content",
           {"pass": (CASE, neutral_names(clean())),
            "fail": (CASE, {"Covering_Letter.pdf": cover_letter()})},
           {"pass": "Every file named document-NN.pdf, yet each is identified by type from its content and mapped to its "
                    "checklist item.",
            "fail": "A covering letter that names no document: not identified, routed for a person to classify, never "
                    "assigned a type."}),
        tc("TC-05", "B", "mislabelled-file", "Mislabelled file",
           {"pass": (CASE, None), "fail": (CASE, mislabelled())},
           {"pass": "File names agree with their content: no label mismatch.",
            "fail": "Audited statements named as a bank statement, and the company PAN named as a GST certificate: each read "
                    "as what it is, and the mismatch with its name reported."}),
        tc("TC-06", "B", "document-attributed-to-wrong-person", "Document attributed to the wrong person",
           {"pass": (CASE, kyc_by_person(False)), "fail": (CASE, kyc_by_person(True))},
           {"pass": "Each director's KYC filed under that director's name.",
            "fail": "The two directors' KYC sheets filed under each other's names: each attributed to the person it is about, "
                    "and the attribution flagged."}),
        tc("TC-07", "B", "unrecognised-document", "Unrecognised document",
           {"pass": (CASE, None), "fail": (CASE, out_of_list())},
           {"pass": "Only checklist documents: nothing routed for classification.",
            "fail": "A supplier invoice and an insurance schedule added: each routed for a person to classify, with suggested "
                    "types, and neither assigned to a checklist item."}),
        tc("TC-08", "B", "partner-outputs", "Partner outputs",
           {"pass": (CASE, {"Commercial_Bureau_Report.pdf": D.bureau_report()}),
            "partner-reports": (CASE, partner_reports())},
           {"pass": "The commercial bureau report recognised and its key fields read (rank, facilities, related parties).",
            "partner-reports": "The bureau report, a GST analytics report and a bank statement analysis report: each recognised "
                               "as the partner's report it is (not as a GSTR-3B or a bank statement), and its figures "
                               "(turnover by month, filing delays; credits, EMIs, returns by month) available to compare."},
           gaps="The GST analytics and bank statement analysis reports (partner-reports/) follow published vendor samples, "
                "from a fictional analytics firm: the app has no document type for either. Needed: RBL's partners' own "
                "report samples."),
        tc("TC-09", "C", "complete-file", "Complete file",
           {"pass": (CASE, None), "fail": (CASE, D.s_completeness())},
           {"pass": "Every checklist item satisfied; the readiness gate met; ready for credit.",
            "fail": "Items missing, incomplete and outdated: not ready, with each blocker named."}),
        tc("TC-10", "C", "missing-documents", "Missing documents",
           {"pass": (CASE, None), "fail": (CASE, missing())},
           {"pass": "Nothing missing.",
            "fail": "No sanction letter, bureau report, director KYC, audited statements for FY2024-25 or return for AY2025-26: "
                    "each missing item identified with a specific request."}),
        tc("TC-11", "C", "incomplete-documents", "Incomplete documents",
           {"pass": (CASE, None), "fail": (CASE, incomplete())},
           {"pass": "Every document complete.",
            "fail": "GST returns for July and August 2026 absent (a partial period), the board resolution and the facilities "
                    "declaration unsigned, and the FY2025-26 audited statements without their page 2 of 3: each identified as "
                    "insufficient with its deficiency."}),
        tc("TC-12", "C", "outdated-documents", "Outdated documents",
           {"pass": (CASE, None), "fail": (CASE, outdated()),
            "pass-stock-and-valuation": (CASE, with_collateral_documents(stale=False)),
            "fail-stock-and-valuation": (CASE, with_collateral_documents(stale=True))},
           {"pass": "Every dated document within its permitted age.",
            "pass-stock-and-valuation": "A stock statement as on 31 October 2026 and a valuation report of 6 October 2026: "
                                        "both recognised and within their permitted ages.",
            "fail-stock-and-valuation": "A stock statement as on 31 July 2026 and a valuation report of 6 October 2023: each "
                                        "identified as outdated with its date and the permitted age.",
            "fail": "The bank statement ends in July 2026 (more than 45 days before the case), the last GST return is for May "
                    "2026 (more than 120 days), the board resolution is from October 2025 (more than a year): each identified "
                    "as outdated with its date and the permitted age."},
           gaps="The stock statement and the valuation report (the *-stock-and-valuation sets; the valuation report in a "
                "bank's Appendix-I format) have no document type or age rule in the app. Needed: RBL's permitted age for "
                "each."),
        tc("TC-13", "C", "checklist-by-constitution", "Checklist by constitution and product",
           {"private-limited": (CASE, None),
            "partnership": ({**CASE, "borrower": partnership[0].name, "constitution": "partnership"}, partnership[1]),
            "proprietorship": ({**CASE, "borrower": proprietorship[0].name, "constitution": "proprietorship"},
                               proprietorship[1]),
            "partnership-with-deed": ({**CASE, "borrower": partnership_docs[0].name, "constitution": "partnership"},
                                      partnership_docs[1]),
            "proprietorship-with-business-proof": ({**CASE, "borrower": proprietorship_docs[0].name,
                                                    "constitution": "proprietorship"}, proprietorship_docs[1])},
           {"private-limited": "The company checklist: certificate, memorandum, board resolution, entity PAN, directors' KYC, "
                               "financials, returns, statements.",
            "partnership": "The firm checklist: no certificate, memorandum or board resolution asked for; the partners' KYC is.",
            "proprietorship": "The proprietorship checklist: no certificate, memorandum or board resolution; the proprietor's KYC.",
            "partnership-with-deed": "The firm checklist with its constitution documents: the partnership deed and the "
                                     "registration of firm (Form A) recognised and mapped.",
            "proprietorship-with-business-proof": "The proprietorship checklist with the business proof: the Udyam "
                                                  "registration and the shops and establishments certificate recognised and mapped."},
           gaps="The partnership deed, Form A, Udyam certificate and shops and establishments certificate are in the *-with-* "
                "sets; the checklist does not ask for them and the app has no document type for them."),
        tc("TC-14", "C", "consolidated-query-list", "Consolidated pre-login query list",
           {"pass": (CASE, None), "fail": (CASE, D.s_completeness())},
           {"pass": "No query: nothing to ask the customer.",
            "fail": "One list, in plain language for the RM, of every document and clarification needed."}),
        tc("TC-15", "D", "identity-and-registration", "Identity and registration",
           {"pass": (CASE, None), "fail": (CASE, with_third_year(D.s_extraction)),
            "registration-certificates": (CASE, with_registration_certificates())},
           {"pass": "CIN, PAN, GSTIN, company name, incorporation date (in words, as the MCA prints it) and the directors "
                    "(names, DINs) read with their pages.",
            "fail": "A GSTIN with a wrong check character, a seven-digit DIN, a certificate whose incorporation date reads 1 "
                    "March 2015 against the PAN's 18 March 2015, and a return whose total income exceeds its gross total "
                    "income: each value flagged.",
            "registration-certificates": "The GST registration certificate (REG-06) and the Udyam certificate added: GSTIN, "
                                         "legal name, constitution and date of liability, and the Udyam number and enterprise "
                                         "type, read and agreeing with the other documents."},
           gaps="The GST registration certificate and the Udyam certificate (registration-certificates/) have no document "
                "type in the app."),
        tc("TC-16", "D", "financial-statements-and-spread", "Financial statements and spread",
           {"pass": (CASE, None),
            "fail": (CASE, {**clean(), "11_Audited_Financial_Statements_FY2025-26.pdf": audited(
                revenue=FY_TOTAL, profit_before_tax=int(FY_TOTAL * 0.09), page_numbers=True, drop_page=3)}),
            "pass-statutory-headings": (CASE, with_statutory_headings()),
            "provisional-statements": (CASE, with_provisional_statements())},
           {"pass": "Three years of audited statements: the profit and loss and balance sheet items read for each year and "
                    "the spread populated.",
            "fail": "The latest year's statements without the profit and loss page: its items reported not found, and the "
                    "spread's latest year marked incomplete.",
            "pass-statutory-headings": "The latest statements under the statutory Schedule III headings (\"Statement of Profit "
                                       "and Loss for the year ended\", a Notes column) read with the same figures as the "
                                       "template's headings.",
            "provisional-statements": "Provisional statements for the half year to 30 September 2026, under a chartered "
                                      "accountant's compilation certificate, added: recognised as provisional, kept apart "
                                      "from the audited years, their figures read."},
           gaps="The provisional statements (provisional-statements/) have no document type in the app. Needed: RBL's spread "
                "format if it differs from the app's."),
        tc("TC-17", "D", "gst", "GST",
           {"pass": (CASE, None), "fail": (CASE, gst_fail())},
           {"pass": "Turnover and filing date read for every month from November 2025 to October 2026.",
            "fail": "Returns for February and March 2026 absent, and May 2026's filed late: the missing periods identified "
                    "and the filing date read."},
           gaps="No partner GST report here (see TC-08 partner-reports/). The pack's GSTR-1 builder exists but no set "
                "uses it yet."),
        tc("TC-18", "D", "banking", "Banking",
           {"pass": (CASE, two_accounts()), "fail": (CASE, banking_events())},
           {"pass": "Two declared accounts, each with its statement: credits, debits and balances by account and month.",
            "fail": "Instalments every month to a lender not declared, three large cash deposits in August 2026 and two cheque "
                    "returns: each found by month."},
           gaps="No bank statement analysis report from RBL's partner (see TC-08)."),
        tc("TC-19", "D", "confidence-and-evidence", "Confidence and evidence",
           {"pass": (CASE, None),
            "fail": (CASE, {**clean(), "04_Director_KYC_Sathe.pdf": scan(D.director_kyc(), "blurred"),
                            "01_Certificate_of_Incorporation.pdf": D.certificate_of_incorporation(date="First day of March Two thousand fifteen")})},
           {"pass": "Every field carries a confidence and a link to its page.",
            "fail": "A blurred scan of the directors' KYC, and a certificate whose incorporation date (in words) disagrees "
                    "with the PAN's: their fields carry low confidence and are routed for review."}),
        tc("TC-20", "E", "identity-consistency", "Identity consistency",
           {"pass": (CASE, None),
            "fail-pan": (CASE, with_third_year(D.s_pan)), "fail-gstin": (CASE, with_third_year(D.s_gstin)),
            "fail-names": (CASE, with_third_year(D.s_names)), "fail-promoters": (CASE, with_third_year(D.s_promoters)),
            "fail-cin": (CASE, with_third_year(D.s_cin))},
           {"pass": "Every identifier agrees: no identity finding.",
            "fail-pan": "The return and the bureau report carry another company's PAN: ID-01 with both sources.",
            "fail-gstin": "The declaration carries another GSTIN and the bureau report one with a wrong check character: ID-02.",
            "fail-names": "PVT LTD and Pvt. Ltd. variants match; the return's different company name does not: ID-03.",
            "fail-promoters": "KYC for one director only and a third person in the memorandum: ID-04 and ID-08.",
            "fail-cin": "The certificate and the declaration carry other CINs: ID-05 and ID-07."}),
        tc("TC-21", "E", "turnover", "Turnover",
           {"pass": (CASE, None), "fail": (CASE, with_third_year(D.s_turnover))},
           {"pass": "Audited revenue, the returns, the tax return and bank credits agree within tolerance.",
            "fail": "Bank credits 38% under the returns for three months, returns 35% over the bank for three, audited "
                    "revenue and the return's turnover off the returns: TO-01 to TO-05 and TX-03 to TX-05 with values."}),
        tc("TC-22", "E", "bank-accounts", "Bank accounts",
           {"pass": (CASE, None), "fail": (CASE, accounts_fail())},
           {"pass": "Every declared account has its statement; no statement for an undeclared account.",
            "fail": "A declared account without a statement, and a statement for an account not declared: BA-01 and BA-02."}),
        tc("TC-23", "E", "existing-obligations", "Existing obligations",
           {"pass": (CASE, None), "fail": (CASE, with_third_year(D.s_obligations))},
           {"pass": "Declared facilities, the sanction letter, the bureau report and the instalments agree.",
            "fail": "Instalments every month to a lender not declared, the sanction letter's amount and instalment off the "
                    "declaration, and a facility in the bureau report the declaration omits: OB-01 to OB-03."}),
        tc("TC-24", "F", "policy-norms-and-deviations", "Policy norms and deviations",
           {"pass": policy("none"),
            **{f"fail-{v.replace('_', '-')}": policy(v) for v in ("young_company", "bureau_rank", "negative_net_worth",
                                                                 "loss_latest_year", "request_above_turnover_share",
                                                                 "two_years_of_statements")}},
           {"pass": "Every norm met: no deviation.",
            "fail-young-company": "Incorporated in June 2024: EL-01 business vintage under three years.",
            "fail-bureau-rank": "Commercial bureau rank 8: EL-02 worse than 6.",
            "fail-negative-net-worth": "Reserves of minus 98 lakh against 50 lakh capital: EL-03 net worth not positive.",
            "fail-loss-latest-year": "A loss before tax of 64 lakh in FY2025-26: EL-04.",
            "fail-request-above-turnover-share": "4.95 crore asked against 24.16 crore turnover (20.5%): EL-05 above 20% "
                                                 "(the norm applies to the turnover method, requests up to 5 crore).",
            "fail-two-years-of-statements": "Audited statements for two years only: DOC-02 under three years."},
           gaps="The norms are the app's provisional set. Needed: RBL's Business Banking policy norms and its deviation "
                "record for the case set."),
        tc("TC-25", "F", "approving-authority", "Approving authority",
           {"pass": ({**CASE, "amount_inr": 18_000_000, "facilities": ["cash_credit"]}, None),
            "regional-credit-head": ({**CASE, "amount_inr": 42_500_000, "facilities": ["cash_credit"]}, None),
            "zonal-credit-committee": ({**CASE, "amount_inr": 120_000_000, "facilities": ["cash_credit"]}, None)},
           {"pass": "1.8 crore cash credit: the Credit Officer.",
            "regional-credit-head": "4.25 crore cash credit: the Regional Credit Head.",
            "zonal-credit-committee": "12 crore cash credit: the Zonal Credit Committee."},
           gaps="The approval matrix is the app's provisional one, and comparing with the recorded approval needs RBL's "
                "record. Needed: RBL's approval matrix and the recorded approval for each case."),
    ]
    return cases


def write(out: Path) -> list[dict]:
    for old in ("B", "C", "D", "E", "F"):              # the sets are rebuilt; README.md and RESULTS.md are kept
        if (out / old).exists():
            shutil.rmtree(out / old)
    clean_docs = clean()
    cases = build_cases()
    index = []
    for c in cases:
        tc_dir = out / f"{c['section']}" / f"{c['id']}-{c['slug']}"
        lines = [f"# {c['id']}: {c['title']}", "", f"Written for a case created in the {CASE_DATE}. Every name and number "
                 "is fictional.", ""]
        for name, (case, docs) in c["sets"].items():
            folder = tc_dir / name
            folder.mkdir(parents=True)
            for fname, data in sorted((docs if docs is not None else clean_docs).items()):
                (folder / fname).write_bytes(data)
            message = sourcing_message(case)
            (folder / "00_Sourcing_Message.txt").write_text(message)
            (folder / "case.json").write_text(json.dumps({**case, "message_text": message}, indent=1) + "\n")
            lines += [f"## {name}/", "", c["expect"][name], "",
                      f"Create the appraisal by pasting 00_Sourcing_Message.txt on the New appraisal screen (channel: email) "
                      f"and confirming: {case['borrower']}, {case['constitution'].replace('_', ' ')}, "
                      f"{', '.join(f.replace('_', ' ') for f in case['facilities'])}, Rs. {case['amount_inr']:,}; then upload "
                      f"every PDF in the folder.", ""]
            index.append({"id": c["id"], "section": c["section"], "set": name, "folder": str(folder.relative_to(out)),
                          "files": len(list(folder.glob("*.pdf"))), "expect": c["expect"][name]})
        if c["gaps"]:
            lines += ["## Not covered yet", "", c["gaps"], ""]
        (tc_dir / "expected.md").write_text("\n".join(lines))
    (out / "index.json").write_text(json.dumps({"case_date": CASE_DATE, "sets": index,
                                               "gaps": {c["id"]: c["gaps"] for c in cases if c["gaps"]}}, indent=1))
    return index


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    index = write(out)
    print(f"{len(index)} sets in {len({i['id'] for i in index})} test cases written to {out}")
