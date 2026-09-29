"""Build the synthetic test files and their canned sidecar results.

    .venv/bin/python -m tests.fixtures.build_fixtures

Writes tests/fixtures/files/<name> (small PDFs, deterministic bytes) and
tests/fixtures/ingest/<sha256>.json (IngestResult, validated against the
contract) for the StubIngestClient. All names are fictional and were
checked against the excluded-terms list; every date is relative to the
fixed test as_of, 2026-09-29.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.contracts import IngestResult
from engine.identifiers import build_gstin
from tests.fixtures.pdfgen import make_pdf

HERE = Path(__file__).resolve().parent
FILES = HERE / "files"
INGEST = HERE / "ingest"

AS_OF = "2026-09-29"
FULL = {"classification": 1.0, "page_grade": 1.0, "reading_trust": 1.0, "validation": 1.0, "agreement": 1.0}

TARUN = {"name": "Tarun Velankar", "pan": "ABCPV1234K", "din": "01234567"}
ISHITA = {"name": "Ishita Barve", "pan": "ABCPB5678M", "din": "07654321"}
SUNIL = {"name": "Sunil Karve", "pan": "ABCPK9012L"}

KESTREL = {"name": "Kestrel Fabricators Private Limited", "pan": "AAACK1234F", "cin": "U28999MH2015PTC123456"}
HERONBAY = {"name": "Heronbay Polymers Private Limited", "pan": "AAACH5678Q", "cin": "U25209MH2012PTC654321"}
GST_WINDOW = [f"{y}-{m:02d}" for y, m in [(2025, 9), (2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 9)]]


def page(n: int, grade: str = "A", reasons: tuple[str, ...] = ()) -> dict:
    return {"n": n, "route": "text", "grade": grade, "reasons": list(reasons), "ocr_confidence": None}


def field(name: str, value, page_n: int, *, comps: dict | None = None, raw: str | None = None) -> dict:
    return {
        "field": name,
        "value": value,
        "raw": raw if raw is not None else (None if value is None else str(value)),
        "page": page_n if value is not None else None,
        "bbox": [0.1, 0.1, 0.5, 0.15] if value is not None else None,
        "method": "deterministic",
        "confidence_components": dict(comps if comps is not None else FULL),
        "missing_reason": None if value is not None else "not on the page",
    }


def table(name: str, rows: list[dict], page_n: int) -> list[dict]:
    return [field(f"{name}[{i}].{col}", value, page_n) for i, row in enumerate(rows) for col, value in row.items()]


class Bundle:
    """One PDF: a page of text and a logical document per entry."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.pages: list[str] = []
        self.documents: list[dict] = []

    def add(
        self,
        text: str,
        types: list[str],
        fields: list[dict],
        *,
        key: str,
        instance_key: str | None = None,
        identity: dict | None = None,
        defects: list[dict] | None = None,
        grade: str = "A",
        reasons: tuple[str, ...] = (),
        confidence: float = 0.95,
        candidates: list[tuple[str, float]] | None = None,
        split_uncertain: bool = False,
    ) -> None:
        self.pages.append(text)
        n = len(self.pages)
        for f in fields:
            if f["page"] is not None:
                f["page"] = n
        self.documents.append(
            {
                "doc_key": key,
                "file_id": "fixture",
                "page_from": n,
                "page_to": n,
                "pages": [page(n, grade, reasons)],
                "classification": {
                    "types": types,
                    "confidence": confidence,
                    "exit_tier": "signals" if types else "none",
                    "signals": [],
                    "candidates": [{"type_id": t, "confidence": c} for t, c in (candidates or [])],
                },
                "instance_key": instance_key,
                "fields": fields,
                "identity": identity or {},
                "defects": defects or [],
                "duplicate_of_key": None,
                "split_uncertain": split_uncertain,
            }
        )

    def result(self) -> dict:
        return {
            "case_ref": "fixture",
            "config_version": "fixture",
            "engine_version": "fixture",
            "model_provider": "stub",
            "files": [{"file_id": "fixture", "status": "processed", "reason": None}],
            "documents": self.documents,
            "timings": [
                {"stage": stage, "file_id": "fixture", "ms": ms}
                for stage, ms in (("read", 40), ("grade", 12), ("split", 8), ("classify", 20), ("extract", 55))
            ],
        }

    def write(self, *, overrides: dict[str, dict] | None = None) -> str:
        data = make_pdf(self.pages)
        sha = hashlib.sha256(data).hexdigest()
        FILES.mkdir(parents=True, exist_ok=True)
        INGEST.mkdir(parents=True, exist_ok=True)
        (FILES / self.name).write_bytes(data)
        _write_result(INGEST / f"{sha}.json", self.result())
        for type_id, result in (overrides or {}).items():
            _write_result(INGEST / f"{sha}@{type_id}.json", result)
        return sha


