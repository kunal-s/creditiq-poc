"""Expected values were read by hand from the sample PDFs. The accuracy report at the end is the
PoC's C3 measure on digital documents: key fields found with the right value."""

import pytest

from .conftest import values

CO = "Southgate Textiles Private Limited"

EXPECTED = {
    "Southgate_Certificate_of_Incorporation.pdf": [{
        "company_name": CO, "cin": "U17291TZ2016PTC027431", "date_of_incorporation": "2016-03-18",
        "company_type": "Company limited by shares", "roc": "Registrar of Companies, Coimbatore, Tamil Nadu"}],
    "Southgate_MOA_AOA.pdf": [{
        "company_name": CO, "registered_office": "Tamil Nadu", "authorized_share_capital": 15000000, "paid_up_share_capital": 10000000}],
    "Southgate_Entity_PAN.pdf": [{"company_name": CO, "pan": "AAHCS6612M", "date_of_issue": "2016-03-24"}],
    "Southgate_Director_KYC_Iyer_x2.pdf": [
        {"person_name": "Lakshmi Iyer", "din": "07421683", "designation": "Managing Director", "date_of_birth": "1979-07-12",
         "pan": "AXXXX1683M", "id_document_type": "Aadhaar", "id_number": "XXXX XXXX 4471"},
        {"person_name": "Venkat Iyer", "din": "07421699", "designation": "Director", "date_of_birth": "1976-09-03",
         "pan": "AXXXX1699V", "id_document_type": "Aadhaar", "id_number": "XXXX XXXX 9026"}],
    "Southgate_Board_Resolution_draft.pdf": [{
        "company_name": CO, "meeting_date": "2026-08-03", "borrowing_limit": 42500000,
        "lender_name": "Continental Commercial Bank, Coimbatore SME Branch", "authorized_persons": ["Lakshmi Iyer", "Venkat Iyer"]}],
    "Southgate_Audited_FS_FY2025.pdf": [{
        "company_name": CO, "financial_year": "FY2025 (ended 31 March 2025)",
        "auditor_name": "M/s. Rangaswamy & Associates, Chartered Accountants", "audit_date": "2025-08-29"}],
    "Southgate_Audited_FS_FY2024.pdf": [{"company_name": CO, "audit_date": "2024-08-27"}],
    "Southgate_ITR_FY2024_FY2025.pdf": [
        {"pan": "AAHCS6612M", "taxpayer_name": CO, "assessment_year": "2024-25", "financial_year": "FY2024", "filing_date": "2024-10-28",
         "acknowledgement_number": "247100320281024", "gross_total_income": 11802986, "total_income": 11802986, "tax_payable": 3068776, "tax_paid": 3068776, "refund_amount": 0},
        {"pan": "AAHCS6612M", "taxpayer_name": CO, "assessment_year": "2025-26", "financial_year": "FY2025", "filing_date": "2025-10-27",
         "acknowledgement_number": "247100915271025", "gross_total_income": 15490378, "total_income": 15490378, "tax_payable": 4027498, "tax_paid": 4027498, "refund_amount": 0}],
    "Southgate_CCB_CA_Statements_12m.pdf": [{
        "account_holder_name": CO, "account_number": "914020055831447", "bank_name": "Continental Commercial Bank", "branch": "Coimbatore SME",
        "ifsc": "CCBL0004821", "statement_period_start": "2025-08-01", "statement_period_end": "2026-07-31",
        "opening_balance": 18809000, "closing_balance": 25622250, "currency": "INR"}],
}
GSTR_PERIODS = ["December 2025", "January 2026", "February 2026", "March 2026", "April 2026", "May 2026", "June 2026", "July 2026"]
GSTR_TAXABLE = [24120500, 23864000, 22705500, 27418300, 24980400, 26142600, 25873100, 23890900]
GSTR_FILED = ["2026-01-18", "2026-02-17", "2026-03-18", "2026-04-18", "2026-05-19", "2026-06-18", "2026-07-17", "2026-08-18"]


@pytest.mark.parametrize("name", list(EXPECTED))
def test_key_fields_are_extracted_with_the_right_value(results, name):
    r = results[name]
    assert r.status == "processed" and len(r.documents) == len(EXPECTED[name])
    for doc, exp in zip(r.documents, EXPECTED[name]):
        got = values(doc)
        for k, v in exp.items():
            assert got.get(k) == v, f"{name} {doc.instance_key} {k}: {got.get(k)!r} != {v!r}"


def test_gstr_instances_one_per_return_with_cover_as_front_matter(results):
    r = results["Southgate_GSTR3B_Dec2025_Jul2026.pdf"]
    assert r.front_matter_pages == [1] and len(r.documents) == 8
    assert [values(d)["tax_period"] for d in r.documents] == GSTR_PERIODS
    assert [values(d)["filing_date"] for d in r.documents] == GSTR_FILED
    assert [d.tables["outward_supplies"].rows[0].cells["taxable_value"] for d in r.documents] == GSTR_TAXABLE
    assert sum(GSTR_TAXABLE) == 198995300  # the cover's printed total
    d = r.documents[0]
    assert [row.cells["tax_amount"] for row in d.tables["tax_payment"].rows] == [0, 603012, 603012, 1206024]
    assert d.tables["input_tax_credit"].rows[0].cells == {"description": "(A) ITC Available (whether in full or part)", "igst": 0, "cgst": 518590, "sgst": 518590}


