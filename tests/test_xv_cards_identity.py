"""The identity cards of the cross-verification board (ID-01 to ID-08; engine/xv_cards/identity.py):
each statement or source as a column with its provenance, value and coverage, and the rows behind
it with their document and page; two documents of one type told apart by what each covers; the
majority value as the reference; the difference in words; what would complete a check short of
documents; the key-figure lines for the area's overview card. An identity card has no amount and
no gaps, and building it never changes a finding. Every name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cases, crosschecks, db, facts, pipeline, xv_cards
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

CO = "Kestrel Tools Pvt Ltd"
PAN, ITR_PAN, BUREAU_PAN = "AAACK1234F", "AAACK9876Q", "AAACK9999Z"
CIN, OTHER_CIN = "U28990MH2015PTC123456", "U28990MH2015PTC123465"
HERONBAY = "Heronbay Polymers Private Limited"
TARUN, ISHITA, SUNIL, LEELA = "Tarun Velankar", "Ishita Barve", "Sunil Karve", "Leela Varghese"
TARUN_PAN, ISHITA_PAN = "ABCPV1234K", "ABCPB5678M"
TARUN_DIN, ISHITA_DIN, SUNIL_DIN = "01234567", "07654321", "09123456"
# The fields a card builder sets; everything else in a finding is the rule's.
CARD = {"columns", "gaps", "gap_tolerance", "mismatch", "reference", "amount", "request", "highlights"}
LABELS = {"ID-01": "PAN", "ID-02": "GSTIN", "ID-03": "Company name", "ID-04": "Promoters", "ID-05": "CIN",
          "ID-06": "Director identifiers", "ID-07": "CIN particulars", "ID-08": "Directors in the memorandum",
          "ID-09": "Names of people"}
"""Each check's line on the area's overview card."""


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _cards(client: TestClient, headers: dict, root: Path, case_id: str) -> dict[str, list[dict]]:
    """The board's findings by rule, after a fresh run of the checks."""
    _refresh(root, case_id)
    response = client.get(f"/api/cases/{case_id}/cross-verification", headers=headers)
    assert response.status_code == 200, response.text
    out: dict[str, list[dict]] = {}
    for item in response.json()["items"]:
        out.setdefault(item["finding"]["rule_id"], []).append(item["finding"])
    return out


def _card(client: TestClient, headers: dict, root: Path, case_id: str, rule: str) -> dict:
    [f] = _cards(client, headers, root, case_id)[rule]
    return f


def _columns(f: dict) -> list[tuple]:
    return [(c["label"], c["value"], c["differs"]) for c in f["columns"]]


def _pages(evidence: list[dict]) -> list[tuple[str, int]]:
    return [(e["document_id"], e["page"]) for e in evidence]


def _rows(c: dict) -> list[tuple[list, list[tuple[str, int]]]]:
    return [(r["cells"], _pages(r["evidence"])) for r in c["rows"]]


def _no_amount(f: dict) -> None:
    assert f["gaps"] == [] and f["amount"] is None and f["gap_tolerance"] is None


def _lines(f: dict) -> list[tuple]:
    """The finding's key-figure lines for the overview card: label, facts (label, value, differs), note.
    Each names its finding, rule and outcome, and an identifier is text."""
    for h in f["highlights"]:
        assert (h["finding_id"], h["rule_id"], h["outcome"]) == (f["id"], f["rule_id"], f["outcome"])
        assert all(x["unit"] == "text" for x in h["facts"])
    return [(h["label"], [(x["label"], x["value"], x["differs"]) for x in h["facts"]], h["note"]) for h in f["highlights"]]


def _message_doc(root: Path, case_id: str) -> str:
    conn = db.connect(root)
    try:
        return conn.execute("SELECT id FROM documents WHERE case_id = ? AND doc_key = 'message'", (case_id,)).fetchone()["id"]
    finally:
        conn.close()


def _span(message: str, text: str) -> str:
    """A case-header source pointing at `text` in the sourcing message."""
    start = message.index(text)
    return f"message:{start}-{start + len(text)}"


def _person(value: str) -> dict:
    """A case-header value a person entered: it has no page to cite."""
    return {"value": value, "source": "person"}


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, analyst: dict, root: Path, **overrides) -> str:
    return make_case(client, analyst, root, **{"borrower": CO, **overrides})


# --- ID-01 entity PAN: each statement a column, or each group when there are more than four ---


def test_each_pan_statement_is_a_column_and_the_majority_is_the_reference(client, analyst, published_data_root):
    root = published_data_root
    message = f"{CO}, PAN {PAN}, needs a term loan for a new press line."
    case_id = _case(client, analyst, root, message_text=message, header={"pan": {"value": PAN, "source": _span(message, PAN)}})
    card = add_doc(root, case_id, "company_pan", {"pan": PAN}, page=3)
    itr = add_doc(root, case_id, "income_tax_return", {"pan": PAN})
    gst = add_doc(root, case_id, "gstr_3b", {"gstin": "27AAACX9999Q1Z3"})
    f = _card(client, analyst, root, case_id, "ID-01")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Company PAN", PAN, False), ("Income tax return", PAN, False),
                           ("GSTR-3B (PAN within the GSTIN)", "AAACX9999Q", True), ("Sourcing message", PAN, False)]
    cols = f["columns"]
    assert [c["sources"] for c in cols] == [["company_pan"], ["income_tax_return"], ["gstr_3b"], ["application_message"]]
    assert [c["provenance"] for c in cols] == [["borrower_supplied"]] * 3 + [["declared"]]
    assert [c["coverage"] for c in cols] == ["Page 3", "Page 1", "Page 1", "In the sourcing message"]
    pages = [[(card, 3)], [(itr, 1)], [(gst, 1)], [(_message_doc(root, case_id), 1)]]
    assert [_pages(c["evidence"]) for c in cols] == pages
    assert [_rows(c) for c in cols] == [[(["PAN", c["value"]], p)] for c, p in zip(cols, pages)]
    assert all(c["row_columns"] == ["Field", "Value"] and c["unit"] == "text" for c in cols)
    assert f["reference"] == PAN
    assert f["mismatch"] == "GSTR-3B (PAN within the GSTIN) gives AAACX9999Q; the other 3 sources give AAACK1234F."
    assert f["request"] is None
    _no_amount(f)
    # The overview line: each value once, the majority first, the odd one marked; a long group is counted.
    assert _lines(f) == [("PAN", [("2 documents and the sourcing message", PAN, False),
                                  ("GSTR-3B (PAN within the GSTIN)", "AAACX9999Q", True)], None)]


