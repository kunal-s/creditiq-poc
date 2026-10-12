"""The key figures on the board's area overview cards (engine/xv.py, from the lines each card
builder gives its finding): up to three lines per area, taken from the area's open discrepancies in
rank order, then its decided discrepancies, then the checks that could not run, then the passed
ones. Each line names its finding, rule and outcome, so the screen can link it to its card and
colour it; the screen computes nothing. Every name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

CO = "Kestrel Tools Pvt Ltd"
PAN, BUREAU_PAN = "AAACK1234F", "AAACK9999Z"
GSTIN, BUREAU_GSTIN = "27AAACK1234F1Z0", "29AAACK1234F1ZW"
TARUN, ISHITA, SUNIL = "Tarun Velankar", "Ishita Barve", "Sunil Karve"
FY26 = months((2025, 4), 12)
PERIODS = [f"{m} {2025 if i < 9 else 2026}" for i, m in enumerate(
    ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February",
     "March"])]
ASHWOOD, TIDEWATER = "Ashwood Finserv Limited", "Tidewater Finance Limited"
LIMIT = 3
"""Key-figure lines on an area's card."""


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _board(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/cross-verification", headers=headers)
    assert response.status_code == 200, response.text
    board = response.json()
    _picked_in_order(board)
    return board


def _picked_in_order(board: dict) -> None:
    """Each area's lines are the first three of its findings' lines: open discrepancies in rank order,
    then decided ones, then the checks that could not run and those that passed, in the board's order
    (a check that did not apply has none), each naming its finding as it is on the board."""
    for area in board["areas"]:
        items = [i for i in board["items"] if i["finding"]["area"] == area["area"]]
        failed = [i for i in items if i["finding"]["outcome"] == "fail"]
        picked = ([i for i in failed if not i["adjudicated"]] + [i for i in failed if i["adjudicated"]]
                  + [i for i in items if i["finding"]["outcome"] in ("incomplete", "pass")])
        assert area["highlights"] == [h for i in picked for h in i["finding"]["highlights"]][:LIMIT], area["area"]
        outcomes = {i["finding"]["id"]: (i["finding"]["rule_id"], i["finding"]["outcome"]) for i in items}
        assert all(outcomes[h["finding_id"]] == (h["rule_id"], h["outcome"]) for h in area["highlights"]), area["area"]


def _lines(board: dict, area: str) -> list[tuple]:
    """An area's lines: rule, label, facts (label, value, differs), note."""
    [found] = [a for a in board["areas"] if a["area"] == area]
    return [(h["rule_id"], h["label"], [(x["label"], x["value"], x["differs"]) for x in h["facts"]], h["note"])
            for h in found["highlights"]]


def _span(message: str, text: str) -> dict:
    """A case-header value read from the sourcing message."""
    start = message.index(text)
    return {"value": text, "source": f"message:{start}-{start + len(text)}"}


def _kestrel(client: TestClient, headers: dict, root: Path) -> str:
    """A case like the demo's Kestrel: the bureau gives another PAN and GSTIN and names a promoter the
    KYC does not; GST INR 11.82 cr and audited INR 11.80 cr against bank credits of INR 9.00 cr, with
    INR 18.00 cr declared; a declared account without a statement, a statement not declared and an
    account seen only in a transfer; Ashwood declared at INR 80.00 lakh against INR 95.00 lakh in the
    sanction letter and the bureau, Tidewater in the bureau only, and its instalments in the bank."""
    promoters = f"{TARUN}; {ISHITA}; {SUNIL}"
    message = (f"{CO}, PAN {PAN}, GSTIN {GSTIN}, needs a term loan. Promoters: {promoters}. "
               f"Turnover INR 18 crore in FY 2025-26.")
    turnover = _span(message, "INR 18 crore")
    case_id = make_case(client, headers, root, borrower=CO, message_text=message, header={
        "pan": _span(message, PAN), "gstin": _span(message, GSTIN), "promoters": _span(message, promoters),
        "declared_turnover_inr": {**turnover, "value": "180000000"}})
    add_doc(root, case_id, "company_pan", {"pan": PAN, "company_name": CO})
    add_doc(root, case_id, "income_tax_return", {"pan": PAN, "taxpayer_name": CO})
    for period in PERIODS:
        gstr(root, case_id, period, 9_850_000, gstin=GSTIN)
    audited(root, case_id, "2026-03-31")  # revenue INR 11.80 cr; long-term borrowings INR 1.50 cr
    add_doc(root, case_id, "director_kyc", {"person_name": TARUN, "din": "01234567", "pan": "ABCPV1234K"})
    add_doc(root, case_id, "director_kyc", {"person_name": ISHITA, "din": "07654321", "pan": "ABCPB5678M"})
    add_doc(root, case_id, "commercial_bureau_report", {
        "company_name": CO, "pan": BUREAU_PAN, "gstin": BUREAU_GSTIN, "report_date": "2026-09-20",
        "related_parties": [{"name": n, "relationship": "Director"} for n in (TARUN, ISHITA, SUNIL)],
        "credit_facilities": [
            {"lender": ASHWOOD, "facility": "Term loan", "sanctioned_amount": 9_500_000, "outstanding": 6_000_000,
             "overdue": 0, "status": "Standard"},
            {"lender": TIDEWATER, "facility": "Term loan", "sanctioned_amount": 12_000_000, "outstanding": 7_500_000,
             "overdue": 0, "status": "Standard"}]})
    add_doc(root, case_id, "existing_facilities_declaration", {
        "company_name": CO, "declaration_date": "2026-09-15",
        "facilities": [{"lender": ASHWOOD, "facility": "Term loan", "sanctioned_amount": 8_000_000, "emi": 145_000}],
        "bank_accounts": [{"bank": "Lotuscrest Bank", "account_number": n, "account_type": "Current account"}
                          for n in ("901000001234", "901000005678")]})
    add_doc(root, case_id, "sanction_letter", {"lender_name": ASHWOOD, "borrower_name": CO, "sanction_date": "2024-04-12",
                                              "facilities": [{"facility": "Term loan", "sanctioned_amount": 9_500_000}]})
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 7_500_000} for ym in FY26]
         + [{"date": "2025-06-10", "description": "TL DISB LOAN A/C 88991", "credit": 5_000_000}]
         + [{"date": f"{ym}-10", "description": "NACH DR TIDEWATER FIN EMI 000123", "debit": 250_000} for ym in FY26]
         + [{"date": f"{ym}-05", "description": "NACH DR ASHWOOD FINSERV", "debit": 145_000} for ym in FY26]
         + [{"date": "2025-05-02", "description": "NEFT TRANSFER TO A/C 778899001122", "debit": 500_000}], holder=CO)
    bank(root, case_id, [], last4="7777", bank_name="Ironleaf Bank", holder=CO)
    _refresh(root, case_id)
    return case_id