def _write_result(path: Path, result: dict) -> None:
    IngestResult.model_validate(result)  # the contract (contracts/ingest-result.schema.json)
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# --- Documents used by several bundles ---


def coi(b: Bundle, entity: dict, key: str) -> None:
    b.add(
        f"CERTIFICATE OF INCORPORATION\n{entity['name']}\nCorporate Identity Number {entity['cin']}",
        ["certificate_of_incorporation"],
        [field("company_name", entity["name"], 1), field("cin", entity["cin"], 1),
         field("incorporation_date", "2015-06-12", 1)],
        key=key,
    )


def board_resolution(b: Bundle, entity: dict, key: str, *, signed: bool) -> None:
    b.add(
        f"CERTIFIED TRUE COPY OF THE RESOLUTION OF THE BOARD OF DIRECTORS\n{entity['name']}\n"
        "RESOLVED THAT the company do borrow from the bank",
        ["board_resolution"],
        [
            field("company_name", entity["name"], 1),
            field("resolution_date", "2026-09-01", 1),
            field("signed", signed, 1),
            *table("directors", [{"name": TARUN["name"], "din": TARUN["din"]},
                                 {"name": ISHITA["name"], "din": ISHITA["din"]}], 1),
        ],
        key=key,
        defects=[] if signed else [{"code": "unsigned", "detail": "", "pages": []}],
    )


def audited_fs(b: Bundle, entity: dict, year_end: str, key: str, text_extra: str = "") -> None:
    b.add(
        f"{entity['name']}\nBALANCE SHEET AS AT {year_end}\nINDEPENDENT AUDITOR'S REPORT {text_extra}",
        ["audited_financial_statements"],
        [
            field("period_end", year_end, 1),
            field("audited", True, 1),
            field("revenue_from_operations", 118000000, 1),
            field("profit_after_tax", 6400000, 1),
            field("net_worth", 42000000, 1),
            field("pages_present", "balance sheet, profit and loss, notes", 1),
        ],
        key=key,
        instance_key=f"FY{int(year_end[:4]) - 1}-{year_end[2:4]}",
    )


def kyc_pan(b: Bundle, person: dict, key: str, text_extra: str = "") -> None:
    b.add(
        f"INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\n{person['name']}\n{person['pan']} {text_extra}",
        ["kyc_pan_individual"],
        [field("name", person["name"], 1), field("pan", person["pan"], 1)],
        key=key,
        instance_key=person["pan"],
        identity={"name": person["name"], "pan": person["pan"]},
    )


def gstr3b(b: Bundle, entity: dict, period: str, key: str, **kw) -> None:
    gstin = build_gstin("27", entity["pan"])
    b.add(
        f"FORM GSTR-3B\nGSTIN {gstin}\nTax period {period}\n3.1 Outward taxable supplies",
        ["gstr_3b"],
        [field("gstin", gstin, 1), field("period", period, 1), field("outward_taxable_supplies", 9800000, 1),
         field("filing_date", f"{period}-20", 1)],
        key=key,
        instance_key=period,
        **kw,
    )


def bank_statement(b: Bundle, account: str, bank: str, key: str, start: str = "2025-09-01",
                   end: str = "2026-08-31") -> None:
    b.add(
        f"STATEMENT OF ACCOUNT\n{bank}\nAccount XXXXXX{account}\nPeriod {start} to {end}\nOpening balance",
        ["bank_statement"],
        [
            field("bank", bank, 1),
            field("account_holder", "account holder", 1),
            field("account_number_masked", f"XXXXXX{account}", 1),
            field("period_from", start, 1),
            field("period_to", end, 1),
            field("transactions[0].amount", 125000, 1),
        ],
        key=key,
        instance_key=account,
    )


def declaration(b: Bundle, key: str, *, facilities: list[dict], accounts: list[dict]) -> None:
    b.add(
        "DECLARATION OF EXISTING FACILITIES\nWe hereby declare our borrowings with other banks",
        ["existing_facilities_declaration"],
        [
            field("declaration_date", "2026-09-10", 1),
            field("nil_declared", not facilities, 1),
            *table("facilities", facilities, 1),
            *table("accounts", accounts, 1),
        ],
        key=key,
    )


# --- Bundles ---