def test_two_pans_with_no_majority_are_both_marked_and_both_named(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    card = add_doc(root, case_id, "company_pan", {"pan": PAN})
    itr = add_doc(root, case_id, "income_tax_return", {"pan": PAN}, corrected={"pan": ITR_PAN})
    f = _card(client, analyst, root, case_id, "ID-01")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Company PAN", PAN, True), ("Income tax return", ITR_PAN, True)]
    assert [_rows(c) for c in f["columns"]] == [[(["PAN", PAN], [(card, 1)])], [(["PAN", ITR_PAN], [(itr, 1)])]]
    # The return's PAN is a person's correction, and its column says so (F-19.4).
    assert [c["relies_on_manual"] for c in f["columns"]] == [False, True]
    assert f["reference"] is None
    assert f["mismatch"] == "2 different values: AAACK1234F (Company PAN); AAACK9876Q (Income tax return)."
    _no_amount(f)
    assert _lines(f) == [("PAN", [("Company PAN", PAN, True), ("Income tax return", ITR_PAN, True)], None)]


def test_agreeing_pans_pass_with_no_reference_and_no_mismatch(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"pan": PAN})
    add_doc(root, case_id, "income_tax_return", {"pan": PAN})
    f = _card(client, analyst, root, case_id, "ID-01")
    assert f["outcome"] == "pass"
    assert _columns(f) == [("Company PAN", PAN, False), ("Income tax return", PAN, False)]
    assert f["reference"] is None and f["mismatch"] is None and f["request"] is None
    _no_amount(f)
    assert _lines(f) == [("PAN", [("2 sources", PAN, False)], "same across 2 sources")]


def test_a_pan_waiting_for_review_asks_for_the_review_and_not_for_a_document(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    card = add_doc(root, case_id, "company_pan", {"pan": PAN}, pending={"pan"})
    add_doc(root, case_id, "income_tax_return", {"pan": ITR_PAN})
    f = _card(client, analyst, root, case_id, "ID-01")
    assert f["outcome"] == "incomplete" and f["explanation"].startswith("Waiting for review of company PAN")
    # The columns keep the rule's sides: two values, neither the majority.
    assert _columns(f) == [("Company PAN", PAN, True), ("Income tax return", ITR_PAN, True)]
    assert [c["awaiting_review"] for c in f["columns"]] == [True, False]
    assert _pages(f["columns"][0]["evidence"]) == [(card, 1)]
    assert f["request"] is None and f["mismatch"] is None and f["reference"] is None
    _no_amount(f)
    # The values so far, marked as the card marks them, and that a review completes it.
    assert _lines(f) == [("PAN", [("Company PAN", PAN, True), ("Income tax return", ITR_PAN, True)], "waiting for review")]


def test_more_than_four_pan_statements_are_grouped_as_the_rule_grouped_them(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    card = add_doc(root, case_id, "company_pan", {"pan": PAN}, page=2)
    itr = add_doc(root, case_id, "income_tax_return", {"pan": PAN})
    returns = [gstr(root, case_id, p, 4_000_000) for p in ("April 2025", "May 2025", "June 2025")]
    report = add_doc(root, case_id, "commercial_bureau_report", {"pan": BUREAU_PAN})
    f = _card(client, analyst, root, case_id, "ID-01")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Company PAN, Income tax return, GSTR-3B (PAN within the GSTIN)", PAN, False),
                           ("Commercial bureau report", BUREAU_PAN, True)]
    agree, odd = f["columns"]
    # A row per statement in the group, each with its own document and page; the returns, alike by
    # type, are told apart by their months.
    assert agree["row_columns"] == ["Document", "PAN"]
    assert _rows(agree) == [(["Company PAN", PAN], [(card, 2)]), (["Income tax return", PAN], [(itr, 1)])] + [
        ([f"GSTR-3B (PAN within the GSTIN) · {month}", PAN], [(r, 1)])
        for r, month in zip(returns, ("Apr 2025", "May 2025", "Jun 2025"))]
    assert _pages(agree["evidence"]) == [(card, 2), (itr, 1)] + [(r, 1) for r in returns]
    assert agree["coverage"] == "5 documents"
    assert agree["sources"] == ["company_pan", "income_tax_return", "gstr_3b"] and agree["provenance"] == ["borrower_supplied"]
    assert _rows(odd) == [(["Commercial bureau report", BUREAU_PAN], [(report, 1)])]
    assert odd["coverage"] == "Page 1" and odd["provenance"] == ["independent"]
    assert f["reference"] == PAN
    assert f["mismatch"] == "Commercial bureau report gives AAACK9999Z; the other 5 sources give AAACK1234F."
    _no_amount(f)
    assert _lines(f) == [("PAN", [("5 documents", PAN, False), ("Commercial bureau report", BUREAU_PAN, True)], None)]


# --- ID-02 GSTIN ---


def test_one_gstin_in_every_return_is_not_applicable_and_keeps_its_columns(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    april = add_doc(root, case_id, "gstr_3b", {"gstin": "27AAACK1234F1Z0", "tax_period": "April 2025"})
    may = add_doc(root, case_id, "gstr_3b", {"gstin": "27AAACK1234F1Z0", "tax_period": "May 2025"})
    f = _card(client, analyst, root, case_id, "ID-02")
    assert f["outcome"] == "not_applicable"
    # Neither return shows outward supplies, so the facts hold no month for either, and both are on
    # page 1: each is told apart by its place among them.
    assert _columns(f) == [("GSTR-3B · 1 of 2", "27AAACK1234F1Z0", False), ("GSTR-3B · 2 of 2", "27AAACK1234F1Z0", False)]
    assert [_rows(c) for c in f["columns"]] == [[(["GSTIN", "27AAACK1234F1Z0"], [(d, 1)])] for d in (april, may)]
    assert f["reference"] is None and f["mismatch"] is None and f["request"] is None
    _no_amount(f)
    # A check that did not apply has no line on the overview card.
    assert f["highlights"] == []


def test_gstins_with_no_majority_are_grouped_and_every_value_is_named(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"gstin": _person("24AAACK1234F1Z9")})
    first = [gstr(root, case_id, p, 4_000_000) for p in ("April 2025", "May 2025")]
    second = [gstr(root, case_id, p, 4_000_000, gstin="29AAACK1234F1Z5") for p in ("June 2025", "July 2025")]
    f = _card(client, analyst, root, case_id, "ID-02")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("GSTR-3B", "27AAACK1234F1Z0", True), ("GSTR-3B", "29AAACK1234F1Z5", True),
                           ("Sourcing message", "24AAACK1234F1Z9", True)]
    cols = f["columns"]
    # Typed on the case by a person, the value has no place in the sourcing message to point to.
    assert [c["coverage"] for c in cols] == ["2 documents", "2 documents", "Entered on the case"]
    # Each return's row names its month.
    assert [_rows(c) for c in cols[:2]] == [[([f"GSTR-3B · {m}", c["value"]], [(d, 1)]) for d, m in zip(docs, named)]
                                            for c, docs, named in zip(cols, (first, second),
                                                                      (("Apr 2025", "May 2025"), ("Jun 2025", "Jul 2025")))]
    # A value a person entered on the case has no page: its row and column cite none.
    assert _rows(cols[2]) == [(["Sourcing message", "24AAACK1234F1Z9"], [])] and cols[2]["evidence"] == []
    assert all(c["row_columns"] == ["Document", "GSTIN"] for c in cols)
    assert f["reference"] is None
    assert f["mismatch"] == ("3 different values: 27AAACK1234F1Z0 (GSTR-3B); 29AAACK1234F1Z5 (GSTR-3B); "
                             "24AAACK1234F1Z9 (Sourcing message).")
    _no_amount(f)
    assert _lines(f) == [("GSTIN", [("GSTR-3B", "27AAACK1234F1Z0", True), ("GSTR-3B", "29AAACK1234F1Z5", True),
                                    ("Sourcing message", "24AAACK1234F1Z9", True)], None)]