def test_each_area_card_shows_the_key_figures_of_its_greatest_discrepancies(client, analyst, published_data_root):
    board = _board(client, analyst, _kestrel(client, analyst, published_data_root))
    # The two PANs and the two GSTINs side by side, the bureau's marked; the promoter the KYC lacks.
    assert _lines(board, "identity") == [
        ("ID-01", "PAN", [("15 documents and the sourcing message", PAN, False),
                          ("Commercial bureau report", BUREAU_PAN, True)], None),
        ("ID-02", "GSTIN", [("GSTR-3B, Sourcing message", GSTIN, False), ("Commercial bureau report", BUREAU_GSTIN, True)],
         None),
        ("ID-04", "Promoters", [], "Sunil Karve is not in KYC received"),
    ]
    # The turnover figures in rupees (the screen writes them in crores), the smaller marked, how far apart.
    assert _lines(board, "turnover") == [
        ("TO-02", "GST against bank credits · FY 2025-26",
         [("GST outward supplies", 118_200_000, False), ("Bank credits", 90_000_000, True)], "23.9% apart · tolerance 1%"),
        ("TO-03", "Audited against bank credits · FY 2025-26",
         [("Audited", 118_000_000, False), ("Bank credits", 90_000_000, True)], "23.7% apart · tolerance 1%"),
        ("TO-04", "Declared against audited · FY 2025-26",
         [("Declared", 180_000_000, False), ("Audited", 118_000_000, True)], "34.4% apart · tolerance 2%"),
    ]
    assert [x["unit"] for a in board["areas"] if a["area"] == "turnover" for h in a["highlights"] for x in h["facts"]] == [
        "inr"] * 6
    # A line per account flagged.
    assert _lines(board, "accounts") == [
        ("BA-01", "Lotuscrest Bank ·5678", [], "declared, no statement"),
        ("BA-02", "Ironleaf Bank ·7777", [], "statement, not declared"),
        ("BA-02", "Account ·1122", [], "seen only in transfers"),
    ]
    # A line per lender problem, then the lender paid by instalment that nobody declared; at most three,
    # so the passed borrowings check has no room.
    assert _lines(board, "obligations") == [
        ("OB-01", ASHWOOD, [("Declared", 8_000_000, True), ("Sanction letter and bureau report", 9_500_000, False)],
         "15.8% apart · tolerance 5%"),
        ("OB-01", TIDEWATER, [], "not declared · INR 1.20 cr in the bureau report"),
        ("OB-02", "TIDEWATER FIN", [], "INR 2.50 lakh a month in the bank statements, not declared"),
    ]
    assert [i["finding"]["outcome"] for i in board["items"] if i["finding"]["rule_id"] == "OB-03"] == ["pass"]