def complete_bundle() -> Bundle:
    """TC-11: everything a private limited CC + TL case with collateral needs."""
    b = Bundle("complete_bundle.pdf")
    e = KESTREL
    gstin = build_gstin("27", e["pan"])
    coi(b, e, "k-coi")
    b.add(f"MEMORANDUM OF ASSOCIATION\n{e['name']}\nObjects of the company", ["moa_aoa"],
          [field("company_name", e["name"], 1), field("borrowing_powers", "as per articles", 1)], key="k-moa")
    board_resolution(b, e, "k-br", signed=True)
    b.add(f"INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\n{e['name']}\n{e['pan']}", ["pan_entity"],
          [field("name", e["name"], 1), field("pan", e["pan"], 1)], key="k-pan")
    b.add(f"FORM GST REG-06 REGISTRATION CERTIFICATE\n{gstin}\nLegal name {e['name']}",
          ["gst_registration_certificate"],
          [field("gstin", gstin, 1), field("legal_name", e["name"], 1),
           field("constitution", "Private Limited Company", 1),
           *table("persons", [{"name": TARUN["name"], "designation": "Director"},
                              {"name": ISHITA["name"], "designation": "Director"}], 1)],
          key="k-gstreg")
    b.add("UDYAM REGISTRATION CERTIFICATE\nUDYAM-MH-18-0012345\nType of enterprise Small", ["udyam_certificate"],
          [field("udyam_number", "UDYAM-MH-18-0012345", 1), field("enterprise_name", e["name"], 1)], key="k-udyam")
    kyc_pan(b, TARUN, "k-kyc-tarun")
    kyc_pan(b, ISHITA, "k-kyc-ishita")
    audited_fs(b, e, "2026-03-31", "k-fs26")
    audited_fs(b, e, "2025-03-31", "k-fs25")
    b.add(f"{e['name']}\nPROVISIONAL BALANCE SHEET AS AT 31 AUGUST 2026\nProfit and loss",
          ["provisional_financial_statements"],
          [field("period_end", "2026-08-31", 1), field("audited", False, 1),
           field("revenue_from_operations", 52000000, 1),
           field("pages_present", "balance sheet, profit and loss", 1)],
          key="k-prov", instance_key="FY2026-27")
    b.add(f"{e['name']}\nPROJECTED BALANCE SHEET AND PROFIT AND LOSS\nAssumptions", ["projected_financial_statements"],
          [field("period_end", "2027-03-31", 1), field("revenue_from_operations", 140000000, 1)],
          key="k-proj", instance_key="FY2027-28")
    for ay in ("2026-27", "2025-26"):
        b.add(f"INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT\nAssessment Year {ay}\nPAN {e['pan']}",
              ["itr_acknowledgement"],
              [field("assessment_year", ay, 1), field("pan", e["pan"], 1), field("total_income", 8600000, 1)],
              key=f"k-itr-{ay}", instance_key=ay)
    b.add("CREDIT MONITORING ARRANGEMENT (CMA) DATA\nMaximum permissible bank finance", ["cma_data"],
          [field("assessed_bank_finance", 50000000, 1)], key="k-cma")
    bank_statement(b, "1234", "Lotuscrest Bank", "k-bank-1234")
    for period in GST_WINDOW:
        gstr3b(b, e, period, f"k-3b-{period}")
    b.add("STOCK AND BOOK DEBTS STATEMENT AS AT 31-08-2026\nRaw material\nFinished goods", ["stock_statement"],
          [field("as_at_date", "2026-08-31", 1), field("total_stock", 21000000, 1), field("book_debts", 16000000, 1)],
          key="k-stock")
    b.add("AGEING OF DEBTORS AND CREDITORS\n0-30 30-60 above 90", ["debtors_creditors_ageing"],
          [field("as_at_date", "2026-08-31", 1)], key="k-ageing")
    b.add(f"COMMERCIAL CREDIT INFORMATION REPORT\n{e['name']}\nRank 3", ["bureau_commercial"],
          [field("subject_name", e["name"], 1), field("report_date", "2026-09-15", 1), field("score", "Rank 3", 1)],
          key="k-bureau")
    declaration(b, "k-decl", facilities=[],
                accounts=[{"bank": "Lotuscrest Bank", "account_number_masked": "XXXXXX1234"}])
    b.add("SALE DEED\nSchedule of property\nSub-Registrar", ["title_document"],
          [field("owner", e["name"], 1), field("registration_date", "2018-02-14", 1)],
          key="k-title", instance_key="plot-7")
    b.add("VALUATION REPORT\nFair market value\nRealisable value", ["valuation_report"],
          [field("valuation_date", "2026-06-10", 1), field("market_value", 98000000, 1)],
          key="k-valuation", instance_key="plot-7")
    return b