def test_beyond_four_values_the_last_column_holds_the_rest_and_the_majority_keeps_its_own(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"gstin": _person("33AAACK1234F1Z1")})
    odd = add_doc(root, case_id, "gstr_3b", {"gstin": "27AAACK1234F1Z0"})
    add_doc(root, case_id, "commercial_bureau_report", {"gstin": "29AAACK1234F1Z5"})
    declared = add_doc(root, case_id, "existing_facilities_declaration", {"gstin": "24AAACK1234F1Z9"})
    majority = [add_doc(root, case_id, "gstr_3b", {"gstin": "07AAACK1234F1Z2"}) for _ in range(2)]
    f = _card(client, analyst, root, case_id, "ID-02")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("GSTR-3B", "27AAACK1234F1Z0", True), ("Commercial bureau report", "29AAACK1234F1Z5", True),
                           ("GSTR-3B", "07AAACK1234F1Z2", False),
                           ("Declaration of existing facilities and Sourcing message", "24AAACK1234F1Z9; 33AAACK1234F1Z1", True)]
    kept, rest = f["columns"][2], f["columns"][3]
    # No month is known for any of the three returns, all on page 1: each row names its place among them.
    assert _rows(f["columns"][0]) == [(["GSTR-3B · 1 of 3", "27AAACK1234F1Z0"], [(odd, 1)])]
    assert _rows(kept) == [([f"GSTR-3B · {n} of 3", "07AAACK1234F1Z2"], [(d, 1)]) for n, d in zip((2, 3), majority)]
    assert _rows(rest) == [(["Declaration of existing facilities", "24AAACK1234F1Z9"], [(declared, 1)]),
                           (["Sourcing message", "33AAACK1234F1Z1"], [])]
    assert rest["sources"] == ["existing_facilities_declaration", "application_message"] and rest["provenance"] == ["declared"]
    assert rest["coverage"] == "1 document and an entry on the case"
    assert f["reference"] == "07AAACK1234F1Z2"
    assert f["mismatch"] == ("GSTR-3B gives 27AAACK1234F1Z0; Commercial bureau report gives 29AAACK1234F1Z5; "
                             "Declaration of existing facilities gives 24AAACK1234F1Z9; Sourcing message gives 33AAACK1234F1Z1; "
                             "the other 2 sources give 07AAACK1234F1Z2.")
    _no_amount(f)
    # As many values as a card has columns, the majority first; the line says how many there are.
    assert _lines(f) == [("GSTIN", [("GSTR-3B", "07AAACK1234F1Z2", False), ("GSTR-3B · 1 of 3", "27AAACK1234F1Z0", True),
                                    ("Commercial bureau report", "29AAACK1234F1Z5", True),
                                    ("Declaration of existing facilities", "24AAACK1234F1Z9", True)], "5 different values")]


# --- ID-03 legal name: the names "read" ---


def test_a_name_variant_agrees_with_the_majority_and_the_odd_name_reads_differently(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    card = add_doc(root, case_id, "company_pan", {"pan": PAN, "company_name": CO})
    itr = add_doc(root, case_id, "income_tax_return", {"pan": PAN, "taxpayer_name": "KESTREL TOOLS PRIVATE LIMITED"})
    afs = add_doc(root, case_id, "audited_financial_statements", {"company_name": HERONBAY}, page=4)
    f = _card(client, analyst, root, case_id, "ID-03")
    assert f["outcome"] == "fail"
    # Each document's name as printed; the return's spelling is the same name, so it does not differ.
    assert _columns(f) == [("Company PAN", CO, False), ("Income tax return", "KESTREL TOOLS PRIVATE LIMITED", False),
                           ("Audited financial statements", HERONBAY, True)]
    assert [_rows(c) for c in f["columns"]] == [[(["Legal name", CO], [(card, 1)])],
                                                [(["Legal name", "KESTREL TOOLS PRIVATE LIMITED"], [(itr, 1)])],
                                                [(["Legal name", HERONBAY], [(afs, 4)])]]
    assert [c["coverage"] for c in f["columns"]] == ["Page 1", "Page 1", "Page 4"]
    assert f["reference"] == CO
    assert f["mismatch"] == ("Audited financial statements reads Heronbay Polymers Private Limited; "
                             "the other 2 sources read Kestrel Tools Pvt Ltd.")
    _no_amount(f)
    # The name the majority gives first, with the documents giving it, as their group is labelled.
    assert _lines(f) == [("Company name", [("Company PAN, Income tax return", CO, False),
                                           ("Audited financial statements", HERONBAY, True)], None)]


def test_two_names_with_no_majority_are_both_named(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"company_name": CO})
    add_doc(root, case_id, "audited_financial_statements", {"company_name": HERONBAY})
    f = _card(client, analyst, root, case_id, "ID-03")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Company PAN", CO, True), ("Audited financial statements", HERONBAY, True)]
    assert f["reference"] is None
    assert f["mismatch"] == ("2 different values: Kestrel Tools Pvt Ltd (Company PAN); "
                             "Heronbay Polymers Private Limited (Audited financial statements).")


def test_each_spelling_takes_the_marking_of_the_name_it_was_grouped_with(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"company_name": CO})
    add_doc(root, case_id, "income_tax_return", {"taxpayer_name": "KESTREL TOOLS PRIVATE LIMITED"})
    add_doc(root, case_id, "audited_financial_statements", {"company_name": HERONBAY})
    add_doc(root, case_id, "gstr_3b", {"legal_name": "HERONBAY POLYMERS PVT LTD"})
    f = _card(client, analyst, root, case_id, "ID-03")
    assert f["outcome"] == "fail"
    # Two names, two documents each: neither is the majority, so every column differs, spellings included.
    assert _columns(f) == [("Company PAN", CO, True), ("Income tax return", "KESTREL TOOLS PRIVATE LIMITED", True),
                           ("Audited financial statements", HERONBAY, True), ("GSTR-3B", "HERONBAY POLYMERS PVT LTD", True)]
    assert f["reference"] is None
    assert f["mismatch"] == ("2 different values: Kestrel Tools Pvt Ltd (Company PAN and Income tax return); "
                             "Heronbay Polymers Private Limited (Audited financial statements and GSTR-3B).")