def test_decided_discrepancies_give_way_to_the_open_ones(client, analyst, published_data_root):
    case_id = _kestrel(client, analyst, published_data_root)
    board = _board(client, analyst, case_id)
    ids = {i["finding"]["rule_id"]: i["finding"]["id"] for i in board["items"] if i["finding"]["outcome"] == "fail"}
    for rule, decision in (("ID-01", "accept"), ("OB-01", "dismiss")):
        response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{ids[rule]}/decision",
                               json={"decision": decision, "comment": "Checked against the documents on file"},
                               headers=analyst)
        assert response.status_code == 200, response.text
    board = _board(client, analyst, case_id)
    # The decided PAN follows the open GSTIN and promoters.
    assert [(rule, label) for rule, label, _, _ in _lines(board, "identity")] == [
        ("ID-02", "GSTIN"), ("ID-04", "Promoters"), ("ID-01", "PAN")]
    # The open instalments line comes first; the decided lender lines follow, as many as there is room for.
    assert [(rule, label) for rule, label, _, _ in _lines(board, "obligations")] == [
        ("OB-02", "TIDEWATER FIN"), ("OB-01", ASHWOOD), ("OB-01", TIDEWATER)]
    # A decided line keeps its outcome: a discrepancy, decided.
    [pan] = [h for a in board["areas"] if a["area"] == "identity" for h in a["highlights"] if h["rule_id"] == "ID-01"]
    assert pan["outcome"] == "fail"


def test_without_a_discrepancy_an_area_shows_what_could_not_run_then_what_passed(client, analyst, published_data_root):
    """No discrepancy anywhere: the identity card leads with the checks that could not run (each with
    what would complete it), though passed checks come earlier in the configuration; the turnover
    card, where every check ran, shows what each confirmed."""
    root = published_data_root
    case_id = make_case(client, analyst, root, borrower=CO)
    add_doc(root, case_id, "company_pan", {"pan": PAN, "company_name": CO})
    add_doc(root, case_id, "income_tax_return", {"pan": PAN, "taxpayer_name": CO})
    audited(root, case_id, "2026-03-31", set_rows={"(a) Long-term borrowings": 0})  # revenue INR 11.80 cr
    for period in PERIODS:
        gstr(root, case_id, period, 9_800_000, gstin=GSTIN)  # INR 11.76 cr
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 9_780_000}
                         for ym in FY26], holder=CO)  # INR 11.74 cr
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    outcomes = {i["finding"]["rule_id"]: i["finding"]["outcome"] for i in board["items"]}
    assert "fail" not in outcomes.values(), outcomes
    assert outcomes["ID-01"] == outcomes["ID-03"] == "pass"
    assert [(rule, note) for rule, _, _, note in _lines(board, "identity")] == [
        ("ID-04", "the director KYC needed"),
        ("ID-05", "the certificate of incorporation and the memorandum and articles of association needed"),
        ("ID-06", "the director KYC and the memorandum and articles of association needed")]
    assert all(h["outcome"] == "incomplete" for a in board["areas"] if a["area"] == "identity" for h in a["highlights"])
    # Every turnover check ran and passed: the figures, and how far apart within the tolerance.
    assert _lines(board, "turnover") == [
        ("TO-01", "Audited against GST · FY 2025-26",
         [("Audited", 118_000_000, False), ("GST outward supplies", 117_600_000, False)], "0.3% apart · within 1%"),
        ("TO-02", "GST against bank credits · FY 2025-26",
         [("GST outward supplies", 117_600_000, False), ("Bank credits", 117_360_000, False)], "0.2% apart · within 1%"),
        ("TO-03", "Audited against bank credits · FY 2025-26",
         [("Audited", 118_000_000, False), ("Bank credits", 117_360_000, False)], "0.5% apart · within 1%"),
    ]
