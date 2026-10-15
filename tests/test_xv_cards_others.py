"""The cards of the bank-account, obligation and board-resolution checks on the cross-verification
board (F-19.3; BA-01, BA-02, OB-01 to OB-03, BR-01 to BR-04): each source compared as a column,
with the rows read behind it and the page each came from; the gap on each leg; for a check
without an amount the difference in words; for an incomplete check what would complete it; the
key-figure lines for the area's overview card (a line per account or lender problem).

A card is presentation: the last test holds every outcome, explanation, side, detail and missing
list identical with the card builders and without them. BR-01 to BR-04 are switched off in
configuration: their tests switch every rule on (all_rules_enabled). Every name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cases, crosschecks, db, facts, pipeline, xv_cards
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, months

CO = "Kestrel Tools Private Limited"
TIDEWATER = {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12_000_000,
             "outstanding": 7_500_000, "emi": 250_000}
LOTUSCREST = {"lender": "Lotuscrest Bank", "facility": "Cash credit", "sanctioned_amount": 20_000_000,
              "outstanding": 18_500_000}
EMI = "NACH DR TIDEWATER FIN EMI 000123"
MINE = {"BA-01", "BA-02", "OB-01", "OB-02", "OB-03", "BR-01", "BR-02", "BR-03", "BR-04"}
NOT_DOCUMENTS = {"application_message"}
"""A source that is the case's own record, not a document with pages."""


# --- Documents with known values ---


def declaration(root: Path, case_id: str, facilities=(), accounts=(), *, page: int = 2) -> str:
    return add_doc(root, case_id, "existing_facilities_declaration", {
        "company_name": CO, "declaration_date": "2026-09-15", "facilities": list(facilities),
        "bank_accounts": [{"bank": b, "account_number": n, "account_type": "Current account"} for b, n in accounts]},
        page=page)


def statement(root: Path, case_id: str, transactions=(), *, last4: str = "1234", page: int = 3) -> str:
    return add_doc(root, case_id, "bank_statement", {
        "account_holder_name": "Kestrel Tools Pvt Ltd", "account_number": f"90100000{last4}", "bank_name": "Lotuscrest Bank",
        "statement_period_start": "2025-04-01", "statement_period_end": "2026-03-31",
        "transactions": list(transactions)}, page=page)


def instalments(narration: str = EMI, amount: int = 250_000) -> list[dict]:
    return [{"date": f"{ym}-10", "description": narration, "debit": amount} for ym in months((2025, 4), 6)]


def sanction(root: Path, case_id: str, lender: str, amount: int, emi: int | None = None, *, page: int = 4) -> str:
    facility = {"facility": "Term loan", "sanctioned_amount": amount, **({"emi": emi} if emi else {})}
    return add_doc(root, case_id, "sanction_letter", {"lender_name": lender, "borrower_name": CO,
                                                      "sanction_date": "2024-04-12", "facilities": [facility]}, page=page)


def bureau(root: Path, case_id: str, facilities=(), *, page: int = 5) -> str:
    return add_doc(root, case_id, "commercial_bureau_report", {
        "company_name": CO, "pan": "AAACK1234F", "report_date": "2026-09-20",
        "credit_facilities": [{**f, "overdue": 0, "status": "Standard"} for f in facilities]}, page=page)


def resolution(root: Path, case_id: str, *, page: int = 7, pending: set[str] | None = None, **fields) -> str:
    return add_doc(root, case_id, "board_resolution_borrowing", fields, page=page, pending=pending)


# --- Reading the board ---


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _holds(f: dict) -> None:
    """What every card of these rules keeps to."""
    breached = [g for g in f["gaps"] if g["breached"]]
    if f["outcome"] == "fail":
        assert breached or f["mismatch"], f"{f['rule_id']}: a discrepancy shows no breached leg and no difference"
    elif f["outcome"] == "pass":
        assert not breached and not f["mismatch"], f"{f['rule_id']}: a pass shows a breach"
    else:
        assert not f["gaps"] and f["amount"] is None and not f["mismatch"] and not f["gap_tolerance"], f["rule_id"]
    if f["outcome"] != "incomplete":
        assert f["request"] is None, f["rule_id"]
    # A reference value is an identifier check's; these rules compare no identifier.
    assert f["reference"] is None and len(f["columns"]) <= 4
    for c in f["columns"]:
        assert c["label"] and c["provenance"] == list(dict.fromkeys(c["provenance"]))
        traced = [r["evidence"][0] for r in c["rows"] if r["evidence"]]
        if traced:
            assert c["evidence"] and c["evidence"][0] == traced[0], f"{f['rule_id']} {c['label']}"
        documents = [s for s in c["sources"] if "." not in s and s not in NOT_DOCUMENTS]
        if documents and set(c["sources"]) <= set(documents):
            # Every row of a column a document backs carries that document and its page.
            for r in c["rows"]:
                assert r["evidence"], f"{f['rule_id']} {c['label']}: row {r['cells']} has no page"
                assert all(e["document_id"] and e["page"] >= 1 for e in r["evidence"])


def _board(client: TestClient, headers: dict, root: Path, case_id: str) -> dict[str, list[dict]]:
    _refresh(root, case_id)
    response = client.get(f"/api/cases/{case_id}/cross-verification", headers=headers)
    assert response.status_code == 200, response.text
    out: dict[str, list[dict]] = {}
    for item in response.json()["items"]:
        out.setdefault(item["finding"]["rule_id"], []).append(item["finding"])
    for rule in MINE:
        for f in out.get(rule, []):
            _holds(f)
    return out