def test_grouped_names_keep_each_document_s_spelling_in_its_row(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    coi = add_doc(root, case_id, "certificate_of_incorporation", {"company_name": "Kestrel Tools Private Limited"})
    moa = add_doc(root, case_id, "memorandum_articles_of_association", {"company_name": "KESTREL TOOLS PVT LTD"})
    card = add_doc(root, case_id, "company_pan", {"company_name": CO})
    statement = bank(root, case_id, [], holder="KESTREL TOOLS P")
    afs = add_doc(root, case_id, "audited_financial_statements", {"company_name": HERONBAY})
    f = _card(client, analyst, root, case_id, "ID-03")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Certificate of incorporation, Memorandum and articles of association, Company PAN, Bank statement",
                            "Kestrel Tools Private Limited", False), ("Audited financial statements", HERONBAY, True)]
    agree, odd = f["columns"]
    assert agree["row_columns"] == ["Document", "Legal name"]
    assert _rows(agree) == [(["Certificate of incorporation", "Kestrel Tools Private Limited"], [(coi, 1)]),
                            (["Memorandum and articles of association", "KESTREL TOOLS PVT LTD"], [(moa, 1)]),
                            (["Company PAN", CO], [(card, 1)]),
                            (["Bank statement", "KESTREL TOOLS P"], [(statement, 1)])]
    assert agree["coverage"] == "4 documents" and _rows(odd) == [(["Audited financial statements", HERONBAY], [(afs, 1)])]
    assert f["reference"] == "Kestrel Tools Private Limited"
    assert f["mismatch"] == ("Audited financial statements reads Heronbay Polymers Private Limited; "
                             "the other 4 sources read Kestrel Tools Private Limited.")


# --- ID-05 CIN ---


def test_a_cin_short_of_the_memorandum_asks_for_it_then_names_both_values(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    coi = add_doc(root, case_id, "certificate_of_incorporation", {"cin": CIN})
    f = _card(client, analyst, root, case_id, "ID-05")
    assert f["outcome"] == "incomplete" and f["missing"] == ["Memorandum and articles of association"]
    assert _columns(f) == [("Certificate of incorporation", CIN, False)]
    assert _rows(f["columns"][0]) == [(["CIN", CIN], [(coi, 1)])]
    assert f["request"] == "the memorandum and articles of association"
    assert f["mismatch"] is None and f["reference"] is None
    assert _lines(f) == [("CIN", [("Certificate of incorporation", CIN, False)],
                          "the memorandum and articles of association needed")]

    moa = add_doc(root, case_id, "memorandum_articles_of_association", {"cin": OTHER_CIN}, page=2)
    f = _card(client, analyst, root, case_id, "ID-05")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Certificate of incorporation", CIN, True), ("Memorandum and articles of association", OTHER_CIN, True)]
    assert _rows(f["columns"][1]) == [(["CIN", OTHER_CIN], [(moa, 2)])] and f["columns"][1]["coverage"] == "Page 2"
    assert f["reference"] is None and f["request"] is None
    assert f["mismatch"] == ("2 different values: U28990MH2015PTC123456 (Certificate of incorporation); "
                             "U28990MH2015PTC123465 (Memorandum and articles of association).")
    _no_amount(f)
    assert _lines(f) == [("CIN", [("Certificate of incorporation", CIN, True),
                                  ("Memorandum and articles of association", OTHER_CIN, True)], None)]


def test_a_cin_in_the_sourcing_message_against_two_documents(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"cin": _person(OTHER_CIN)})
    add_doc(root, case_id, "certificate_of_incorporation", {"cin": CIN})
    add_doc(root, case_id, "memorandum_articles_of_association", {"cin": CIN})
    f = _card(client, analyst, root, case_id, "ID-05")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Certificate of incorporation", CIN, False), ("Memorandum and articles of association", CIN, False),
                           ("Sourcing message", OTHER_CIN, True)]
    # A person typed the CIN on the case: the column says so rather than point into the message.
    assert f["columns"][2]["coverage"] == "Entered on the case" and f["columns"][2]["provenance"] == ["declared"]
    assert f["columns"][2]["relies_on_manual"] and f["columns"][2]["evidence"] == []
    assert f["reference"] == CIN
    assert f["mismatch"] == "Sourcing message gives U28990MH2015PTC123465; the other 2 sources give U28990MH2015PTC123456."
    assert _lines(f) == [("CIN", [("2 documents", CIN, False), ("Sourcing message", OTHER_CIN, True)], None)]


# --- Two documents of one type: told apart by what each covers, else by page ---


def test_returns_and_audited_statements_are_told_apart_by_the_years_they_cover(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    later = add_doc(root, case_id, "income_tax_return", {"pan": PAN, "taxpayer_name": CO, "assessment_year": "2025-26"})
    earlier = add_doc(root, case_id, "income_tax_return", {"pan": PAN, "taxpayer_name": CO, "assessment_year": "2024-25"},
                      page=3)
    books = audited(root, case_id, "2026-03-31")
    other = audited(root, case_id, "2025-03-31", company_name=HERONBAY, page=2)
    f = _card(client, analyst, root, case_id, "ID-03")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Income tax return · AY 2025-26", CO, False), ("Income tax return · AY 2024-25", CO, False),
                           ("Audited financial statements · FY 2025-26", "Kestrel Tools Private Limited", False),
                           ("Audited financial statements · FY 2024-25", HERONBAY, True)]
    pages = [(later, 1), (earlier, 3), (books, 1), (other, 2)]
    assert [_rows(c) for c in f["columns"]] == [[(["Legal name", c["value"]], [p])] for c, p in zip(f["columns"], pages)]
    assert [c["coverage"] for c in f["columns"]] == ["Page 1", "Page 3", "Page 1", "Page 2"]
    # The difference in words names the documents by type, as the rule's explanation does.
    assert f["mismatch"] == ("Audited financial statements reads Heronbay Polymers Private Limited; "
                             "the other 3 sources read Kestrel Tools Pvt Ltd.")
    # The overview line names the odd document as its column does: by the year it covers.
    assert _lines(f) == [("Company name", [("3 documents", CO, False),
                                           ("Audited financial statements · FY 2024-25", HERONBAY, True)], None)]


def test_documents_of_one_type_covering_nothing_known_are_told_apart_by_page(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"pan": PAN}, page=2)
    add_doc(root, case_id, "company_pan", {"pan": PAN}, page=5)
    add_doc(root, case_id, "income_tax_return", {"pan": ITR_PAN})
    f = _card(client, analyst, root, case_id, "ID-01")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Company PAN · page 2", PAN, False), ("Company PAN · page 5", PAN, False),
                           ("Income tax return", ITR_PAN, True)]
    assert f["mismatch"] == "Income tax return gives AAACK9876Q; the other 2 sources give AAACK1234F."


def test_bank_statements_are_told_apart_by_account_then_by_the_months_they_cover(client, analyst, published_data_root):
    root = published_data_root
    year = [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 1_000_000}
            for ym in months((2025, 4), 12)]
    case_id = _case(client, analyst, root)
    bank(root, case_id, year, holder=CO)
    bank(root, case_id, year, last4="5678", bank_name="Harbourline Bank", holder=CO)
    add_doc(root, case_id, "company_pan", {"company_name": CO})
    f = _card(client, analyst, root, case_id, "ID-03")
    assert [c["label"] for c in f["columns"]] == [
        "Bank statement · Lotuscrest Bank ·1234", "Bank statement · Harbourline Bank ·5678", "Company PAN"]

    # Two statements of one account: the months of the credits read from each.
    other = _case(client, analyst, root, borrower=HERONBAY)
    bank(root, other, year[:6], holder=HERONBAY, end="2025-09-30")
    bank(root, other, year[6:], holder=HERONBAY, start="2025-10-01")
    add_doc(root, other, "company_pan", {"company_name": HERONBAY})
    f = _card(client, analyst, root, other, "ID-03")
    assert [c["label"] for c in f["columns"]] == [
        "Bank statement · Apr 2025 to Sep 2025", "Bank statement · Oct 2025 to Mar 2026", "Company PAN"]


