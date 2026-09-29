"""TC-01 (F-04): a new application from a pasted message.

Every proposed value carries its span in the message; identifiers that fail
their format or checksum are flagged, never corrected; nothing is stored
until the RM confirms; edits keep both values.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from engine import db
from engine.identifiers import build_gstin
from tests.conftest import ANALYST, MANAGER, RM, sign_in

GSTIN = build_gstin("27", "AAACK1234F")

CLEAN_EMAIL = f"""From: Arjun Deshpande <arjun.deshpande@rblbank.com>
To: Credit Desk
Subject: CC and TL proposal - Kestrel Fabricators Pvt Ltd

Dear Team,

Please find a new proposal for M/s Kestrel Fabricators Pvt Ltd (PAN AAACK1234F, GSTIN {GSTIN}).
They require a Cash Credit limit of Rs. 50 lakh and a Term Loan of Rs. 1.5 crore.
Turnover FY26: ₹12,50,00,000.
Directors: Tarun Velankar and Ishita Barve.
Existing banking with Tidewater Bank (CC 30L).
Contact: Tarun Velankar, 98200 12345

Regards,
Arjun
"""

WHATSAPP = """[12/09/26, 10:15:32 AM] Vikrant Salgaonkar: sir new case hai - heronbay polymers pvt ltd
[12/09/26, 10:16:05 AM] Vikrant Salgaonkar: CC 50L chahiye, TO approx 3 cr
[12/09/26, 10:16:40 AM] Vikrant Salgaonkar: PAN AAACH5678Q
"""

AMBIGUOUS = "Proposal for Marigold Weaves LLP / Quillon Exports Pvt Ltd group, TL 2 cr, turnover 3 cr or 30 cr?"


def _propose(client: TestClient, headers: dict, text: str, channel: str = "email") -> dict:
    response = client.post("/api/cases/proposals", json={"channel": channel, "text": text}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _source(text: str, field: dict) -> str:
    span = field["span"]
    return text[span["start"]:span["end"]]


def _every_value_has_a_span(text: str, proposal: dict) -> None:
    for name, f in proposal["fields"].items():
        if f["value"] is not None:
            assert f["span"] is not None, f"{name} proposed without a span"
            assert 0 <= f["span"]["start"] < f["span"]["end"] <= len(text)
        for c in f["candidates"]:
            assert 0 <= c["span"]["start"] < c["span"]["end"] <= len(text)


def test_tc01_clean_email_proposes_every_field_with_its_span(client: TestClient):
    rm = sign_in(client, RM)
    p = _propose(client, rm, CLEAN_EMAIL)
    f = p["fields"]
    _every_value_has_a_span(CLEAN_EMAIL, p)
    assert f["borrower"]["status"] == "found" and f["borrower"]["value"] == "Kestrel Fabricators Pvt Ltd"
    assert f["constitution"]["value"] == "private_limited"
    assert f["facilities"]["value"] == "cash_credit,term_loan"
    # The existing CC with another bank is existing banking, not a request.
    assert "Tidewater Bank" in f["existing_banking"]["value"]
    # Two facility amounts: the total is proposed for confirmation, each part with its span.
    assert f["amount_inr"]["value"] == "20000000" and f["amount_inr"]["status"] == "unclear"
    assert sorted(c["value"] for c in f["amount_inr"]["candidates"]) == ["15000000", "5000000"]
    assert f["pan"] == {**f["pan"], "status": "found", "value": "AAACK1234F"}
    assert _source(CLEAN_EMAIL, f["pan"]) == "AAACK1234F"
    assert f["gstin"]["status"] == "found" and f["gstin"]["value"] == GSTIN
    assert f["declared_turnover_inr"]["value"] == "125000000"
    assert _source(CLEAN_EMAIL, f["declared_turnover_inr"]) == "₹12,50,00,000"
    assert f["promoters"]["value"] == "Tarun Velankar; Ishita Barve"
    assert "98200 12345" in f["contact"]["value"]
    assert f["cin"]["status"] == "not_found"
    # Headers and the signature are provenance, not content.
    kinds = {s["kind"] for s in p["stripped"]}
    assert {"header", "signature"} <= kinds
    assert p["missing_minimum"] == []
    assert p["text_sha256"]


def test_tc01_messy_whatsapp_hinglish(client: TestClient):
    rm = sign_in(client, RM)
    p = _propose(client, rm, WHATSAPP, channel="whatsapp")
    f = p["fields"]
    _every_value_has_a_span(WHATSAPP, p)
    assert f["borrower"]["value"] == "heronbay polymers pvt ltd"
    assert f["facilities"]["value"] == "cash_credit"
    assert f["amount_inr"]["status"] == "found" and f["amount_inr"]["value"] == "5000000"
    assert _source(WHATSAPP, f["amount_inr"]) == "50L"
    assert f["declared_turnover_inr"]["value"] == "30000000"
    assert f["declared_turnover_inr"]["note"] == "Stated as approximate."
    assert f["pan"]["value"] == "AAACH5678Q"
    assert f["constitution"]["value"] == "private_limited"
    # The sender is provenance: never proposed as a promoter.
    assert f["promoters"]["status"] == "not_found"
    kinds = [s["kind"] for s in p["stripped"]]
    assert kinds.count("timestamp") == 3 and kinds.count("sender") == 3


def test_tc01_two_company_names_and_an_llp_are_unclear(client: TestClient):
    rm = sign_in(client, RM)
    p = _propose(client, rm, AMBIGUOUS)
    f = p["fields"]
    _every_value_has_a_span(AMBIGUOUS, p)
    assert f["borrower"]["status"] == "unclear" and f["borrower"]["value"] is None
    assert [c["value"] for c in f["borrower"]["candidates"]] == ["Marigold Weaves LLP", "Quillon Exports Pvt Ltd"]
    assert f["constitution"]["status"] == "unclear"
    assert "LLP" in f["constitution"]["note"]
    # "3 cr or 30 cr?" is shown as unclear with both readings.
    assert f["declared_turnover_inr"]["status"] == "unclear"
    assert {c["value"] for c in f["declared_turnover_inr"]["candidates"]} == {"30000000", "300000000"}
    assert "borrower" in p["missing_minimum"]


def test_tc01_invalid_identifiers_are_flagged_never_corrected(client: TestClient):
    rm = sign_in(client, RM)
    wrong_check = GSTIN[:-1] + ("1" if GSTIN[-1] != "1" else "2")
    text = f"Client: Orchid Castings Pvt Ltd, PAN AAAXO1234Z, GSTIN {wrong_check}, CC 40 lakh, TO 3-4 cr"
    f = _propose(client, rm, text)["fields"]
    assert f["pan"]["status"] == "invalid" and f["pan"]["value"] == "AAAXO1234Z"
    assert "not corrected" in f["pan"]["note"]
    assert f["gstin"]["status"] == "invalid" and f["gstin"]["value"] == wrong_check
    assert "check character" in f["gstin"]["note"]
    # A malformed PAN (too short) is invalid too.
    short = _propose(client, rm, "M/s Orchid Castings Pvt Ltd PAN: AAACO123 OD 25L")["fields"]
    assert short["pan"]["status"] == "invalid" and short["pan"]["value"] == "AAACO123"
    # A range is unclear, with both readings.
    assert f["declared_turnover_inr"]["status"] == "unclear"
    assert [c["value"] for c in f["declared_turnover_inr"]["candidates"]] == ["30000000", "40000000"]


def test_tc01_duplicate_borrower_is_offered_and_needs_a_reason(client: TestClient):
    rm = sign_in(client, RM)
    first = client.post(
        "/api/cases",
        json={"borrower": "Kestrel Fabricators Pvt Ltd", "facilities": ["cash_credit"], "amount_inr": 5000000,
              "channel": "email", "pan": "AAACK1234F", "constitution": "private_limited"},
        headers=rm,
    )
    assert first.status_code == 201
    p = _propose(client, rm, CLEAN_EMAIL)
    assert [d["id"] for d in p["duplicates"]] == [first.json()["id"]]

    body = {"borrower": "Kestrel Fabricators Private Limited", "facilities": ["cash_credit"], "amount_inr": 5000000,
            "channel": "email", "pan": "AAACK1234F"}
    refused = client.post("/api/cases", json=body, headers=rm)
    assert refused.status_code == 409
    assert refused.json()["detail"]["duplicates"][0]["id"] == first.json()["id"]
    created = client.post("/api/cases", json={**body, "duplicate_override_reason": "Separate unit, new GSTIN"},
                          headers=rm)
    assert created.status_code == 201


def test_tc01_confirmed_proposal_keeps_both_values_and_the_message(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    p = _propose(client, rm, CLEAN_EMAIL)
    f = p["fields"]

    def header(name: str, confirmed: str | None = None) -> dict:
        span = f[name]["span"]
        return {"value": confirmed if confirmed is not None else f[name]["value"], "proposed": f[name]["value"],
                "source": f"message:{span['start']}-{span['end']}"}

    body = {
        "borrower": "Kestrel Fabricators Private Limited",
        "constitution": "private_limited",
        "facilities": ["cash_credit", "term_loan"],
        "amount_inr": 20000000,
        "channel": "email",
        "pan": "AAACK1234F",
        "header": {
            "borrower": header("borrower", "Kestrel Fabricators Private Limited"),
            "pan": header("pan"),
            "declared_turnover_inr": header("declared_turnover_inr"),
            "promoters": header("promoters"),
            "existing_banking": header("existing_banking"),
        },
        "message_text": CLEAN_EMAIL,
    }
    created = client.post("/api/cases", json=body, headers=rm)
    assert created.status_code == 201, created.text
    case = created.json()
    # RM edits keep both values (F-01.2, F-04.8).
    assert case["header"]["borrower"]["value"] == "Kestrel Fabricators Private Limited"
    assert case["header"]["borrower"]["proposed"] == "Kestrel Fabricators Pvt Ltd"
    assert case["header"]["borrower"]["source"].startswith("message:")
    # The message is the case's first document.
    docs = client.get(f"/api/cases/{case['id']}/documents", headers=rm).json()
    assert len(docs) == 1 and docs[0]["classification"]["types"] == ["application_message"]
    files = client.get(f"/api/cases/{case['id']}/files", headers=rm).json()
    assert files[0]["sha256"] == p["text_sha256"]
    # Declared figures are stored as the RM's unverified declaration (for F-19).
    conn = db.connect(published_data_root)
    try:
        declared = {r["field"]: dict(r) for r in conn.execute("SELECT * FROM declared_figures")}
    finally:
        conn.close()
    assert declared["declared_turnover_inr"]["value"] == "125000000"
    assert declared["declared_turnover_inr"]["basis"] == "RM declaration, unverified"
    assert declared["amount_inr"]["value"] == "20000000"
    # Promoters from the message are parties with the message as source (F-10.2).
    parties = client.get(f"/api/cases/{case['id']}/parties", headers=rm).json()
    assert {p["name"] for p in parties if p["role"] == "promoter"} == {"Tarun Velankar", "Ishita Barve"}
    assert all(p["source"].startswith("message:") for p in parties if p["role"] == "promoter")
    # The message page renders.
    image = client.get(f"/api/cases/{case['id']}/documents/{docs[0]['id']}/pages/1", headers=rm)
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")


def test_tc01_header_source_must_point_into_the_message(client: TestClient):
    rm = sign_in(client, RM)
    body = {"borrower": "Heronbay Polymers Pvt Ltd", "facilities": ["cash_credit"], "amount_inr": 5000000,
            "channel": "whatsapp", "message_text": "short",
            "header": {"borrower": {"value": "x", "proposed": "x", "source": "message:0-999"}}}
    assert client.post("/api/cases", json=body, headers=rm).status_code == 422


def test_tc01_without_confirmation_no_case_exists(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    _propose(client, rm, CLEAN_EMAIL)
    _propose(client, rm, WHATSAPP, channel="whatsapp")
    conn = db.connect(published_data_root)
    try:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
    finally:
        conn.close()
    assert client.get("/api/cases", headers=rm).json() == []


def test_tc01_proposal_permissions(client: TestClient):
    body = {"channel": "email", "text": "CC 50L"}
    assert client.post("/api/cases/proposals", json=body).status_code == 401
    assert client.post("/api/cases/proposals", json=body, headers=sign_in(client, MANAGER)).status_code == 403
    assert client.post("/api/cases/proposals", json=body, headers=sign_in(client, ANALYST)).status_code == 200
    bad = client.post("/api/cases/proposals", json={"channel": "fax", "text": "x"}, headers=sign_in(client, RM))
    assert bad.status_code == 422