def _one(board: dict[str, list[dict]], rule: str) -> dict:
    [f] = board[rule]
    return f


def _column(f: dict, key: str) -> dict:
    return next(c for c in f["columns"] if c["key"] == key)


def _pages(evidence: list[dict]) -> list[tuple[str, int]]:
    return [(e["document_id"], e["page"]) for e in evidence]


def _rows(c: dict) -> list[tuple[list, list[tuple[str, int]]]]:
    return [(r["cells"], _pages(r["evidence"])) for r in c["rows"]]


def _gaps(f: dict) -> list[tuple]:
    return [(g["label"], g["amount"], g["pct"], g["base"], g["legs"], g["breached"]) for g in f["gaps"]]


def _lines(f: dict) -> list[tuple]:
    """The finding's key-figure lines for the overview card: label, facts (label, value, differs), note.
    Each names its finding, rule and outcome; the figures are sanctioned amounts, in rupees."""
    for h in f["highlights"]:
        assert (h["finding_id"], h["rule_id"], h["outcome"]) == (f["id"], f["rule_id"], f["outcome"])
        assert all(x["unit"] == "inr" for x in h["facts"])
    return [(h["label"], [(x["label"], x["value"], x["differs"]) for x in h["facts"]], h["note"]) for h in f["highlights"]]


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, analyst: dict, root: Path, **overrides) -> str:
    return make_case(client, analyst, root, **{"borrower": "Kestrel Tools Pvt Ltd", **overrides})


# --- Bank accounts (BA-01, BA-02) ---