# --- ID-04 promoter set: a column per source, a row per person ---


def test_a_promoter_missing_from_the_kyc_is_named_and_the_kyc_column_differs(client, analyst, published_data_root):
    root = published_data_root
    message = f"{CO} needs a term loan. Promoters: {TARUN}; {LEELA}."
    case_id = _case(client, analyst, root, message_text=message,
                    header={"promoters": {"value": f"{TARUN}; {LEELA}", "source": _span(message, f"{TARUN}; {LEELA}")}})
    kyc = add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    f = _card(client, analyst, root, case_id, "ID-04")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("KYC received", TARUN, True), ("Sourcing message", f"{TARUN}; {LEELA}", False)]
    received, said = f["columns"]
    assert received["row_columns"] == said["row_columns"] == ["Name", "DIN", "PAN"]
    assert _rows(received) == [([TARUN, TARUN_DIN, TARUN_PAN], [(kyc, 1)])]
    message_doc = _message_doc(root, case_id)
    assert _rows(said) == [([TARUN, None, None], [(message_doc, 1)]), ([LEELA, None, None], [(message_doc, 1)])]
    assert _pages(said["evidence"]) == [(message_doc, 1)]
    assert [c["provenance"] for c in f["columns"]] == [["borrower_supplied"], ["declared"]]
    assert [c["coverage"] for c in f["columns"]] == ["Page 1", "In the sourcing message"]
    assert f["mismatch"] == "Leela Varghese is not in KYC received."
    assert f["reference"] is None and f["request"] is None
    _no_amount(f)
    assert _lines(f) == [("Promoters", [], "Leela Varghese is not in KYC received")]


def test_promoters_across_three_sources_follow_the_rule_s_order_of_sources(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"promoters": _person(f"{TARUN}; {LEELA}")})
    report = add_doc(root, case_id, "commercial_bureau_report", {"related_parties": [
        {"name": TARUN, "relationship": "Director", "pan": TARUN_PAN},
        {"name": ISHITA, "relationship": "Director", "pan": ISHITA_PAN}]})
    kyc = add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    f = _card(client, analyst, root, case_id, "ID-04")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("KYC received", TARUN, True), ("Sourcing message", f"{TARUN}; {LEELA}", True),
                           ("Commercial bureau report", f"{TARUN}; {ISHITA}", True)]
    received, said, bureau = f["columns"]
    assert _rows(received) == [([TARUN, TARUN_DIN, TARUN_PAN], [(kyc, 1)])]
    assert _rows(said) == [([TARUN, None, None], []), ([LEELA, None, None], [])] and said["evidence"] == []
    assert _rows(bureau) == [([TARUN, None, TARUN_PAN], [(report, 1)]), ([ISHITA, None, ISHITA_PAN], [(report, 1)])]
    assert _pages(bureau["evidence"]) == [(report, 1)]
    assert [c["provenance"] for c in f["columns"]] == [["borrower_supplied"], ["declared"], ["independent"]]
    assert [c["coverage"] for c in f["columns"]] == ["Page 1", "Entered on the case", "Page 1"]
    assert f["explanation"] == ("The promoters named differ between sources: Leela Varghese has no KYC on file "
                                "and is not named in the commercial bureau report; Ishita Barve has no KYC on "
                                "file and is not named in the sourcing message.")
    assert f["mismatch"] == ("Leela Varghese is not in KYC received and Commercial bureau report; "
                             "Ishita Barve is not in KYC received and Sourcing message.")
    assert _lines(f) == [("Promoters", [], "Leela Varghese is not in KYC received and Commercial bureau report; "
                                           "Ishita Barve is not in KYC received and Sourcing message")]


def test_the_same_promoters_everywhere_pass(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"promoters": _person(f"{TARUN}; {ISHITA}")})
    first = add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    second = add_doc(root, case_id, "director_kyc", {"person_name": ISHITA, "din": ISHITA_DIN, "pan": ISHITA_PAN})
    f = _card(client, analyst, root, case_id, "ID-04")
    assert f["outcome"] == "pass"
    assert _columns(f) == [("KYC received", f"{TARUN}; {ISHITA}", False), ("Sourcing message", f"{TARUN}; {ISHITA}", False)]
    received = f["columns"][0]
    assert _rows(received) == [([TARUN, TARUN_DIN, TARUN_PAN], [(first, 1)]), ([ISHITA, ISHITA_DIN, ISHITA_PAN], [(second, 1)])]
    assert received["coverage"] == "2 documents" and _pages(received["evidence"]) == [(first, 1), (second, 1)]
    assert f["mismatch"] is None and f["reference"] is None and f["request"] is None
    _no_amount(f)
    assert _lines(f) == [("Promoters", [], "the same 2 people in 2 sources")]


def test_promoters_named_only_in_the_sourcing_message_ask_for_the_kyc(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"promoters": _person(f"{TARUN}; {ISHITA}")})
    f = _card(client, analyst, root, case_id, "ID-04")
    assert f["outcome"] == "incomplete" and f["missing"] == ["Director KYC"]
    assert _columns(f) == [("Sourcing message", f"{TARUN}; {ISHITA}", False)]
    assert f["request"] == "the director KYC" and f["mismatch"] is None
    _no_amount(f)
    assert _lines(f) == [("Promoters", [], "the director KYC needed")]


# --- ID-06 director identifiers ---


def test_a_director_s_din_and_pan_that_disagree_are_put_in_words(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"pan": PAN})
    moa = add_doc(root, case_id, "memorandum_articles_of_association",
               {"directors": [{"name": TARUN, "din": TARUN_DIN}, {"name": ISHITA, "din": ISHITA_DIN}]}, page=5)
    first = add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    second = add_doc(root, case_id, "director_kyc", {"person_name": ISHITA, "din": "07654300", "pan": PAN})
    f = _card(client, analyst, root, case_id, "ID-06")
    assert f["outcome"] == "fail"
    assert _columns(f) == [
        ("Memorandum and articles", f"{TARUN} (DIN {TARUN_DIN}); {ISHITA} (DIN {ISHITA_DIN})", True),
        ("KYC received", f"{TARUN} (DIN {TARUN_DIN}, PAN {TARUN_PAN}); {ISHITA} (DIN 07654300, PAN {PAN})", True)]
    memorandum, received = f["columns"]
    assert _rows(memorandum) == [([TARUN, TARUN_DIN, None], [(moa, 5)]), ([ISHITA, ISHITA_DIN, None], [(moa, 5)])]
    assert _rows(received) == [([TARUN, TARUN_DIN, TARUN_PAN], [(first, 1)]), ([ISHITA, "07654300", PAN], [(second, 1)])]
    assert [c["coverage"] for c in f["columns"]] == ["Page 5", "2 documents"]
    assert all(c["row_columns"] == ["Name", "DIN", "PAN"] and c["provenance"] == ["borrower_supplied"] for c in f["columns"])
    assert f["mismatch"] == ("Ishita Barve: DIN 07654300 on the KYC against 07654321 in the memorandum; "
                             "PAN AAACK1234F is not an individual's PAN.")
    assert f["reference"] is None
    _no_amount(f)
    assert _lines(f) == [("Director identifiers", [], "Ishita Barve: DIN 07654300 on the KYC against 07654321 in the "
                                                      "memorandum; PAN AAACK1234F is not an individual's PAN")]


