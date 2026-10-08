"""Build the synthetic test files and their canned results from the document-processing service.

    .venv/bin/python -m tests.fixtures.build_fixtures

Writes tests/fixtures/files/<name> (small PDFs, deterministic bytes, one document type per file as
the service reads them) and tests/fixtures/ingest/<sha256>.json (an IngestFileResult in contract
version 2, validated against the contract) for the StubIngestClient. A file the person assigned a
type to has `<sha256>@<type_id>.json`. All names are fictional; every date is relative to the fixed
test as_of, 2026-09-29. The statement rows use the labels printed in audited statements so the
configured line mappings (config/statements.yaml) are exercised.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.contracts.ingest import IngestFileResult
from engine.identifiers import build_gstin
from tests.fixtures.pdfgen import make_pdf

HERE = Path(__file__).resolve().parent
FILES = HERE / "files"
INGEST = HERE / "ingest"

AS_OF = "2026-09-29"
COMPS = {"classification": 1.0, "page_grade": 1.0, "reading_trust": 1.0, "validation": 1.0, "agreement": 0.8}

TARUN = {"name": "Tarun Velankar", "pan": "ABCPV1234K", "din": "01234567", "dob": "1978-04-02"}
ISHITA = {"name": "Ishita Barve", "pan": "ABCPB5678M", "din": "07654321", "dob": "1981-11-19"}
SUNIL = {"name": "Sunil Karve", "pan": "ABCPK9012L", "din": "09123456", "dob": "1975-01-30"}

KESTREL = {"name": "Kestrel Fabricators Private Limited", "pan": "AAACK1234F", "cin": "U28999MH2015PTC123456"}
HERONBAY = {"name": "Heronbay Polymers Private Limited", "pan": "AAACH5678Q", "cin": "U25209MH2012PTC654321"}
GST_WINDOW = [f"{y}-{m:02d}" for y, m in [(2025, 9), (2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 9)]]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]

W, H = 595.0, 842.0


def bbox(n: int = 0) -> list[float]:
    return [50.0, 100.0 + 15 * n, 300.0, 112.0 + 15 * n]


def source(page: int, text: str = "") -> dict:
    return {"kind": "page", "page": page, "text": text, "bbox": bbox(), "sheet": None, "range": None}


def fld(value, *, page: int = 1, raw: str | None = None, conf: float = 0.96, method: str = "pattern", required: bool = False,
        needs_review: bool = False, comps: dict | None = None) -> dict:
    if value is None:
        return {"status": "missing", "reason": "not_found", "value": None, "raw_text": None, "method": None, "confidence": 0.0,
                "components": {}, "source": None, "required": required, "key_field": required, "needs_review": False}
    return {"status": "found", "reason": None, "value": value, "raw_text": raw if raw is not None else str(value), "method": method,
            "confidence": conf, "components": dict(comps if comps is not None else COMPS), "source": source(page, str(value)[:60]),
            "required": required, "key_field": required, "needs_review": needs_review}


def table(columns: list[str], rows: list[dict], page: int = 1, conf: float = 0.96) -> dict:
    return {
        "status": "found", "reason": None, "columns": columns, "repairs": [], "unparsed": 0, "confidence": conf,
        "source": {"page_start": page, "page_end": page, "bbox": [50.0, 100.0, 545.0, 100.0 + 15 * len(rows)]},
        "rows": [{"cells": {c: r.get(c) for c in columns}, "raw": {c: str(r[c]) for c in columns if r.get(c) is not None},
                  "source": {"page": page, "bbox": bbox(i), "line_ids": [f"p{page}.l{i + 1}"]}} for i, r in enumerate(rows)],
    }


def document(type_id: str, fields: dict, *, tables: dict | None = None, instance_key: str | None = None, identity: dict | None = None,
             defects: list[dict] | None = None, n: int = 1, pages: tuple[int, int] = (1, 1), decision: str = "auto_accept") -> dict:
    return {
        "instance_no": n, "instance_key": instance_key, "page_from": pages[0], "page_to": pages[1], "document_type": type_id,
        "fields": fields, "tables": tables or {}, "validation": [],
        "confidence": {"document": 0.96, "decision": decision, "reasons": [], "composition": {}},
        "identity": identity or {}, "defects": defects or [],
    }


def page_info(n: int, grade: str = "A", reasons: tuple[str, ...] = (), source_kind: str = "text_layer") -> dict:
    return {"page": n, "source": source_kind, "width": W, "height": H, "grade": grade, "reasons": list(reasons),
            "reading_trust": 1.0 if grade == "A" else 0.4, "ocr_conf": None, "sheet": None, "blank": False, "words": 40}


class File:
    """One PDF holding one kind of document (one or more instances)."""

    def __init__(self, name: str, type_id: str | None, *, confidence: float = 0.95, candidates: list[tuple[str, float]] | None = None) -> None:
        self.name, self.type_id = name, type_id
        self.pages: list[str] = []
        self.documents: list[dict] = []
        self.page_infos: list[dict] = []
        self.confidence, self.candidates = confidence, candidates or []

    def page(self, text: str, grade: str = "A", reasons: tuple[str, ...] = ()) -> int:
        self.pages.append(text)
        self.page_infos.append(page_info(len(self.pages), grade, reasons))
        return len(self.pages)

    def add(self, text: str, doc_type: str, fields: dict, *, grade: str = "A", reasons: tuple[str, ...] = (), **kw) -> None:
        n = self.page(text, grade, reasons)
        fields = {k: _on_page(v, n) for k, v in fields.items()}
        tables = {k: _table_on_page(v, n) for k, v in (kw.pop("tables", None) or {}).items()}
        self.documents.append(document(doc_type, fields, tables=tables, n=len(self.documents) + 1, pages=(n, n), **kw))

    def result(self, sha: str) -> dict:
        cls = {
            "type": self.type_id, "confidence": self.confidence if self.type_id else 0.41, "tier": "signals" if self.type_id else "none",
            "signals": {"required": ["fixture"], "supporting": [], "contrary": []} if self.type_id else {},
            "candidates": [{"type": t, "score": s} for t, s in (self.candidates or ([(self.type_id, self.confidence)] if self.type_id else []))][:3],
            "needs_review": not self.type_id, "reason": None, "mixed_content": [], "model_error": None,
        }
        decisions = {d["confidence"]["decision"] for d in self.documents}
        return {
            "file_id": "fixture", "sha256": sha, "name": self.name, "status": "processed", "reject": None, "error": None,
            "run_id": "RUN-FIXTURE", "source": {"kind": "pdf", "pages": len(self.pages)}, "grade": "A", "route": {}, "pages": self.page_infos,
            "front_matter_pages": [], "classification": cls, "documents": self.documents,
            "decision": "human_review" if (not self.type_id or "human_review" in decisions) else "auto_accept",
            "review_reasons": [], "trace": [],
        }

    def write(self, *, overrides: dict[str, dict] | None = None) -> str:
        data = make_pdf(self.pages)
        sha = hashlib.sha256(data).hexdigest()
        FILES.mkdir(parents=True, exist_ok=True)
        INGEST.mkdir(parents=True, exist_ok=True)
        (FILES / self.name).write_bytes(data)
        _write(INGEST / f"{sha}.json", self.result(sha))
        for type_id, result in (overrides or {}).items():
            _write(INGEST / f"{sha}@{type_id}.json", {**result, "sha256": sha, "name": self.name})
        return sha


def _on_page(f: dict, n: int) -> dict:
    if f.get("source"):
        f = {**f, "source": {**f["source"], "page": n}}
    return f


def _table_on_page(t: dict, n: int) -> dict:
    t = json.loads(json.dumps(t))
    if t.get("source") and "page_start" in t["source"]:
        t["source"]["page_start"] = t["source"]["page_end"] = n
    for r in t["rows"]:
        r["source"]["page"] = n
    return t


def _write(path: Path, result: dict) -> None:
    IngestFileResult.model_validate(result)  # the contract (contract version 2)
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# --- Documents ---


def statement_tables(year_end: str, *, scale: float = 1.0, previous_scale: float = 0.85) -> dict:
    """Balance sheet and profit and loss as printed: label rows with the current and previous year."""
    def row(label, value):
        return {"particulars": label, "current_period": None if value is None else round(value * scale),
                "previous_period": None if value is None else round(value * previous_scale)}

    pl = [row("I. Revenue from operations", 118_000_000), row("II. Other income", 1_000_000),
          row("III. Total income (I + II)", 119_000_000), row("IV. Expenses:", None),
          row("Cost of materials consumed", 80_000_000), row("Employee benefits expense", 12_000_000),
          row("Finance costs", 3_500_000), row("Depreciation and amortisation", 4_000_000), row("Other expenses", 12_000_000),
          row("Total expenses", 111_500_000), row("V. Profit before tax (III - IV)", 7_500_000),
          row("VI. Tax expense (current and deferred)", 1_100_000), row("VII. Profit for the year (V - VI)", 6_400_000)]
    bs = [row("I. EQUITY AND LIABILITIES", None), row("(1) Shareholders' funds", None), row("(a) Share capital", 10_000_000),
          row("(b) Reserves and surplus", 32_000_000), row("(2) Non-current liabilities", None),
          row("(a) Long-term borrowings", 15_000_000), row("(3) Current liabilities", None),
          row("(a) Short-term borrowings", 12_000_000), row("(b) Trade payables", 20_000_000),
          row("(c) Other current liabilities", 3_000_000), row("(d) Short-term provisions", 2_000_000),
          row("TOTAL", 94_000_000), row("II. ASSETS", None), row("(1) Non-current assets", None),
          row("(a) Property, plant and equipment", 35_000_000), row("(2) Current assets", None),
          row("(a) Inventories", 25_000_000), row("(b) Trade receivables", 24_000_000),
          row("(c) Cash and bank balances", 6_000_000), row("(d) Short-term loans and advances", 4_000_000),
          row("TOTAL", 94_000_000)]
    cols = ["particulars", "current_period", "previous_period"]
    return {"profit_and_loss": table(cols, pl), "balance_sheet": table(cols, bs)}


def coi(f: File, entity: dict) -> None:
    f.add(f"CERTIFICATE OF INCORPORATION\n{entity['name']}\nCorporate Identity Number {entity['cin']}", "certificate_of_incorporation",
          {"company_name": fld(entity["name"], required=True), "cin": fld(entity["cin"], method="identifier", required=True),
           "date_of_incorporation": fld("2015-06-12", required=True), "company_type": fld("Company limited by shares"),
           "registered_address": fld("Plot 7, Industrial Estate, Pune 411019"), "roc": fld("Registrar of Companies, Pune")},
          identity={"name": entity["name"], "cin": entity["cin"]})


def moa(f: File, entity: dict, directors: list[dict]) -> None:
    f.add(f"MEMORANDUM OF ASSOCIATION OF {entity['name']}\nObjects clause", "memorandum_articles_of_association",
          {"company_name": fld(entity["name"], required=True), "cin": fld(None), "registered_office": fld("Maharashtra"),
           "authorized_share_capital": fld(15_000_000), "paid_up_share_capital": fld(10_000_000),
           "objects_of_company": fld("To manufacture fabricated metal products"),
           "directors": fld([{"name": d["name"], "din": d.get("din")} for d in directors])},
          tables={"shareholding": table(["shareholder_name", "number_of_shares", "shareholding_percentage"],
                                        [{"shareholder_name": d["name"], "number_of_shares": 500_000} for d in directors])},
          identity={"name": entity["name"]})


def board_resolution(f: File, entity: dict, *, signed: bool) -> None:
    f.add(f"CERTIFIED TRUE COPY OF THE RESOLUTION OF THE BOARD OF DIRECTORS\n{entity['name']}\nRESOLVED THAT the company do borrow",
          "board_resolution_borrowing",
          {"company_name": fld(entity["name"], required=True), "resolution_date": fld("2026-09-01", required=True),
           "meeting_date": fld("2026-09-01"), "resolution_number": fld(None), "borrowing_limit": fld(65_000_000),
           "lender_name": fld("RBL Bank"), "purpose_of_borrowing": fld("Working capital"),
           "authorized_persons": fld([TARUN["name"], ISHITA["name"]]), "authorized_signatories": fld([TARUN["name"]])},
          identity={"name": entity["name"]}, defects=[] if signed else [{"code": "unsigned", "detail": "signature block blank", "pages": [1]}])


def company_pan(f: File, entity: dict) -> None:
    f.add(f"INTIMATION OF ALLOTMENT OF PERMANENT ACCOUNT NUMBER\n{entity['name']}\n{entity['pan']}", "company_pan",
          {"company_name": fld(entity["name"], required=True), "pan": fld(entity["pan"], method="identifier", required=True),
           "date_of_issue": fld("2015-06-20")},
          identity={"name": entity["name"], "pan": entity["pan"]})


def director_kyc(f: File, person: dict, text_extra: str = "", *, grade: str = "A", reasons: tuple[str, ...] = ()) -> None:
    f.add(f"DIRECTOR KYC SUMMARY SHEET\nName of Director {person['name']}\nPAN {person['pan']} {text_extra}", "director_kyc",
          {"person_name": fld(person["name"], required=True), "din": fld(person.get("din")), "designation": fld("Director"),
           "date_of_birth": fld(person.get("dob")), "pan": fld(person["pan"], method="alias"), "id_document_type": fld("Aadhaar"),
           "id_number": fld("XXXX XXXX 4471"), "address": fld("12 Lake Road, Pune 411001")},
          identity={k: person[k] for k in ("pan", "din", "dob") if person.get(k)} | {"name": person["name"]},
          instance_key=person["name"], grade=grade, reasons=reasons)


def audited_fs(f: File, entity: dict, year_end: str, text_extra: str = "", *, scale: float = 1.0) -> None:
    year = int(year_end[:4])
    f.add(f"{entity['name']}\nAUDITED FINANCIAL STATEMENTS\nBALANCE SHEET AS AT {year_end}\n{text_extra}", "audited_financial_statements",
          {"company_name": fld(entity["name"], required=True),
           "financial_year": fld(f"FY{year} (ended 31 March {year})", required=True),
           "auditor_name": fld("M/s. Rao and Associates, Chartered Accountants"), "audit_date": fld(f"{year}-08-29"),
           "accounting_standard": fld(None)},
          tables=statement_tables(year_end, scale=scale), identity={"name": entity["name"]}, instance_key=f"FY{year}")


def itr(f: File, entity: dict, years: list[str]) -> None:
    for ay in years:
        f.add(f"INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT\nAssessment Year {ay}\nPAN {entity['pan']}", "income_tax_return",
              {"pan": fld(entity["pan"], method="identifier", required=True), "taxpayer_name": fld(entity["name"], required=True),
               "assessment_year": fld(ay, required=True), "financial_year": fld(None), "filing_date": fld("2026-07-30"),
               "acknowledgement_number": fld("247100320281024"), "total_income": fld(8_600_000), "tax_payable": fld(2_150_000),
               "tax_paid": fld(2_150_000), "refund_amount": fld(0)},
              identity={"name": entity["name"], "pan": entity["pan"]}, instance_key=ay)


def gstr3b(f: File, entity: dict, periods: list[str], *, taxable: int = 9_800_000, grade: str = "A", reasons: tuple[str, ...] = (),
           low_gstin: bool = False) -> None:
    gstin = build_gstin("27", entity["pan"])
    for period in periods:
        y, m = int(period[:4]), int(period[5:])
        name = f"{MONTH_NAMES[m - 1]} {y}"
        low = {"classification": 0.9, "page_grade": 0.5, "reading_trust": 0.4, "validation": 1.0, "agreement": 0.8}
        gst = fld(gstin, method="identifier", required=True, conf=0.55 if low_gstin else 0.96, needs_review=low_gstin, comps=low if low_gstin else None)
        f.add(f"FORM GSTR-3B\nGSTIN {gstin}\nTax period {name}\n3.1 Outward taxable supplies", "gstr_3b",
              {"gstin": gst, "legal_name": fld(entity["name"], required=True, conf=0.57 if low_gstin else 0.96, needs_review=low_gstin, comps=low if low_gstin else None), "trade_name": fld(None),
               "tax_period": fld(name, required=True, conf=0.58 if low_gstin else 0.96, needs_review=low_gstin, comps=low if low_gstin else None), "filing_date": fld(f"{y}-{m:02d}-20"), "return_status": fld("Filed")},
              tables={"outward_supplies": table(["description", "taxable_value", "igst", "cgst", "sgst"],
                                                [{"description": "(a) Outward taxable supplies (other than zero rated, nil rated and exempted)",
                                                  "taxable_value": taxable, "igst": 0, "cgst": taxable * 9 // 100, "sgst": taxable * 9 // 100}])},
              identity={"name": entity["name"], "gstin": gstin}, instance_key=name, grade=grade, reasons=reasons)


def bank_statement(f: File, account: str, bank: str, holder: str, *, start: str = "2025-09-01", end: str = "2026-08-31", credit: int = 9_500_000,
                   emi: tuple[str, int, int] | None = None, payments: int = 0) -> None:
    """One credit a month; optionally a monthly instalment debit (narration, amount, months) and a
    monthly payment to suppliers."""
    rows = []
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    balance, k = 5_000_000, 0
    while (y, m) <= (ey, em):
        balance += credit
        rows.append({"date": f"{y}-{m:02d}-05", "description": "NEFT CR CUSTOMER RECEIPT", "reference_number": f"NEFT/{k:04d}",
                     "debit": None, "credit": credit, "balance": balance})
        if payments:
            balance -= payments
            rows.append({"date": f"{y}-{m:02d}-07", "description": "NEFT DR SUPPLIER PAYMENT", "reference_number": f"NEFT/P{k:04d}",
                         "debit": payments, "credit": None, "balance": balance})
        if emi and k < emi[2]:
            balance -= emi[1]
            rows.append({"date": f"{y}-{m:02d}-10", "description": emi[0], "reference_number": f"ACH/{k:04d}", "debit": emi[1],
                         "credit": None, "balance": balance})
        k += 1
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    f.add(f"STATEMENT OF ACCOUNT\n{bank}\nAccount {account}\nStatement {start} to {end}\nOpening balance", "bank_statement",
          {"account_holder_name": fld(holder, required=True), "account_number": fld(f"90100000{account}", required=True),
           "bank_name": fld(bank, required=True), "branch": fld("Pune"), "ifsc": fld("LOTU0000123"),
           "statement_period_start": fld(start, required=True), "statement_period_end": fld(end, required=True),
           "opening_balance": fld(5_000_000), "closing_balance": fld(balance), "currency": fld("INR")},
          tables={"transactions": table(["date", "description", "reference_number", "debit", "credit", "balance"], rows)},
          identity={"name": holder}, instance_key=account)


# Existing facilities and the bureau (test plan TC-20, TC-23): one term loan from a fictional lender,
# the same in the declaration, its sanction letter and the bureau report, and paid in the bank statement.
TIDEWATER_TL = {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12_000_000,
                "outstanding": 7_500_000, "emi": 250_000}


def facilities_declaration(f: File, entity: dict, account: str) -> None:
    f.add(f"DECLARATION OF EXISTING CREDIT FACILITIES AND BANK ACCOUNTS\nName of Company {entity['name']}\n"
          "We hereby declare that the company has the following existing credit facilities", "existing_facilities_declaration",
          {"company_name": fld(entity["name"], required=True), "declaration_date": fld("2026-09-15"),
           "pan": fld(entity["pan"], method="identifier"), "cin": fld(entity["cin"], method="identifier"), "gstin": fld(None)},
          tables={"facilities": table(["lender", "facility", "sanctioned_amount", "outstanding", "emi"], [TIDEWATER_TL]),
                  "bank_accounts": table(["bank", "account_number", "account_type"],
                                         [{"bank": "Lotuscrest Bank", "account_number": f"90100000{account}", "account_type": "Current account"}])},
          identity={"name": entity["name"], "pan": entity["pan"], "cin": entity["cin"]})


def sanction_letter(f: File, entity: dict) -> None:
    f.add(f"TIDEWATER FINANCE LIMITED\nSANCTION LETTER\nBorrower {entity['name']}\nWe are pleased to sanction the following credit facility",
          "sanction_letter",
          {"lender_name": fld("Tidewater Finance Limited", required=True), "borrower_name": fld(entity["name"], required=True),
           "sanction_date": fld("2024-04-12"), "reference_number": fld("TFL/SL/2024/0457")},
          tables={"facilities": table(["facility", "sanctioned_amount", "interest_rate", "tenure", "emi"],
                                      [{"facility": "Term loan", "sanctioned_amount": 12_000_000, "interest_rate": "11.25% p.a.",
                                        "tenure": "60 months", "emi": 250_000}])},
          identity={"name": entity["name"]})


def bureau_report(f: File, entity: dict, directors: list[dict]) -> None:
    gstin = build_gstin("27", entity["pan"])
    f.add(f"COMMERCIAL CREDIT INFORMATION REPORT\nCompany Name {entity['name']}\nPAN {entity['pan']}\nCredit Rank 4",
          "commercial_bureau_report",
          {"company_name": fld(entity["name"], required=True), "pan": fld(entity["pan"], method="identifier", required=True),
           "cin": fld(entity["cin"], method="identifier"), "gstin": fld(gstin, method="identifier"),
           "report_date": fld("2026-09-20"), "credit_rank": fld("4")},
          tables={"credit_facilities": table(["lender", "facility", "sanctioned_amount", "outstanding", "overdue", "status"],
                                             [{**{k: v for k, v in TIDEWATER_TL.items() if k != "emi"}, "overdue": 0, "status": "Standard"}]),
                  "related_parties": table(["name", "relationship", "pan"],
                                           [{"name": d["name"], "relationship": "Director", "pan": d["pan"]} for d in directors])},
          identity={"name": entity["name"], "pan": entity["pan"], "cin": entity["cin"], "gstin": gstin})


# --- Cases ---


def complete_case() -> list[File]:
    """TC-11: everything a private limited case needs, as separate files."""
    e = KESTREL
    files = []
    for name, type_id, build in [
        ("kestrel certificate of incorporation.pdf", "certificate_of_incorporation", lambda f: coi(f, e)),
        ("kestrel memorandum and articles.pdf", "memorandum_articles_of_association", lambda f: moa(f, e, [TARUN, ISHITA])),
        ("kestrel board resolution.pdf", "board_resolution_borrowing", lambda f: board_resolution(f, e, signed=True)),
        ("kestrel pan.pdf", "company_pan", lambda f: company_pan(f, e)),
        ("kestrel audited fy2026.pdf", "audited_financial_statements", lambda f: audited_fs(f, e, "2026-03-31")),
        # The FY 2025-26 statements show FY 2024-25 at 0.85 of this year: the FY 2024-25 statements agree (FS-01).
        ("kestrel audited fy2025.pdf", "audited_financial_statements", lambda f: audited_fs(f, e, "2025-03-31", scale=0.85)),
        ("kestrel itr.pdf", "income_tax_return", lambda f: itr(f, e, ["2026-27", "2025-26"])),
        ("kestrel gst returns.pdf", "gstr_3b", lambda f: gstr3b(f, e, GST_WINDOW)),
        ("kestrel current account.pdf", "bank_statement",
         lambda f: bank_statement(f, "1234", "Lotuscrest Bank", e["name"], emi=("NACH DR TIDEWATER FIN EMI 000123", 250_000, 6),
                                  payments=9_300_000)),
        ("kyc tarun velankar.pdf", "director_kyc", lambda f: director_kyc(f, TARUN)),
        ("kyc ishita barve.pdf", "director_kyc", lambda f: director_kyc(f, ISHITA)),
        ("kestrel existing facilities declaration.pdf", "existing_facilities_declaration",
         lambda f: facilities_declaration(f, e, "1234")),
        ("kestrel sanction letter tidewater.pdf", "sanction_letter", lambda f: sanction_letter(f, e)),
        ("kestrel bureau report.pdf", "commercial_bureau_report", lambda f: bureau_report(f, e, [TARUN, ISHITA])),
    ]:
        f = File(name, type_id)
        build(f)
        files.append(f)
    return files


def partial_case() -> list[File]:
    """TC-12 to TC-14, TC-16: a private limited case with gaps."""
    e = HERONBAY
    out = []
    for name, type_id, build in [
        ("heronbay certificate of incorporation.pdf", "certificate_of_incorporation", lambda f: coi(f, e)),
        ("heronbay board resolution.pdf", "board_resolution_borrowing", lambda f: board_resolution(f, e, signed=False)),
        ("heronbay audited fy2026.pdf", "audited_financial_statements", lambda f: audited_fs(f, e, "2026-03-31")),
        ("heronbay gst returns.pdf", "gstr_3b", lambda f: gstr3b(f, e, GST_WINDOW[4:])),
        ("heronbay current account.pdf", "bank_statement", lambda f: bank_statement(f, "1234", "Lotuscrest Bank", e["name"], start="2026-01-01")),
        ("kyc tarun velankar heronbay.pdf", "director_kyc", lambda f: director_kyc(f, TARUN)),
    ]:
        f = File(name, type_id)
        build(f)
        out.append(f)
    return out


def singles() -> list[tuple[File, dict]]:
    out: list[tuple[File, dict]] = []

    # TC-07: audited statements named as a bank statement.
    f = File("bank statement apr-mar.pdf", "audited_financial_statements")
    audited_fs(f, HERONBAY, "2025-03-31", "(tc07)")
    out.append((f, {}))

    # TC-08: labelled for one director, carries the other's identity.
    f = File("Tarun Velankar PAN.pdf", "director_kyc")
    director_kyc(f, ISHITA, "(tc08)")
    out.append((f, {}))

    # TC-08: a KYC that matches nobody on the case.
    f = File("Sunil Karve PAN.pdf", "director_kyc")
    director_kyc(f, SUNIL)
    out.append((f, {}))

    # TC-09: outside the closed list: unclassified, with candidates; a person assigns the type.
    f = File("scan_0412.pdf", None, candidates=[("company_pan", 0.41), ("certificate_of_incorporation", 0.30), ("director_kyc", 0.12)])
    f.page("Certificate\nRegistration number AAACH5678Q\nEntity")
    assigned = File("scan_0412.pdf", "company_pan")
    company_pan(assigned, HERONBAY)
    assigned.documents[0]["fields"]["company_name"]["source"]["text"] = HERONBAY["name"]
    out.append((f, {"company_pan": assigned.result("")}))

    # F-17: a photographed return, grade C, a key value below the threshold.
    f = File("gst_sep_photo.pdf", "gstr_3b")
    gstr3b(f, HERONBAY, ["2025-09"], grade="C", reasons=("blur",), low_gstin=True)
    out.append((f, {}))

    # F-07.5: an unreadable ITR (grade U), and later a better copy.
    f = File("itr_blurred.pdf", "income_tax_return")
    itr(f, HERONBAY, ["2025-26"])
    f.page_infos[0].update(grade="U", reasons=["blur"], reading_trust=0.0)
    f.documents[0]["fields"] = {}
    f.pages[0] = "INDIAN INCOME TAX RETURN\n(blurred scan)"
    out.append((f, {}))
    f = File("itr_clear.pdf", "income_tax_return")
    itr(f, HERONBAY, ["2025-26"])
    out.append((f, {}))
    return out


def main() -> None:
    for old in INGEST.glob("*.json"):
        old.unlink()
    shas = {}
    cases = {}
    for case, files in (("complete", complete_case()), ("partial", partial_case())):
        cases[case] = [f.name for f in files]
        for f in files:
            shas[f.name] = f.write()
    (HERE / "cases.json").write_text(json.dumps(cases, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for f, overrides in singles():
        shas[f.name] = f.write(overrides=overrides)
    for name, sha in shas.items():
        print(f"{sha}  {name}")


if __name__ == "__main__":
    main()