def test_account_cards_show_each_account_where_it_appears(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    decl = declaration(root, case_id, accounts=[("Lotuscrest Bank", "901000001234"), ("Lotuscrest Bank", "901000005678")])
    main = statement(root, case_id, [{"date": "2025-05-02", "description": "NEFT TRANSFER TO A/C 778899001122",
                                      "debit": 500_000}], page=3)
    other = statement(root, case_id, last4="7777", page=4)
    board = _board(client, analyst, root, case_id)

    ba1 = _one(board, "BA-01")
    assert ba1["outcome"] == "fail"
    assert [c["key"] for c in ba1["columns"]] == ["declared", "statements"]
    assert [c["label"] for c in ba1["columns"]] == ["Declared accounts", "Statements on file"]
    assert [c["provenance"] for c in ba1["columns"]] == [["declared"], ["borrower_supplied"]]
    assert [c["differs"] for c in ba1["columns"]] == [False, True]
    declared, statements = ba1["columns"]
    assert declared["value"] == "Lotuscrest Bank ·1234, Lotuscrest Bank ·5678" and declared["coverage"] == "2 accounts declared"
    assert declared["row_columns"] == ["Account", "Where it appears"]
    # A declared row opens the declaration, even for an account that also has a statement.
    assert _rows(declared) == [(["Lotuscrest Bank ·1234", "Declaration of existing facilities"], [(decl, 2)]),
                               (["Lotuscrest Bank ·5678", "Declaration of existing facilities"], [(decl, 2)])]
    assert _pages(declared["evidence"]) == [(decl, 2)]
    # A statement row opens the statement's own page.
    assert statements["coverage"] == "Statements for 2 accounts"
    assert _rows(statements) == [(["Lotuscrest Bank ·1234", "Bank statement"], [(main, 3)]),
                                 (["Lotuscrest Bank ·7777", "Bank statement"], [(other, 4)])]
    assert _pages(statements["evidence"]) == [(main, 3), (other, 4)]
    assert ba1["mismatch"] == "Lotuscrest Bank ·5678 was declared but has no statement."
    assert ba1["gaps"] == [] and ba1["amount"] is None and ba1["reference"] is None and ba1["request"] is None
    # A line per account flagged, named as the card names it.
    assert _lines(ba1) == [("Lotuscrest Bank ·5678", [], "declared, no statement")]

    ba2 = _one(board, "BA-02")
    assert ba2["outcome"] == "fail"
    assert [c["key"] for c in ba2["columns"]] == ["declared", "statements", "transfers"]
    assert [c["differs"] for c in ba2["columns"]] == [False, True, True]
    transfers = _column(ba2, "transfers")
    assert transfers["label"] == "Seen in transfers" and transfers["value"] == "Account ·1122"
    assert transfers["coverage"] == "1 account named in transfer narrations"
    # The transfer row opens the statement page the narration was read from.
    assert _rows(transfers) == [(["Account ·1122", "Transfer in Lotuscrest Bank ·1234"], [(main, 3)])]
    assert ba2["mismatch"] == ("Lotuscrest Bank ·7777 has a statement but was not declared; Account ·1122 appears only "
                               "in a transfer, with no statement and no declaration.")
    assert ba2["gaps"] == [] and ba2["amount"] is None
    assert _lines(ba2) == [("Lotuscrest Bank ·7777", [], "statement, not declared"),
                           ("Account ·1122", [], "seen only in transfers")]


def test_account_cards_for_accounts_declared_in_the_sourcing_message(client, analyst, published_data_root):
    root = published_data_root
    note = "Current account with Lotuscrest Bank a/c 90100001234"
    # Declared in the declaration and in the sourcing message, with its statement.
    both = _case(client, analyst, root, header={"existing_banking": {"value": note, "source": "person"}})
    decl = declaration(root, both, accounts=[("Lotuscrest Bank", "901000001234")])
    main = statement(root, both)
    board = _board(client, analyst, root, both)
    ba1 = _one(board, "BA-01")
    assert ba1["outcome"] == "pass" and ba1["mismatch"] is None and ba1["gaps"] == []
    declared = _column(ba1, "declared")
    assert declared["label"] == "Declared accounts"
    assert declared["sources"] == ["existing_facilities_declaration", "application_message"]
    assert declared["provenance"] == ["declared"]
    assert _rows(declared) == [(["Lotuscrest Bank ·1234", "Declaration of existing facilities; Sourcing message"],
                                [(decl, 2)])]
    assert _rows(_column(ba1, "statements")) == [(["Lotuscrest Bank ·1234", "Bank statement"], [(main, 3)])]
    assert _one(board, "BA-02")["outcome"] == "pass" and _one(board, "BA-02")["mismatch"] is None
    # On a pass, what each rule confirmed.
    assert _lines(ba1) == [("1 declared account", [], "with a statement")]
    assert _lines(_one(board, "BA-02")) == [("1 account on file", [], "declared")]

    # Declared only in the sourcing message: the RM's note, as written, entered by a person (no page).
    message = _case(client, analyst, root, borrower="Heronbay",
                    header={"existing_banking": {"value": note, "source": "person"}})
    statement(root, message)
    ba1 = _one(_board(client, analyst, root, message), "BA-01")
    assert ba1["outcome"] == "pass"
    declared = _column(ba1, "declared")
    assert declared["label"] == "Declared in the sourcing message" and declared["value"] == note
    assert declared["sources"] == ["application_message"] and declared["provenance"] == ["declared"]
    assert declared["coverage"] == "1 account declared"
    assert _rows(declared) == [(["Lotuscrest Bank ·1234", "Sourcing message"], [])]

    # Two statements and nothing declared: BA-02 has nothing to hold them against, and says what it found.
    nothing = _case(client, analyst, root, borrower="Heronbay", duplicate_override_reason="A third scenario")
    statement(root, nothing)
    statement(root, nothing, last4="7777", page=4)
    board = _board(client, analyst, root, nothing)
    assert _one(board, "BA-01")["outcome"] == "not_applicable" and _one(board, "BA-01")["highlights"] == []
    ba2 = _one(board, "BA-02")
    assert ba2["outcome"] == "pass" and _lines(ba2) == [("2 accounts on file", [], "no other account in the documents")]


def test_a_declared_row_opens_the_declaration_that_lists_the_account(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    declaration(root, case_id)
    # A second declaration that lists only accounts: no other fact names its document.
    second = add_doc(root, case_id, "existing_facilities_declaration",
                     {"bank_accounts": [{"bank": "Lotuscrest Bank", "account_number": "901000001234"}]}, page=5)
    main = statement(root, case_id)
    ba1 = _one(_board(client, analyst, root, case_id), "BA-01")
    assert ba1["outcome"] == "pass"
    assert _rows(_column(ba1, "declared")) == [(["Lotuscrest Bank ·1234", "Declaration of existing facilities"],
                                                [(second, 5)])]
    assert _rows(_column(ba1, "statements")) == [(["Lotuscrest Bank ·1234", "Bank statement"], [(main, 3)])]


@pytest.mark.usefixtures("all_rules_enabled")
def test_checks_with_nothing_on_file_ask_for_the_documents(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    board = _board(client, analyst, root, case_id)
    for rule in ("BA-01", "OB-01"):
        f = _one(board, rule)
        assert f["outcome"] == "not_applicable" and f["columns"] == [] and f["request"] is None
    requests = {r: _one(board, r)["request"] for r in ("BA-02", "OB-02", "OB-03", "BR-01", "BR-02", "BR-04")}
    assert requests == {
        "BA-02": "the bank statement",
        "OB-02": "the bank statement",
        "OB-03": "the audited financial statements and the bank statement",
        "BR-01": "the board resolution for borrowing",
        "BR-02": "the board resolution for borrowing, the director KYC and the memorandum and articles of association",
        "BR-04": "the board resolution for borrowing and the certificate of incorporation",
    }
    for rule in requests:
        assert _one(board, rule)["outcome"] == "incomplete"
    # Each line says what would complete its check; a check that did not apply has none.
    assert {r: _lines(_one(board, r)) for r in ("BA-01", "BA-02", "OB-01", "OB-02", "OB-03")} == {
        "BA-01": [], "OB-01": [],
        "BA-02": [("Accounts on file", [], "the bank statement needed")],
        "OB-02": [("Instalments", [], "the bank statement needed")],
        "OB-03": [("Borrowings and instalments", [], "the audited financial statements and the bank statement needed")],
    }


# --- Existing facilities (OB-01) ---


def test_facility_legs_mirror_each_lender_problem(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    decl = declaration(root, case_id, [TIDEWATER])
    letter = sanction(root, case_id, "TIDEWATER FINANCE LTD", 15_000_000)
    report = bureau(root, case_id, [{**TIDEWATER, "sanctioned_amount": 15_200_000}, LOTUSCREST])
    f = _one(_board(client, analyst, root, case_id), "OB-01")
    assert f["outcome"] == "fail"
    assert "Tidewater Finance Limited: sanctioned amounts differ" in f["explanation"]
    assert "Lotuscrest Bank: not declared" in f["explanation"]
    assert [c["key"] for c in f["columns"]] == ["declaration", "sanction_letters", "bureau"]
    assert [c["label"] for c in f["columns"]] == ["Declaration of existing facilities", "Sanction letters",
                                                  "Commercial bureau report"]
    assert [c["provenance"] for c in f["columns"]] == [["declared"], ["borrower_supplied"], ["independent"]]
    assert [c["differs"] for c in f["columns"]] == [True, True, True]
    assert [c["coverage"] for c in f["columns"]] == ["1 facility declared", "1 facility in 1 letter",
                                                     "2 facilities reported · INR 2.60 cr outstanding"]
    assert _column(f, "declaration")["row_columns"] == ["Lender", "Facility", "Sanctioned", "EMI"]
    assert _rows(_column(f, "declaration")) == [(["Tidewater Finance Limited", "Term loan", 12_000_000, 250_000], [(decl, 2)])]
    assert _rows(_column(f, "sanction_letters")) == [(["TIDEWATER FINANCE LTD", "Term loan", 15_000_000, None], [(letter, 4)])]
    bureau_column = _column(f, "bureau")
    assert bureau_column["row_columns"] == ["Lender", "Facility", "Sanctioned", "Outstanding", "Overdue"]
    assert _rows(bureau_column) == [(["Tidewater Finance Limited", "Term loan", 15_200_000, 7_500_000, 0], [(report, 5)]),
                                    (["Lotuscrest Bank", "Cash credit", 20_000_000, 18_500_000, 0], [(report, 5)])]
    assert _pages(bureau_column["evidence"]) == [(report, 5)]
    # The amounts differ: a leg per pair that differs, each against the 5% tolerance, so the
    # sanction letter against the bureau (1.3%) is shown but not breached. The lender nobody
    # declared: the amount the bureau shows.
    tidewater = "Tidewater Finance Limited"
    assert _gaps(f) == [
        (f"{tidewater}: declared against sanction letter", 3_000_000, 20.0, "sanction letter",
         f"{tidewater} declared against sanction letter", True),
        (f"{tidewater}: declared against bureau", 3_200_000, 21.1, "bureau", f"{tidewater} declared against bureau", True),
        (f"{tidewater}: sanction letter against bureau", 200_000, 1.3, "bureau",
         f"{tidewater} sanction letter against bureau", False),
        ("Lotuscrest Bank: not declared", 20_000_000, None, None, "Lotuscrest Bank", True),
    ]
    assert f["amount"] == 20_000_000 and f["gap_tolerance"] == "5%" and f["request"] is None
    # A line per lender problem. The amounts side by side, the declared one marked: the sanction letter
    # and the bureau agree within the tolerance; how far apart the widest pair is. The lender nobody
    # declared: the amount shown, and where.
    assert _lines(f) == [
        (tidewater, [("Declared", 12_000_000, True), ("Sanction letter", 15_000_000, False),
                     ("Bureau report", 15_200_000, False)], "21.1% apart · tolerance 5%"),
        ("Lotuscrest Bank", [], "not declared · INR 2.00 cr in the bureau report"),
    ]


def test_a_declared_facility_nothing_else_shows_is_one_leg(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    declaration(root, case_id, [TIDEWATER, LOTUSCREST])
    bureau(root, case_id, [TIDEWATER])
    f = _one(_board(client, analyst, root, case_id), "OB-01")
    assert f["outcome"] == "fail"
    # No sanction letter is on file: no column for one.
    assert [c["key"] for c in f["columns"]] == ["declaration", "bureau"]
    assert _gaps(f) == [("Lotuscrest Bank: declared, but no sanction letter or bureau entry shows it", 20_000_000, None,
                         None, "Lotuscrest Bank", True)]
    assert f["amount"] == 20_000_000
    assert _lines(f) == [("Lotuscrest Bank", [], "declared, but no sanction letter or bureau entry shows it")]


def test_sanctioned_amounts_that_agree_share_one_figure_and_the_odd_one_is_marked(client, analyst, published_data_root):
    root = published_data_root
    ashwood = {"lender": "Ashwood Finserv Limited", "facility": "Term loan", "sanctioned_amount": 8_000_000}
    case_id = _case(client, analyst, root)
    declaration(root, case_id, [ashwood])
    sanction(root, case_id, "Ashwood Finserv Limited", 9_500_000)
    bureau(root, case_id, [{**ashwood, "sanctioned_amount": 9_500_000, "outstanding": 6_000_000}])
    f = _one(_board(client, analyst, root, case_id), "OB-01")
    assert f["outcome"] == "fail"
    # The sanction letter and the bureau agree to the rupee: one figure for both.
    assert _lines(f) == [("Ashwood Finserv Limited", [("Declared", 8_000_000, True),
                                                      ("Sanction letter and bureau report", 9_500_000, False)],
                          "15.8% apart · tolerance 5%")]

    # Two sources, each its own amount: the smaller is marked, as the card's leg is measured against it.
    two = _case(client, analyst, root, borrower="Heronbay")
    declaration(root, two, [ashwood])
    bureau(root, two, [{**ashwood, "sanctioned_amount": 9_500_000, "outstanding": 6_000_000}])
    f = _one(_board(client, analyst, root, two), "OB-01")
    assert _lines(f) == [("Ashwood Finserv Limited", [("Declared", 8_000_000, True), ("Bureau report", 9_500_000, False)],
                          "15.8% apart · tolerance 5%")]


def test_facilities_that_agree_show_no_breach(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    decl = declaration(root, case_id, [TIDEWATER])
    letter = sanction(root, case_id, "Tidewater Finance Limited", 12_000_000, emi=250_000)
    bureau(root, case_id, [TIDEWATER])
    main = statement(root, case_id, instalments())
    board = _board(client, analyst, root, case_id)

    ob1 = _one(board, "OB-01")
    assert ob1["outcome"] == "pass" and [c["differs"] for c in ob1["columns"]] == [False, False, False]
    assert ob1["gaps"] == [] and ob1["amount"] is None and ob1["mismatch"] is None and ob1["gap_tolerance"] == "5%"
    assert _lines(ob1) == [("Existing facilities", [], "1 facility reconciles")]
    assert _rows(_column(ob1, "sanction_letters")) == [(["Tidewater Finance Limited", "Term loan", 12_000_000, 250_000],
                                                        [(letter, 4)])]

    ob2 = _one(board, "OB-02")
    assert ob2["outcome"] == "pass" and ob2["gaps"] == [] and ob2["amount"] is None and ob2["mismatch"] is None
    assert _lines(ob2) == [("Instalments", [], "every lender paid by instalment is declared")]
    assert [c["key"] for c in ob2["columns"]] == ["instalments", "declaration"]
    emis = _column(ob2, "instalments")
    assert emis["label"] == "Instalments in bank statements" and emis["provenance"] == ["borrower_supplied"]
    assert emis["coverage"] == "1 lender · INR 2.50 lakh a month"
    assert emis["row_columns"] == ["Lender", "Account", "Monthly instalment", "Months"]
    [(cells, pages)] = _rows(emis)
    assert cells == ["TIDEWATER FIN", "Lotuscrest Bank ·1234", 250_000, "Apr 2025 to Sep 2025"]
    assert pages and {p for p in pages} == {(main, 3)}
    declared = _column(ob2, "declaration")
    assert declared["row_columns"] == ["Lender", "Facility", "EMI"]
    assert _rows(declared) == [(["Tidewater Finance Limited", "Term loan", 250_000], [(decl, 2)])]


def test_facility_reconciliation_asks_for_what_is_missing(client, analyst, published_data_root):
    root = published_data_root
    declared_only = _case(client, analyst, root)
    decl = declaration(root, declared_only, [TIDEWATER])
    f = _one(_board(client, analyst, root, declared_only), "OB-01")
    # Either document would complete it.
    assert f["outcome"] == "incomplete" and f["request"] == "the sanction letter or the commercial bureau report"
    assert [c["key"] for c in f["columns"]] == ["declaration"]
    assert _rows(f["columns"][0]) == [(["Tidewater Finance Limited", "Term loan", 12_000_000, 250_000], [(decl, 2)])]
    assert _lines(f) == [("Existing facilities", [], "the sanction letter or the commercial bureau report needed")]

    reported_only = _case(client, analyst, root, borrower="Heronbay")
    report = bureau(root, reported_only, [TIDEWATER])
    f = _one(_board(client, analyst, root, reported_only), "OB-01")
    assert f["outcome"] == "incomplete" and f["request"] == "the declaration of existing facilities"
    assert [c["key"] for c in f["columns"]] == ["bureau"]
    assert _pages(f["columns"][0]["evidence"]) == [(report, 5)]
    assert _lines(f) == [("Existing facilities", [], "the declaration of existing facilities needed")]


def test_a_note_typed_on_the_case_is_not_placed_in_the_sourcing_message(client, analyst, published_data_root):
    """The existing banking the RM declared: read from the sourcing message, the column says so; typed
    on the case by a person, it has no place in the message, and the column says it was entered on the case."""
    root = published_data_root
    note = "Current account with Lotuscrest Bank a/c 90100001234"
    typed = _case(client, analyst, root, header={"existing_banking": {"value": note, "source": "person"}})
    bureau(root, typed, [TIDEWATER])
    f = _one(_board(client, analyst, root, typed), "OB-01")
    assert f["outcome"] == "fail"
    declared = _column(f, "sourcing_message")
    assert (declared["label"], declared["value"], declared["coverage"]) == (
        "Declared in the sourcing message", note, "Entered on the case")
    assert declared["evidence"] == [] and declared["relies_on_manual"]
    assert _lines(f) == [("Tidewater Finance Limited", [], "not declared · INR 1.20 cr in the bureau report")]

    message = f"Kestrel Tools Pvt Ltd banks with us: {note}."
    start = message.index(note)
    read = _case(client, analyst, root, borrower="Heronbay", message_text=message,
                 header={"existing_banking": {"value": note, "source": f"message:{start}-{start + len(note)}"}})
    bureau(root, read, [TIDEWATER])
    declared = _column(_one(_board(client, analyst, root, read), "OB-01"), "sourcing_message")
    assert declared["coverage"] == "In the sourcing message" and declared["evidence"][0]["page"] == 1


# --- Instalments (OB-02, OB-03) ---


def test_instalments_to_an_undeclared_lender(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    decl = declaration(root, case_id)  # declares none
    statement(root, case_id, instalments())
    f = _one(_board(client, analyst, root, case_id), "OB-02")
    assert f["outcome"] == "fail"
    assert [c["key"] for c in f["columns"]] == ["instalments", "declaration"]
    assert [c["differs"] for c in f["columns"]] == [True, False]
    nil = _column(f, "declaration")
    # A declaration of no facilities is a statement too: its page is the evidence.
    assert nil["value"] == "None declared" and nil["coverage"] == "Declares no existing facilities"
    assert _rows(nil) == [(["None declared", None, None], [(decl, 2)])]
    assert _gaps(f) == [("Annual outflow to TIDEWATER FIN (INR 2.50 lakh a month), not declared", 3_000_000, None, None,
                         "TIDEWATER FIN", True)]
    assert f["amount"] == 3_000_000 and f["gap_tolerance"] is None
    assert f["mismatch"] == "Instalments to TIDEWATER FIN appear in the bank statements but no declaration names them."
    # A line per lender paid by instalment and not declared, named as the bank statement prints it.
    assert _lines(f) == [("TIDEWATER FIN", [], "INR 2.50 lakh a month in the bank statements, not declared")]

    undeclared = _case(client, analyst, root, borrower="Heronbay")
    statement(root, undeclared, instalments())
    f = _one(_board(client, analyst, root, undeclared), "OB-02")
    assert f["outcome"] == "incomplete" and [c["key"] for c in f["columns"]] == ["instalments"]
    assert f["request"] == ("the declaration of existing facilities (or a written confirmation of the facility behind "
                            "TIDEWATER FIN)")
    assert "; confirm the facility behind TIDEWATER FIN (INR 2.50 lakh a month in 6 months, " in f["explanation"]
    assert _lines(f) == [("Instalments", [], f"{f['request']} needed")]

    # The lender's sanction letter is on file: no word on that facility is asked for, but the declaration in
    # full, signed.
    sanctioned = _case(client, analyst, root, borrower="Marigold Agro Foods Pvt Ltd")
    statement(root, sanctioned, instalments())
    sanction(root, sanctioned, "Tidewater Finance Limited", 12_000_000)
    f = _one(_board(client, analyst, root, sanctioned), "OB-02")
    assert f["outcome"] == "incomplete"
    assert f["request"] == ("the declaration of existing facilities, signed, giving every existing facility "
                            "(lender, limit, outstanding, instalment)")
    assert f["explanation"].startswith("No declaration of existing facilities is on file and the sourcing message "
                                       "declares none, so the instalments to TIDEWATER FIN (INR 2.50 lakh a month in 6 "
                                       "months, ")
    assert f["explanation"].endswith(") cannot be held against one.")


def test_borrowings_against_instalments(client, analyst, published_data_root):
    root = published_data_root
    # Instalments in the bank, no long-term borrowings in the books.
    serviced = _case(client, analyst, root)
    books = audited(root, serviced, "2026-03-31", set_rows={"(a) Long-term borrowings": 0}, page=6)
    main = statement(root, serviced, instalments())
    f = _one(_board(client, analyst, root, serviced), "OB-03")
    assert f["outcome"] == "fail" and f["scope"] == "FY 2025-26"
    borrowings, emis = f["columns"]
    assert borrowings["key"] == "borrowings" and borrowings["label"] == "Long-term borrowings, FY 2025-26 balance sheet"
    assert borrowings["value"] == 0 and borrowings["unit"] == "inr" and borrowings["differs"]
    assert borrowings["coverage"] == "As at 31 Mar 2026 · audited" and borrowings["provenance"] == ["borrower_supplied"]
    assert _rows(borrowings) == [(["Long-term borrowings", "FY 2025-26", 0], [(books, 6)])]
    assert emis["key"] == "instalments" and not emis["differs"] and _pages(emis["evidence"]) == [(main, 3)]
    assert f["amount"] == 3_000_000  # a year of the instalments
    assert f["mismatch"] == ("Instalments of INR 2.50 lakh a month in the bank statements; no long-term borrowings in "
                             "the FY 2025-26 balance sheet.")
    # The overview line puts the difference in the mismatch's words.
    assert _lines(f) == [("Borrowings and instalments", [], "Instalments of INR 2.50 lakh a month in the bank statements; "
                                                            "no long-term borrowings in the FY 2025-26 balance sheet")]

    # Long-term borrowings in the books (1.5 cr), no instalments in the bank.
    unserviced = _case(client, analyst, root, borrower="Heronbay")
    audited(root, unserviced, "2026-03-31", page=6)
    searched = statement(root, unserviced, [{"date": "2025-05-02", "description": "NEFT CR CUSTOMER RECEIPT",
                                             "credit": 500_000}])
    f = _one(_board(client, analyst, root, unserviced), "OB-03")
    assert f["outcome"] == "fail"
    emis = _column(f, "instalments")
    assert emis["value"] == "None found" and emis["differs"] and emis["rows"] == []
    # Nothing found: the statement searched is where to look.
    assert emis["coverage"] == "No regular instalments found" and _pages(emis["evidence"]) == [(searched, 3)]
    assert f["amount"] == 15_000_000
    assert f["mismatch"] == ("Long-term borrowings of INR 1.50 cr in the FY 2025-26 balance sheet; no instalments in "
                             "the bank statements.")
    assert _lines(f) == [("Borrowings and instalments", [], "Long-term borrowings of INR 1.50 cr in the FY 2025-26 "
                                                            "balance sheet; no instalments in the bank statements")]

    # Borrowings in the books, serviced by instalments in the bank: what the rule confirmed.
    serviced_both = _case(client, analyst, root, borrower="Heronbay", duplicate_override_reason="A third scenario")
    audited(root, serviced_both, "2026-03-31", page=6)
    statement(root, serviced_both, instalments())
    f = _one(_board(client, analyst, root, serviced_both), "OB-03")
    assert f["outcome"] == "pass" and f["mismatch"] is None
    assert _lines(f) == [("Borrowings and instalments", [], "serviced in the bank statements")]


# --- The board resolution (BR-01 to BR-04, switched off in configuration) ---


@pytest.mark.usefixtures("all_rules_enabled")
def test_board_resolution_cards(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, amount_inr=65_000_000)
    res = resolution(root, case_id, borrowing_limit=20_000_000, lender_name="Lotuscrest Bank Limited",
                     resolution_date="2014-01-10", authorized_signatories=["Tarun Velankar", "Sunil Karve"])
    coi = add_doc(root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2015-06-01"}, page=8)
    kyc = add_doc(root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567"}, page=9)
    board = _board(client, analyst, root, case_id)

    br1 = _one(board, "BR-01")
    assert br1["outcome"] == "fail"
    limit, requested = br1["columns"]
    assert (limit["key"], limit["label"], limit["value"], limit["unit"], limit["differs"]) == (
        "limit", "Board resolution limit", 20_000_000, "inr", True)
    assert limit["provenance"] == ["borrower_supplied"] and limit["coverage"] == "Resolution dated 10 Jan 2014"
    assert _rows(limit) == [(["Borrowing limit", 20_000_000], [(res, 7)])] and _pages(limit["evidence"]) == [(res, 7)]
    assert (requested["key"], requested["label"], requested["value"], requested["unit"], requested["differs"]) == (
        "requested", "Amount requested", 65_000_000, "inr", False)
    assert requested["sources"] == ["application_message"] and requested["provenance"] == ["declared"]
    assert requested["coverage"] == "On the case record"
    assert _gaps(br1) == [("Shortfall against the amount requested", 45_000_000, 69.2, "requested",
                           "limit against amount requested", True)]
    assert br1["amount"] == 45_000_000 and br1["mismatch"] is None

    br2 = _one(board, "BR-02")
    assert br2["outcome"] == "fail"
    signatories, directors = br2["columns"]
    assert signatories["label"] == "Authorised in the board resolution" and signatories["differs"]
    assert signatories["coverage"] == "2 signatories authorised"
    assert _rows(signatories) == [(["Tarun Velankar", "Board resolution for borrowing"], [(res, 7)]),
                                  (["Sunil Karve", "Board resolution for borrowing"], [(res, 7)])]
    assert directors["label"] == "Directors on file" and not directors["differs"]
    assert directors["coverage"] == "1 director on file"
    assert _rows(directors) == [(["Tarun Velankar", "Director KYC"], [(kyc, 9)])]
    assert br2["mismatch"] == "Sunil Karve is not among the directors on file." and br2["gaps"] == []

    br3 = _one(board, "BR-03")
    assert br3["outcome"] == "fail"
    lender, this_bank = br3["columns"]
    assert lender["value"] == "Lotuscrest Bank Limited" and lender["differs"]
    assert _rows(lender) == [(["Lender", "Lotuscrest Bank Limited"], [(res, 7)])]
    # This bank's names come from the configuration, not a document: no page.
    assert this_bank["label"] == "This bank" and this_bank["value"] == "RBL Bank Limited" and this_bank["provenance"] == []
    assert _rows(this_bank) == [(["RBL Bank Limited"], []), (["RBL Bank"], []), (["Ratnakar Bank Limited"], [])]
    assert br3["mismatch"] == "The resolution names Lotuscrest Bank Limited, not RBL Bank Limited."

    br4 = _one(board, "BR-04")
    assert br4["outcome"] == "fail"
    assert [(c["key"], c["value"], c["unit"], c["differs"]) for c in br4["columns"]] == [
        ("resolution_date", "2014-01-10", "date", True), ("incorporation", "2015-06-01", "date", False),
        ("appraisal_date", "2026-09-29", "date", False)]
    assert [_rows(c) for c in br4["columns"]] == [
        [(["Resolution date", "10 Jan 2014"], [(res, 7)])], [(["Date of incorporation", "1 Jun 2015"], [(coi, 8)])],
        [(["Appraisal date", "29 Sep 2026"], [])]]
    assert br4["mismatch"] == "The resolution is dated 10 Jan 2014, before the company was incorporated on 1 Jun 2015."
    assert br4["gaps"] == [] and br4["amount"] is None


@pytest.mark.usefixtures("all_rules_enabled")
def test_board_resolution_cards_that_pass(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, amount_inr=65_000_000)
    resolution(root, case_id, borrowing_limit=100_000_000, lender_name="RBL Bank Ltd", resolution_date="2025-06-01",
               authorized_signatories=["Tarun Velankar"])
    add_doc(root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2015-06-01"}, page=8)
    add_doc(root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567"}, page=9)
    board = _board(client, analyst, root, case_id)
    assert {r: _one(board, r)["outcome"] for r in ("BR-01", "BR-02", "BR-03", "BR-04")} == dict.fromkeys(
        ("BR-01", "BR-02", "BR-03", "BR-04"), "pass")
    br1 = _one(board, "BR-01")
    # The limit covers the request: the headroom, not a breach; nothing to rank.
    assert _gaps(br1) == [("Headroom over the amount requested", 35_000_000, 53.8, "requested",
                           "limit against amount requested", False)]
    assert br1["amount"] is None
    for rule in ("BR-02", "BR-03", "BR-04"):
        assert len(_one(board, rule)["columns"]) >= 2 and not any(c["differs"] for c in _one(board, rule)["columns"])


@pytest.mark.usefixtures("all_rules_enabled")
def test_a_resolution_limit_that_could_not_be_read(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    res = resolution(root, case_id, lender_name="RBL Bank Ltd")
    f = _one(_board(client, analyst, root, case_id), "BR-01")
    assert f["outcome"] == "incomplete"
    assert f["request"] == "the board resolution for borrowing that states the borrowing limit"
    limit, requested = f["columns"]
    assert limit["value"] is None and limit["coverage"] == "Not read from the resolution"
    assert _pages(limit["evidence"]) == [(res, 7)] and _rows(limit) == [(["Borrowing limit", None], [(res, 7)])]
    assert requested["value"] == 65_000_000


@pytest.mark.usefixtures("all_rules_enabled")
def test_a_check_waiting_for_review_asks_for_nothing(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    resolution(root, case_id, borrowing_limit=20_000_000, pending={"borrowing_limit"})
    f = _one(_board(client, analyst, root, case_id), "BR-01")
    assert f["outcome"] == "incomplete" and f["explanation"].startswith("Waiting for review of board resolution limit")
    # The board links to the review: no request, and the column says it is waiting.
    assert f["request"] is None
    assert [c["awaiting_review"] for c in f["columns"]] == [True, False]


# --- The cards never change an outcome ---


def _everything(client: TestClient, analyst: dict, root: Path) -> str:
    """A case on which every one of these rules fails."""
    case_id = _case(client, analyst, root, amount_inr=65_000_000)
    declaration(root, case_id, [TIDEWATER], accounts=[("Lotuscrest Bank", "901000001234"), ("Lotuscrest Bank", "901000005678")])
    sanction(root, case_id, "TIDEWATER FINANCE LTD", 15_000_000)
    bureau(root, case_id, [{**TIDEWATER, "sanctioned_amount": 15_000_000}, LOTUSCREST])
    statement(root, case_id, instalments() + instalments("NACH DR LOTUSCREST BANK 000555", 300_000)
              + [{"date": "2025-05-02", "description": "NEFT TRANSFER TO A/C 778899001122", "debit": 500_000}])
    statement(root, case_id, last4="7777", page=4)
    audited(root, case_id, "2026-03-31", set_rows={"(a) Long-term borrowings": 0}, page=6)
    resolution(root, case_id, borrowing_limit=20_000_000, lender_name="Lotuscrest Bank Limited",
               resolution_date="2014-01-10", authorized_signatories=["Tarun Velankar", "Sunil Karve"])
    add_doc(root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2015-06-01"}, page=8)
    add_doc(root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567"}, page=9)
    return case_id


DECIDED = {"rule_id", "scope", "title", "outcome", "severity", "blocking", "explanation", "sides", "detail", "missing",
           "tolerance", "query"}
"""What the rule decides; the card never touches it."""


@pytest.mark.usefixtures("all_rules_enabled")
def test_the_cards_never_change_an_outcome(client, analyst, published_data_root, monkeypatch):
    root = published_data_root
    case_id = _everything(client, analyst, root)
    board = _board(client, analyst, root, case_id)
    assert {r: _one(board, r)["outcome"] for r in MINE} == dict.fromkeys(MINE, "fail")
    conn = db.connect(root)
    try:
        case = cases.get_case(conn, case_id)
        with_cards = crosschecks.evaluate(root, case, facts.compute(conn, root, case))
        monkeypatch.setattr(xv_cards, "BUILDERS", {})
        without = crosschecks.evaluate(root, case, facts.compute(conn, root, case))
    finally:
        conn.close()
    assert [(f.rule_id, f.scope) for f in with_cards] == [(f.rule_id, f.scope) for f in without]
    for a, b in zip(with_cards, without):
        assert a.model_dump(include=DECIDED) == b.model_dump(include=DECIDED), a.rule_id
    # The builders did build these cards: without them the columns are the bare sides.
    built = {f.rule_id: f for f in with_cards if f.rule_id in MINE}
    bare = {f.rule_id: f for f in without if f.rule_id in MINE}
    assert all(built[r].columns != bare[r].columns for r in MINE)
    assert all(bare[r].gaps == [] and bare[r].mismatch is None and bare[r].highlights == [] for r in MINE)
    # Every check of the bank accounts and the obligations gave its lines (the board resolution, switched
    # off, has none to give).
    assert all(built[r].highlights for r in MINE if not r.startswith("BR-"))