def test_a_kyc_carrying_the_company_s_pan_is_put_in_words(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"pan": TARUN_PAN})
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "pan": TARUN_PAN})
    f = _card(client, analyst, root, case_id, "ID-06")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("KYC received", f"{TARUN} (DIN —, PAN {TARUN_PAN})", True)]
    assert f["mismatch"] == "Tarun Velankar: PAN ABCPV1234K is the company's PAN."


def test_director_identifiers_that_agree_pass_and_none_printed_is_not_applicable(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "memorandum_articles_of_association", {"directors": [{"name": TARUN, "din": TARUN_DIN}]})
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    f = _card(client, analyst, root, case_id, "ID-06")
    assert f["outcome"] == "pass"
    assert [c["differs"] for c in f["columns"]] == [False, False] and f["mismatch"] is None
    assert _lines(f) == [("Director identifiers", [], "identifiers agree for 1 director")]

    other = _case(client, analyst, root, borrower=HERONBAY)
    add_doc(root, other, "memorandum_articles_of_association", {"directors": [{"name": SUNIL}]})
    kyc = add_doc(root, other, "director_kyc", {"person_name": SUNIL})
    f = _card(client, analyst, root, other, "ID-06")
    assert f["outcome"] == "not_applicable"
    assert _columns(f) == [("Memorandum and articles", f"{SUNIL} (DIN —)", False),
                           ("KYC received", f"{SUNIL} (DIN —, PAN —)", False)]
    assert _rows(f["columns"][1]) == [([SUNIL, None, None], [(kyc, 1)])]
    assert f["mismatch"] is None and f["request"] is None and f["highlights"] == []


# --- ID-07 the CIN against the incorporation particulars ---


def test_the_cin_s_year_against_the_certificate_is_put_in_words(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    coi = add_doc(root, case_id, "certificate_of_incorporation", {"cin": CIN, "date_of_incorporation": "2016-05-01"}, page=2)
    f = _card(client, analyst, root, case_id, "ID-07")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("CIN (Certificate of incorporation)", CIN, True), ("Date of incorporation", "2016-05-01", True),
                           ("Constitution on the case", "Private limited", True)]
    cin, born, constitution = f["columns"]
    # The particulars the CIN encodes, each read from the certificate's page.
    assert cin["row_columns"] == ["Particular", "In the CIN"]
    assert _rows(cin) == [(["Year of incorporation", "2015"], [(coi, 2)]),
                          (["Company class", "Private limited company (PTC)"], [(coi, 2)]),
                          (["Listing", "Unlisted"], [(coi, 2)])]
    # A date for the board to format, as the other cards give one; the row reads it.
    assert [c["unit"] for c in f["columns"]] == ["text", "date", "text"]
    assert _rows(born) == [(["Date of incorporation", "1 May 2016"], [(coi, 2)])] and born["coverage"] == "Page 2"
    assert [c["provenance"] for c in (cin, born)] == [["borrower_supplied"], ["borrower_supplied"]]
    # The constitution is the case's own record: no document, no page.
    assert _rows(constitution) == [(["Constitution", "Private limited"], [])]
    assert constitution["evidence"] == [] and constitution["provenance"] == [] and constitution["coverage"] == "Set on the case"
    assert f["mismatch"] == "Year of incorporation 2015 in the CIN against 2016 on file."
    assert f["reference"] is None
    _no_amount(f)
    assert _lines(f) == [("CIN particulars", [], "year of incorporation 2015 in the CIN against 2016 on file")]


def test_the_cin_s_class_and_listing_against_the_constitution_are_put_in_words(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "certificate_of_incorporation", {"cin": "L28990MH2015PLC123456", "date_of_incorporation": "2015-06-01"})
    f = _card(client, analyst, root, case_id, "ID-07")
    assert f["outcome"] == "fail"
    assert [r["cells"] for r in f["columns"][0]["rows"]] == [
        ["Year of incorporation", "2015"], ["Company class", "Public limited company (PLC)"], ["Listing", "Listed"]]
    assert f["mismatch"] == ("Company class Public limited company (PLC) in the CIN against Private limited on file; "
                             "listing Listed in the CIN against Unlisted (private company) on file.")
    # Every particular held against the CIN, however many: there are at most three.
    assert _lines(f) == [("CIN particulars", [], "company class Public limited company (PLC) in the CIN against Private "
                                                 "limited on file; listing Listed in the CIN against Unlisted (private "
                                                 "company) on file")]


def test_a_cin_that_agrees_passes_and_one_out_of_format_is_not_applicable(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "certificate_of_incorporation", {"cin": CIN, "date_of_incorporation": "2015-06-01"})
    f = _card(client, analyst, root, case_id, "ID-07")
    assert f["outcome"] == "pass"
    assert _columns(f) == [("CIN (Certificate of incorporation)", CIN, False), ("Date of incorporation", "2015-06-01", False),
                           ("Constitution on the case", "Private limited", False)]
    assert f["mismatch"] is None
    assert _lines(f) == [("CIN particulars", [], "agrees with 3 particulars on file")]

    other = _case(client, analyst, root, borrower=HERONBAY)
    coi = add_doc(root, other, "certificate_of_incorporation", {"cin": "U28990MH2015"})
    f = _card(client, analyst, root, other, "ID-07")
    assert f["outcome"] == "not_applicable"
    assert _columns(f) == [("CIN (Certificate of incorporation)", "U28990MH2015", False)]
    assert _rows(f["columns"][0]) == [(["CIN", "U28990MH2015"], [(coi, 1)])]
    assert f["columns"][0]["row_columns"] == ["Field", "Value"]
    assert f["mismatch"] is None and f["request"] is None and f["highlights"] == []


# --- ID-08 memorandum directors ---


def test_a_director_in_the_memorandum_with_no_kyc_is_put_in_words(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"promoters": _person(f"{TARUN}; {LEELA}")})
    moa = add_doc(root, case_id, "memorandum_articles_of_association",
               {"directors": [{"name": TARUN, "din": TARUN_DIN}, {"name": SUNIL, "din": SUNIL_DIN}]})
    kyc = add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    f = _card(client, analyst, root, case_id, "ID-08")
    assert f["outcome"] == "fail"
    assert _columns(f) == [("Memorandum and articles", f"{TARUN}; {SUNIL}", True), ("KYC received", TARUN, False),
                           ("Sourcing message", f"{TARUN}; {LEELA}", False)]
    memorandum, received, said = f["columns"]
    assert _rows(memorandum) == [([TARUN, TARUN_DIN, None], [(moa, 1)]), ([SUNIL, SUNIL_DIN, None], [(moa, 1)])]
    assert _rows(received) == [([TARUN, TARUN_DIN, TARUN_PAN], [(kyc, 1)])]
    assert _rows(said) == [([TARUN, None, None], []), ([LEELA, None, None], [])]
    assert [c["provenance"] for c in f["columns"]] == [["borrower_supplied"], ["borrower_supplied"], ["declared"]]
    assert f["mismatch"] == "Sunil Karve in the memorandum has no KYC and is not named in the sourcing message."
    _no_amount(f)
    assert _lines(f) == [("Directors in the memorandum", [], "Sunil Karve has no KYC and is not named in the sourcing message")]