def partial_bundle() -> Bundle:
    """TC-12, TC-13, TC-14, TC-16: a private limited CC case with gaps."""
    b = Bundle("partial_bundle.pdf")
    e = HERONBAY
    coi(b, e, "h-coi")
    board_resolution(b, e, "h-br", signed=False)
    b.add(f"{e['name']}\nPROVISIONAL PROFIT AND LOSS FOR THE PERIOD ENDED 31 AUGUST 2026",
          ["provisional_financial_statements"],
          [field("period_end", "2026-08-31", 1), field("audited", False, 1),
           field("revenue_from_operations", 36000000, 1), field("pages_present", "profit and loss", 1)],
          key="h-prov", instance_key="FY2026-27",
          defects=[{"code": "pages_absent", "detail": "balance sheet pages absent", "pages": []}])
    for i, period in enumerate(GST_WINDOW[4:]):
        gstr3b(b, e, period, f"h-3b-{period}", split_uncertain=(i == 3))
    b.add("STOCK AND BOOK DEBTS STATEMENT AS AT 30-06-2026\nRaw material", ["stock_statement"],
          [field("as_at_date", "2026-06-30", 1), field("total_stock", 9000000, 1), field("book_debts", 7000000, 1)],
          key="h-stock")
    bank_statement(b, "1234", "Lotuscrest Bank", "h-bank-1234")
    declaration(
        b,
        "h-decl",
        facilities=[{"lender": "Tidewater Bank", "facility": "Cash credit", "limit": 3000000}],
        accounts=[{"bank": "Lotuscrest Bank", "account_number_masked": "XXXXXX1234"},
                  {"bank": "Tidewater Bank", "account_number_masked": "XXXXXX5678"}],
    )
    kyc_pan(b, TARUN, "h-kyc-tarun")
    audited_fs(b, e, "2026-03-31", "h-fs26")
    return b


def singles() -> list[tuple[Bundle, dict]]:
    out = []

    # TC-07: audited statements named as a bank statement.
    b = Bundle("bank statement apr-mar.pdf")
    audited_fs(b, HERONBAY, "2025-03-31", "tc07-fs25", text_extra="(tc07)")
    out.append((b, {}))

    # TC-08: labelled for one director, carries the other's identity.
    b = Bundle("Tarun Velankar PAN.pdf")
    kyc_pan(b, ISHITA, "tc08-kyc", text_extra="(tc08)")
    out.append((b, {}))

    # TC-08: a KYC that matches nobody on the case.
    b = Bundle("Sunil Karve PAN.pdf")
    kyc_pan(b, SUNIL, "tc08-stranger")
    out.append((b, {}))

    # TC-09: outside the closed list's signals: unclassified, with candidates.
    b = Bundle("scan_0412.pdf")
    b.add("Certificate\nRegistration number UDYAM-MH-18-0099887\nEnterprise", [], [], key="tc09-unknown",
          confidence=0.41, candidates=[("udyam_certificate", 0.41), ("covering_letter", 0.30), ("index_page", 0.12)])
    assigned = Bundle("scan_0412.pdf")
    assigned.add("", ["udyam_certificate"],
                 [field("udyam_number", "UDYAM-MH-18-0099887", 1), field("enterprise_name", HERONBAY["name"], 1)],
                 key="tc09-unknown")
    out.append((b, {"udyam_certificate": assigned.result()}))

    # F-17: a photographed return, grade C, a key value below the threshold.
    b = Bundle("gst_sep_photo.pdf")
    low = {"classification": 0.9, "page_grade": 0.5, "reading_trust": 0.4, "validation": 1.0, "agreement": 0.0}
    gstin = build_gstin("27", HERONBAY["pan"])
    b.add(f"FORM GSTR-3B\nGSTIN {gstin}\nTax period 2025-09", ["gstr_3b"],
          [field("gstin", gstin, 1), field("period", "2025-09", 1),
           field("outward_taxable_supplies", 9100000, 1, comps=low, raw="91,00,000"),
           field("filing_date", "2025-10-20", 1)],
          key="f17-3b", instance_key="2025-09", grade="C", reasons=("blur",))
    out.append((b, {}))

    # F-07.5: an unreadable ITR (grade U), and later a better copy.
    b = Bundle("itr_blurred.pdf")
    b.add("ITR", ["itr_acknowledgement"], [], key="u-itr", instance_key="2025-26", grade="U", reasons=("blur",))
    out.append((b, {}))
    b = Bundle("itr_clear.pdf")
    b.add(f"INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT\nAssessment Year 2025-26\nPAN {HERONBAY['pan']}",
          ["itr_acknowledgement"],
          [field("assessment_year", "2025-26", 1), field("pan", HERONBAY["pan"], 1),
           field("total_income", 5100000, 1)],
          key="u-itr-clear", instance_key="2025-26")
    out.append((b, {}))
    return out


def main() -> None:
    for old in INGEST.glob("*.json"):
        old.unlink()
    shas = {}
    for bundle in (complete_bundle(), partial_bundle()):
        shas[bundle.name] = bundle.write()
    for bundle, overrides in singles():
        shas[bundle.name] = bundle.write(overrides=overrides)
    for name, sha in shas.items():
        print(f"{sha}  {name}")


if __name__ == "__main__":
    main()