def test_gstin_with_a_wrong_check_digit_is_flagged_and_sent_to_review(results):
    r = results["Southgate_GSTR3B_Dec2025_Jul2026.pdf"]
    d = r.documents[0]
    chk = next(c for c in d.validation if c.id == "format:gstin")
    assert chk.outcome == "fail" and chk.kind == "checksum" and "check digit" in chk.detail
    assert d.fields["gstin"].confidence <= 0.30 and d.confidence.decision == "human_review"
    assert r.decision == "human_review"


def test_bank_statement_table_ties_out_to_its_own_summary(results):
    d = results["Southgate_CCB_CA_Statements_12m.pdf"].documents[0]
    t = d.tables["transactions"]
    rows = [x.cells for x in t.rows]
    assert len(rows) == 362 and rows[0]["description"] == "OPENING BALANCE"
    assert sum(r["credit"] or 0 for r in rows) == 209489000 and sum(r["debit"] or 0 for r in rows) == 202675750
    assert rows[-1]["balance"] == 25622250 and t.repairs == [] and t.unparsed == 0
    emi = [r for r in rows if r["description"] == "MERIDIAN BANK EMI DR"]
    assert len(emi) == 12 and {r["debit"] for r in emi} == {218750}
    wrapped = next(r for r in rows if (r["reference_number"] or "").startswith("GST/CHALLAN/718341"))
    assert wrapped["reference_number"] == "GST/CHALLAN/71834182"  # a reference wrapped over two lines is rejoined
    assert next(c for c in d.validation if c.id == "running_balance").outcome == "pass"


def test_financial_statement_tables(results):
    d = results["Southgate_Audited_FS_FY2025.pdf"].documents[0]
    bs = {r.cells["particulars"]: r.cells for r in d.tables["balance_sheet"].rows}
    assert bs["(a) Share capital"]["current_period"] == 10000000
    totals = [r.cells for r in d.tables["balance_sheet"].rows if r.cells["particulars"] == "TOTAL"]
    assert [t["current_period"] for t in totals] == [115851630, 115851630] and [t["previous_period"] for t in totals] == [99048750, 99048750]
    pl = {r.cells["particulars"]: r.cells for r in d.tables["profit_and_loss"].rows}
    assert pl["V. Profit before tax (III - IV)"]["current_period"] == 15490378 and pl["VII. Profit for the year (V - VI)"]["previous_period"] == 8734210
    assert pl["Changes in inventories of FG and WIP"]["current_period"] == -2500000  # a printed negative stays negative
    cf = d.tables["cash_flow"].rows
    assert all(r.cells["previous_period"] is None for r in cf)  # the cash flow prints one year
    assert [c.outcome for c in d.validation if c.id.startswith("balance_sheet")] == ["pass", "pass"]


def test_itr_and_moa_tables(results):
    r = results["Southgate_ITR_FY2024_FY2025.pdf"]
    assert [x.cells["amount"] for x in r.documents[1].tables["income_computation"].rows][3] == 15490378
    sh = results["Southgate_MOA_AOA.pdf"].documents[0]
    assert [x.cells["number_of_shares"] for x in sh.tables["shareholding"].rows] == [510000, 490000]
    assert values(sh)["directors"] == [{"name": "Lakshmi Iyer", "din": None}, {"name": "Venkat Iyer", "din": None}]
    assert values(sh)["objects_of_company"].startswith("1. To carry on in India")


def test_unsigned_draft_resolution_goes_to_review_with_reasons(results):
    r = results["Southgate_Board_Resolution_draft.pdf"]
    d = r.documents[0]
    assert d.fields["resolution_date"].status == "missing" and d.fields["resolution_date"].reason == "not_found"
    kinds = {x["kind"] for x in r.review_reasons}
    assert r.decision == "human_review" and {"missing_required", "failed_check"} <= kinds
    assert next(c for c in d.validation if c.id == "signature_block_filled").outcome == "warn"


def test_clean_documents_are_accepted(results):
    for n in ("Southgate_Certificate_of_Incorporation.pdf", "Southgate_Entity_PAN.pdf", "Southgate_Director_KYC_Iyer_x2.pdf", "Southgate_ITR_FY2024_FY2025.pdf",
              "Southgate_Audited_FS_FY2025.pdf", "Southgate_Audited_FS_FY2024.pdf", "Southgate_CCB_CA_Statements_12m.pdf", "Southgate_MOA_AOA.pdf"):
        assert results[n].decision == "auto_accept", (n, results[n].review_reasons)


def test_every_found_value_has_a_source_page_and_box(results):
    for n, r in results.items():
        for d in r.documents:
            for k, f in d.fields.items():
                if f.status == "found":
                    assert f.source.kind == "page" and f.source.page and f.source.text and f.source.bbox and len(f.source.bbox) == 4, (n, k)
                    assert d.page_from <= f.source.page <= d.page_to
            for k, t in d.tables.items():
                if t.status == "found":
                    assert t.source["page_start"] <= t.source["page_end"] and t.source["bbox"]


def test_accuracy_report_digital(results, capsys):
    total = hit = 0
    for name, exp in EXPECTED.items():
        for doc, e in zip(results[name].documents, exp):
            got = values(doc)
            for k, v in e.items():
                total += 1
                hit += got.get(k) == v
    print(f"\nC3 (digital, scalar fields): {hit}/{total}")
    assert hit == total