def test_directors_in_the_memorandum_with_no_kyc_are_put_in_words(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "memorandum_articles_of_association", {"directors": [{"name": TARUN}, {"name": LEELA}, {"name": SUNIL}]})
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN})
    f = _card(client, analyst, root, case_id, "ID-08")
    assert f["outcome"] == "fail"
    assert f["mismatch"] == ("Leela Varghese and Sunil Karve in the memorandum have no KYC and "
                             "are not named in the sourcing message.")
    assert _lines(f) == [("Directors in the memorandum", [],
                          "Leela Varghese and Sunil Karve have no KYC and are not named in the sourcing message")]


def test_a_director_named_in_two_memoranda_is_named_once(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    first = add_doc(root, case_id, "memorandum_articles_of_association", {"directors": [{"name": TARUN}, {"name": SUNIL}]})
    second = add_doc(root, case_id, "memorandum_articles_of_association", {"directors": [{"name": SUNIL}]}, page=2)
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN})
    f = _card(client, analyst, root, case_id, "ID-08")
    assert f["outcome"] == "fail"
    memorandum = f["columns"][0]
    assert _rows(memorandum) == [([TARUN, None, None], [(first, 1)]), ([SUNIL, None, None], [(first, 1)]),
                                 ([SUNIL, None, None], [(second, 2)])]
    assert memorandum["coverage"] == "2 documents" and _pages(memorandum["evidence"]) == [(first, 1), (second, 2)]
    assert f["mismatch"] == "Sunil Karve in the memorandum has no KYC and is not named in the sourcing message."


def test_directors_accounted_for_pass_and_a_memorandum_alone_asks_for_the_kyc(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"promoters": _person(ISHITA)})
    add_doc(root, case_id, "memorandum_articles_of_association", {"directors": [{"name": TARUN}, {"name": ISHITA}]})
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN})
    f = _card(client, analyst, root, case_id, "ID-08")
    assert f["outcome"] == "pass"
    assert _columns(f) == [("Memorandum and articles", f"{TARUN}; {ISHITA}", False), ("KYC received", TARUN, False),
                           ("Sourcing message", ISHITA, False)]
    assert f["mismatch"] is None
    assert _lines(f) == [("Directors in the memorandum", [], "both accounted for")]

    other = _case(client, analyst, root, borrower=HERONBAY)
    add_doc(root, other, "memorandum_articles_of_association", {"directors": [{"name": SUNIL}]})
    f = _card(client, analyst, root, other, "ID-08")
    assert f["outcome"] == "incomplete" and f["missing"] == ["Director KYC"]
    assert _columns(f) == [("Memorandum and articles", SUNIL, False)]
    assert f["request"] == "the director KYC" and f["mismatch"] is None
    assert _lines(f) == [("Directors in the memorandum", [], "the director KYC needed")]


# --- Checks short of documents ---


def test_each_identity_check_short_of_documents_asks_for_the_documents_it_names(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    card = add_doc(root, case_id, "company_pan", {"pan": PAN})
    found = _cards(client, analyst, root, case_id)
    [pan] = found["ID-01"]
    assert pan["outcome"] == "incomplete" and pan["missing"] == ["Income tax return", "GSTR-3B"]
    assert _columns(pan) == [("Company PAN", PAN, False)] and _rows(pan["columns"][0]) == [(["PAN", PAN], [(card, 1)])]
    requests = {rule: fs[0]["request"] for rule, fs in found.items() if rule.startswith("ID-")}
    assert requests == {
        "ID-01": "the income tax return and the GSTR-3B",
        "ID-02": "the GSTR-3B",
        "ID-03": ("the certificate of incorporation, the memorandum and articles of association, the board resolution for "
                  "borrowing, the income tax return, the GSTR-3B, the audited financial statements and the bank statement"),
        "ID-04": "the director KYC",
        "ID-05": "the certificate of incorporation and the memorandum and articles of association",
        "ID-06": "the director KYC and the memorandum and articles of association",
        "ID-07": "the certificate of incorporation",
        "ID-08": "the memorandum and articles of association and the director KYC",
        "ID-09": "the director KYC and the memorandum and articles of association",
    }
    for rule, fs in found.items():
        if rule.startswith("ID-"):
            assert fs[0]["outcome"] == "incomplete" and fs[0]["mismatch"] is None and fs[0]["reference"] is None
            _no_amount(fs[0])
            # Each check's line on the overview card says what would complete it.
            [(label, _facts, note)] = _lines(fs[0])
            assert (label, note) == (LABELS[rule], f"{requests[rule]} needed"), rule
    # With the values so far.
    assert _lines(pan) == [("PAN", [("Company PAN", PAN, False)], "the income tax return and the GSTR-3B needed")]


# --- Values that end with a full stop, values typed on the case, and lines that count the rest ---


def test_a_name_ending_with_a_full_stop_takes_no_second_one(client, analyst, published_data_root):
    root = published_data_root
    dotted, other = "Kestrel Tools Pvt. Ltd.", "Heronbay Polymers Pvt. Ltd."
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"pan": PAN, "company_name": dotted})
    add_doc(root, case_id, "certificate_of_incorporation", {"company_name": dotted})
    add_doc(root, case_id, "audited_financial_statements", {"company_name": other})
    f = _card(client, analyst, root, case_id, "ID-03")
    assert f["outcome"] == "fail" and f["reference"] == dotted
    assert f["mismatch"] == ("Audited financial statements reads Heronbay Polymers Pvt. Ltd.; "
                             "the other 2 sources read Kestrel Tools Pvt. Ltd.")
    assert _lines(f) == [("Company name", [("2 documents", dotted, False), ("Audited financial statements", other, True)],
                          None)]

    # Every value named, the last ending with its own full stop: the sentence closes once.
    two = _case(client, analyst, root, borrower=HERONBAY)
    add_doc(root, two, "audited_financial_statements", {"company_name": other})
    add_doc(root, two, "company_pan", {"company_name": dotted})
    f = _card(client, analyst, root, two, "ID-03")
    assert f["mismatch"] == ("2 different values: Heronbay Polymers Pvt. Ltd. (Audited financial statements); "
                             "Kestrel Tools Pvt. Ltd. (Company PAN).")


