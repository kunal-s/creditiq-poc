"""End-to-end: descriptor -> financial model -> ledger -> rendered PDF,
checked by re-reading the PDF rather than trusting the builder (in the
spirit of the generic repo's validate.py) — but via pdftotext/pdfinfo, never
PyMuPDF (CLAUDE.md rule 10)."""

import subprocess

import pytest

from engine.samplegen.casebuild import compile_case
from engine.samplegen.ledger import generate_bank_ledger
from engine.samplegen.render.bank_statement import build_bank_statement
from engine.samplegen.render.common import FOOTER_TEXT, indian_group


def _pdftotext(path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout


def _pdfinfo(path) -> dict[str, str]:
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=True).stdout
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info


@pytest.fixture(params=["case-a", "case-b"])
def rendered_statement(tmp_path, request):
    case_id = request.param
    c = compile_case(case_id)
    d = c.descriptor
    fy = 2026
    txns = generate_bank_ledger(d, c.financials, fy)
    opening = int(c.financials.years[fy - 1].bs.borrowings_st)
    closing = int(c.financials.years[fy].bs.borrowings_st)
    bank = d.banks[0]
    path, pages = build_bank_statement(
        str(tmp_path),
        file_name=f"{case_id}-bank-statement.pdf",
        bank_name=bank.name,
        branch=f"{d.entity.address.city} Branch",
        entity_name=d.entity.legal_name,
        account_number=d.accounts[0].number,
        ifsc=f"{bank.ifsc_prefix}0001234",
        office=f"{d.entity.address.line1}, {d.entity.address.city}",
        gstin=d.identifiers.gstin,
        period_label="01 April 2025 to 31 March 2026",
        opening_date_label="01 Apr 2025",
        closing_date_label="31 Mar 2026",
        opening=opening,
        closing=closing,
        txns=txns,
    )
    return {"case_id": case_id, "path": path, "pages": pages, "opening": opening, "closing": closing, "txns": txns}


def test_footer_on_every_page(rendered_statement):
    text = _pdftotext(rendered_statement["path"])
    assert text.count(FOOTER_TEXT) == rendered_statement["pages"]


def test_closing_balance_printed_and_correct(rendered_statement):
    text = _pdftotext(rendered_statement["path"])
    assert indian_group(rendered_statement["closing"]) in text


def test_opening_balance_printed_and_correct(rendered_statement):
    text = _pdftotext(rendered_statement["path"])
    assert indian_group(rendered_statement["opening"]) in text


def test_no_watermark_text(rendered_statement):
    text = _pdftotext(rendered_statement["path"])
    assert "SPECIMEN" not in text.upper()
    # "sample" is whitelisted only inside the required footer (plan.md finding
    # 6b) — everywhere else it's a plain textile word to keep out of prose
    # (C12), so check for it only after stripping the footer's own text.
    without_footer = text.upper().replace(FOOTER_TEXT.upper(), "")
    assert "SAMPLE" not in without_footer


def test_metadata_is_neutral(rendered_statement):
    info = _pdfinfo(rendered_statement["path"])
    blob = " ".join(info.values()).upper()
    assert "SPECIMEN" not in blob
    assert rendered_statement["case_id"].upper().replace("-", "") not in blob.replace("-", "")


def test_running_balance_holds_row_by_row(rendered_statement):
    balance = rendered_statement["opening"]
    for t in rendered_statement["txns"]:
        balance = balance - t.credit + t.debit
        assert t.balance == balance


def test_no_text_extraction_errors_and_page_count_matches(rendered_statement):
    info = _pdfinfo(rendered_statement["path"])
    assert int(info["Pages"]) == rendered_statement["pages"]
