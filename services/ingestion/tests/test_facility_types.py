"""The document types for existing facilities and the bureau (test plan TC-20, TC-23): each is
recognised by its own signals and read without a model, from positioned-text PDFs built in
tests/docgen.py. Every name is fictional."""

import pytest

from ingestion.config.loader import load_dir
from ingestion.pipeline import Ingestor
from ingestion.store import Store

from . import docgen
from .conftest import CONFIG, spec, values


@pytest.fixture(scope="module")
def shipped():
    """The configuration as published, without the reference documents' noise overlay."""
    return load_dir(CONFIG, version="test")


def _read(cfg, name: str, data: bytes):
    return Ingestor(cfg, Store(), None, None).process_file("CASE", spec(name, data), data)


def _rows(doc, table: str) -> list[dict]:
    t = doc.tables[table]
    assert t.status == "found", (table, t.reason)
    return [r.cells for r in t.rows]


def test_a_declaration_of_existing_facilities_is_recognised_and_read(shipped):
    data = docgen.facilities_declaration(
        [("Tidewater Finance Limited", "Term loan", "1,20,00,000", "75,00,000", "2,50,000"),
         ("Lotuscrest Bank", "Cash credit", "2,00,00,000", "1,85,00,000", "-")],
        [("Lotuscrest Bank", "901000001234", "Current account"), ("Lotuscrest Bank", "901000005678", "Cash credit account")])
    r = _read(shipped, "declaration.pdf", data)
    c = r.classification
    assert c.type == "existing_facilities_declaration" and c.tier == "signals" and not c.needs_review
    [doc] = r.documents
    got = values(doc)
    assert got["company_name"] == docgen.COMPANY and got["declaration_date"] == "2026-09-15"
    assert got["pan"] == docgen.PAN and got["cin"] == docgen.CIN
    assert _rows(doc, "facilities") == [
        {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12000000, "outstanding": 7500000, "emi": 250000},
        {"lender": "Lotuscrest Bank", "facility": "Cash credit", "sanctioned_amount": 20000000, "outstanding": 18500000, "emi": None},
    ]
    assert _rows(doc, "bank_accounts") == [
        {"bank": "Lotuscrest Bank", "account_number": "901000001234", "account_type": "Current account"},
        {"bank": "Lotuscrest Bank", "account_number": "901000005678", "account_type": "Cash credit account"},
    ]


def test_a_sanction_letter_is_recognised_and_read(shipped):
    data = docgen.sanction_letter("Tidewater Finance Limited", "Term loan", "1,20,00,000", "11.25% p.a.", "60 months", "2,50,000")
    r = _read(shipped, "sanction.pdf", data)
    c = r.classification
    assert c.type == "sanction_letter" and c.tier == "signals" and not c.needs_review
    [doc] = r.documents
    got = values(doc)
    assert got["lender_name"] == "Tidewater Finance Limited" and got["borrower_name"] == docgen.COMPANY
    assert got["sanction_date"] == "2024-04-12" and got["reference_number"] == "TFL/SL/2024/0457"
    assert _rows(doc, "facilities") == [
        {"facility": "Term loan", "sanctioned_amount": 12000000, "interest_rate": "11.25% p.a.", "tenure": "60 months", "emi": 250000}]


def test_a_commercial_bureau_report_is_recognised_and_read(shipped):
    data = docgen.bureau_report(
        [("Tidewater Finance Limited", "Term loan", "1,20,00,000", "75,00,000", "0", "Standard"),
         ("Lotuscrest Bank", "Cash credit", "2,00,00,000", "1,85,00,000", "0", "Standard")],
        [("Tarun Velankar", "Director", "ABCPV1234K"), ("Ishita Barve", "Director", "ABCPB5678M")])
    r = _read(shipped, "bureau.pdf", data)
    c = r.classification
    assert c.type == "commercial_bureau_report" and c.tier == "signals" and not c.needs_review
    [doc] = r.documents
    got = values(doc)
    # The company's PAN, not a director's: it is printed above the related parties.
    assert got["company_name"] == docgen.COMPANY and got["pan"] == docgen.PAN
    assert got["cin"] == docgen.CIN and got["gstin"] == docgen.GSTIN
    assert got["report_date"] == "2026-09-20" and got["credit_rank"] == "4"
    assert _rows(doc, "credit_facilities") == [
        {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12000000, "outstanding": 7500000, "overdue": 0, "status": "Standard"},
        {"lender": "Lotuscrest Bank", "facility": "Cash credit", "sanctioned_amount": 20000000, "outstanding": 18500000, "overdue": 0, "status": "Standard"},
    ]
    assert _rows(doc, "related_parties") == [
        {"name": "Tarun Velankar", "relationship": "Director", "pan": "ABCPV1234K"},
        {"name": "Ishita Barve", "relationship": "Director", "pan": "ABCPB5678M"},
    ]


@pytest.mark.parametrize("build,expected", [
    (lambda: docgen.facilities_declaration([("Tidewater Finance Limited", "Term loan", "1,20,00,000", "75,00,000", "2,50,000")], []),
     "existing_facilities_declaration"),
    (lambda: docgen.sanction_letter("Tidewater Finance Limited", "Term loan", "1,20,00,000", "11.25% p.a.", "60 months", "2,50,000"),
     "sanction_letter"),
    (lambda: docgen.bureau_report([("Tidewater Finance Limited", "Term loan", "1,20,00,000", "75,00,000", "0", "Standard")], []),
     "commercial_bureau_report"),
])
def test_each_new_type_is_placed_by_its_own_signals_with_a_clear_margin(shipped, build, expected):
    r = _read(shipped, "file.pdf", build())
    c = r.classification
    assert c.type == expected and c.candidates[0].type == expected
    # No other type, old or new, comes close or claims a page.
    assert c.candidates[1].score <= c.confidence - shipped.signals.tier1_margin
    assert c.mixed_content == []


def test_fields_the_documents_print_need_no_model(shipped):
    """Read with no model at all, every printed field is found: replay mode needs no recording for them."""
    data = docgen.sanction_letter("Tidewater Finance Limited", "Term loan", "1,20,00,000", "11.25% p.a.", "60 months", "2,50,000")
    [doc] = _read(shipped, "sanction.pdf", data).documents
    assert {k for k, f in doc.fields.items() if f.status == "found"} == {"lender_name", "borrower_name", "sanction_date", "reference_number"}
    assert all(f.method != "model" for f in doc.fields.values())