def test_a_value_typed_on_the_case_says_so_and_one_read_from_the_message_says_where(client, analyst,
                                                                                    published_data_root):
    root = published_data_root
    message = f"{CO}, PAN {PAN}, needs a term loan for a new press line."
    case_id = _case(client, analyst, root, message_text=message, header={
        "pan": {"value": PAN, "source": _span(message, PAN)}, "gstin": _person("27AAACK1234F1Z0")})
    add_doc(root, case_id, "company_pan", {"pan": PAN})
    add_doc(root, case_id, "income_tax_return", {"pan": PAN})
    returns = [gstr(root, case_id, p, 4_000_000) for p in ("April 2025", "May 2025", "June 2025")]
    add_doc(root, case_id, "commercial_bureau_report", {"pan": BUREAU_PAN})
    found = _cards(client, analyst, root, case_id)
    # Read from the message: the group counts it as the sourcing message.
    [pan] = found["ID-01"]
    agree, odd = pan["columns"]
    assert agree["coverage"] == "5 documents and the sourcing message" and odd["coverage"] == "Page 1"
    assert _lines(pan) == [("PAN", [("5 documents and the sourcing message", PAN, False),
                                    ("Commercial bureau report", BUREAU_PAN, True)], None)]
    # Typed by a person: it has no place in the message, and its column says it was entered on the case.
    [gstin] = found["ID-02"]
    assert gstin["outcome"] == "pass" and len(returns) == 3
    assert [(c["label"], c["coverage"]) for c in gstin["columns"]] == [
        ("GSTR-3B · Apr 2025", "Page 1"), ("GSTR-3B · May 2025", "Page 1"), ("GSTR-3B · Jun 2025", "Page 1"),
        ("Sourcing message", "Entered on the case")]
    assert _lines(gstin) == [("GSTIN", [("4 sources", "27AAACK1234F1Z0", False)], "same across 4 sources")]

    # A typed value in a group of documents is counted as an entry on the case.
    typed = _case(client, analyst, root, borrower=HERONBAY, header={"pan": _person(PAN)})
    add_doc(root, typed, "company_pan", {"pan": PAN})
    add_doc(root, typed, "income_tax_return", {"pan": PAN})
    add_doc(root, typed, "gstr_3b", {"gstin": "27AAACK1234F1Z0"})
    add_doc(root, typed, "commercial_bureau_report", {"pan": BUREAU_PAN})
    pan = _card(client, analyst, root, typed, "ID-01")
    assert [c["coverage"] for c in pan["columns"]] == ["3 documents and an entry on the case", "Page 1"]
    assert _lines(pan) == [("PAN", [("3 documents and an entry on the case", PAN, False),
                                    ("Commercial bureau report", BUREAU_PAN, True)], None)]


def test_a_line_names_two_people_and_counts_the_rest(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"promoters": _person(f"{TARUN}; {LEELA}; {SUNIL}; {ISHITA}")})
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    f = _card(client, analyst, root, case_id, "ID-04")
    assert f["mismatch"] == ("Leela Varghese is not in KYC received; Sunil Karve is not in KYC received; "
                             "Ishita Barve is not in KYC received.")
    assert _lines(f) == [("Promoters", [], "Leela Varghese is not in KYC received; Sunil Karve is not in KYC received; "
                                           "and 1 more")]

    other = _case(client, analyst, root, borrower=HERONBAY)
    add_doc(root, other, "memorandum_articles_of_association",
            {"directors": [{"name": TARUN}, {"name": LEELA}, {"name": SUNIL}, {"name": ISHITA}]})
    add_doc(root, other, "director_kyc", {"person_name": TARUN})
    f = _card(client, analyst, root, other, "ID-08")
    assert f["mismatch"] == ("Leela Varghese, Sunil Karve and Ishita Barve in the memorandum have no KYC and "
                             "are not named in the sourcing message.")
    assert _lines(f) == [("Directors in the memorandum", [],
                          "Leela Varghese, Sunil Karve and 1 other have no KYC and are not named in the sourcing message")]


# --- The guard: a card is presentation only ---


def _every_identity_check_failing(client: TestClient, analyst: dict, root: Path) -> str:
    message = f"{CO}, PAN {PAN}, needs a term loan. Promoters: {TARUN}; {LEELA}."
    case_id = _case(client, analyst, root, message_text=message, header={
        "pan": {"value": PAN, "source": _span(message, PAN)},
        "promoters": {"value": f"{TARUN}; {LEELA}", "source": _span(message, f"{TARUN}; {LEELA}")}})
    add_doc(root, case_id, "company_pan", {"pan": PAN, "company_name": CO})
    add_doc(root, case_id, "income_tax_return", {"pan": ITR_PAN, "taxpayer_name": "KESTREL TOOLS PRIVATE LIMITED"})
    add_doc(root, case_id, "gstr_3b", {"gstin": "27AAACX9999Q1Z3", "legal_name": HERONBAY, "tax_period": "April 2025"})
    add_doc(root, case_id, "commercial_bureau_report", {
        "company_name": CO, "pan": BUREAU_PAN, "gstin": "29AAACK1234F1Z5",
        "related_parties": [{"name": TARUN, "relationship": "Director", "pan": TARUN_PAN},
                            {"name": ISHITA, "relationship": "Director", "pan": ISHITA_PAN}]})
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": TARUN_DIN, "pan": TARUN_PAN})
    add_doc(root, case_id, "director_kyc", {"person_name": ISHITA, "din": "07654300", "pan": ISHITA_PAN})
    add_doc(root, case_id, "memorandum_articles_of_association", {"cin": OTHER_CIN, "directors": [
        {"name": TARUN, "din": TARUN_DIN}, {"name": ISHITA, "din": ISHITA_DIN}, {"name": SUNIL, "din": SUNIL_DIN}]})
    add_doc(root, case_id, "certificate_of_incorporation", {"cin": CIN, "date_of_incorporation": "2016-05-01",
                                                        "company_name": "Kestrel Tools Private Limited"})
    return case_id


def test_the_cards_never_change_a_finding(client, analyst, published_data_root, monkeypatch):
    root = published_data_root
    case_id = _every_identity_check_failing(client, analyst, root)
    conn = db.connect(root)
    try:
        case = cases.get_case(conn, case_id)
        with_cards = crosschecks.evaluate(root, case, facts.compute(conn, root, case))
        monkeypatch.setattr(xv_cards, "BUILDERS", {})
        without = crosschecks.evaluate(root, case, facts.compute(conn, root, case))
    finally:
        conn.close()
    identity = {f.rule_id: f for f in with_cards if f.area == "identity"}
    assert sorted(identity) == [f"ID-0{n}" for n in range(1, 10)]
    # The scenario makes ID-01 to ID-08 fail (ID-09, names in full, gives what it gives).
    eight = {rule: f for rule, f in identity.items() if rule != "ID-09"}
    assert {f.outcome for f in eight.values()} == {"fail"}
    # The identity builders ran (a mismatch in words, a line for the overview card) and did not run with
    # the registry emptied.
    assert all(f.mismatch for f in eight.values()) and not any(f.mismatch for f in without)
    assert all(f.highlights for f in eight.values()) and not any(f.highlights for f in without)
    # Outcome, explanation, sides, detail, missing list, query, tolerance, severity, blocking: all the rule's.
    assert [f.model_dump(exclude=CARD) for f in with_cards] == [f.model_dump(exclude=CARD) for f in without]
