"""The model pass over bank-statement transactions the rules could not settle."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import bank_txns, cases, db, pipeline
from engine.ingest_client import IngestError, StubIngestClient
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import bank

# A synthetic, messy statement: what a bank prints when it does not say what an entry is. Every name is fictional.
MESSY = [
    {"date": "2025-04-03", "description": "TO TRANSFER-INB 8841 K MEHTA AGRO", "debit": 84_000},
    {"date": "2025-04-17", "description": "TO TRANSFER-INB 9915 K MEHTA AGRO", "debit": 91_000},
    {"date": "2025-04-09", "description": "BY TRANSFER 402211009988 ORCHID MART PAYMENT", "credit": 7_200},
    {"date": "2025-04-11", "description": "BY 004419 AMBER OILS", "credit": 310_000},
    {"date": "2025-05-02", "description": "ZZ-SETTLEMENT 77/ADJ", "debit": 1_250},
    {"date": "2025-05-05", "description": "NEFT DR SALARY", "debit": 120_000},
]
OPEN = {"TO TRANSFER-INB 8841 K MEHTA AGRO", "TO TRANSFER-INB 9915 K MEHTA AGRO",
        "BY TRANSFER 402211009988 ORCHID MART PAYMENT", "BY 004419 AMBER OILS", "ZZ-SETTLEMENT 77/ADJ"}

ANSWERS = {   # a cue in the narration -> (category, confidence)
    "mehta agro": ("supplier_payment", "high"),
    "orchid mart": ("customer_receipt", "medium"),
    "amber oils": ("customer_receipt", "low"),
}


class FakeModel:
    """Stands in for the document-processing service: answers by cue, records what it was asked."""

    def __init__(self, answers=ANSWERS, fail: Exception | None = None):
        self.answers, self.fail, self.requests = answers, fail, []

    def classify_transactions(self, request: dict) -> dict:
        self.requests.append(request)
        if self.fail:
            raise self.fail
        results = []
        for i in request["items"]:
            category, confidence = next((v for k, v in self.answers.items() if k in i["narration"].lower()), ("unknown", "low"))
            ids = {c["id"] for c in request["categories"] if c["direction"] == i["direction"]}
            results.append({"key": i["key"], "category": category if category in ids or category == "unknown" else "unknown",
                            "confidence": confidence, "reason": f"read {i['narration'][:18]}"})
        return {"model": "fake:model", "calls": 1, "results": results}


@pytest.fixture()
def ready(client: TestClient, published_data_root: Path):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root, borrower="Kestrel Tools Pvt Ltd")
    bank(published_data_root, case_id, MESSY)
    return client, headers, case_id, published_data_root


def rows(client, headers, case_id) -> dict[str, dict]:
    r = client.get(f"/api/cases/{case_id}/transactions", headers=headers, params={"limit": 1000})
    assert r.status_code == 200, r.text
    return {x["narration"]: x for x in r.json()["items"]}


def model_pass(root, case_id, fake):
    conn = db.connect(root)
    try:
        return bank_txns.run_model_pass(conn, root, cases.get_case(conn, case_id), fake)
    finally:
        conn.close()


def test_what_the_rules_cannot_settle_is_open_until_the_model_is_asked(ready):
    client, headers, case_id, _ = ready
    by = rows(client, headers, case_id)
    assert {n for n, r in by.items() if r["needs_review"]} == OPEN
    assert by["NEFT DR SALARY"]["method"] == "rule"


def test_the_model_is_asked_once_per_distinct_narration_with_only_the_published_categories(ready):
    client, headers, case_id, root = ready
    fake = FakeModel()
    result = model_pass(root, case_id, fake)
    assert result == {"asked": 4, "answered": 4, "error": None}      # the two Mehta Agro narrations differ only in digits
    (req,) = fake.requests
    keys = {i["key"] for i in req["items"]}
    assert keys == {"debit:to transfer-inb # k mehta agro", "credit:by transfer # orchid mart payment",
                    "credit:by # amber oils", "debit:zz-settlement #/adj"}
    mehta = next(i for i in req["items"] if "mehta" in i["narration"].lower())
    assert mehta["amount"] in (84_000, 91_000) and mehta["direction"] == "debit"
    assert "salary" not in str(req["items"]).lower()                  # a row the rules settled is not sent
    cats = {c["id"] for c in req["categories"]}
    assert {"customer_receipt", "supplier_payment", "other_debit", "other_credit"} <= cats and req["config_version"]
    assert set(req) == {"config_version", "categories", "items"}      # no case, no borrower, no account in the request


def test_a_confident_answer_settles_every_row_with_that_narration(ready):
    client, headers, case_id, root = ready
    model_pass(root, case_id, FakeModel())
    by = rows(client, headers, case_id)
    for n in ("TO TRANSFER-INB 8841 K MEHTA AGRO", "TO TRANSFER-INB 9915 K MEHTA AGRO"):
        r = by[n]
        assert (r["category"], r["method"], r["status"], r["needs_review"], r["rule_id"]) == ("supplier_payment", "model", "matched", False, None)
        assert r["confidence"] == 0.9 and r["reason"].startswith("read TO TRANSFER")
    orchid = by["BY TRANSFER 402211009988 ORCHID MART PAYMENT"]
    assert (orchid["category"], orchid["method"], orchid["confidence"]) == ("customer_receipt", "model", 0.75)   # medium is accepted


def test_a_low_confidence_or_unknown_answer_stays_open_with_a_suggestion(ready):
    client, headers, case_id, root = ready
    model_pass(root, case_id, FakeModel())
    by = rows(client, headers, case_id)
    amber = by["BY 004419 AMBER OILS"]
    assert (amber["method"], amber["needs_review"], amber["category"], amber["candidates"]) == ("rule", True, "other_credit", ["customer_receipt"])
    assert amber["reason"].startswith("read BY 004419")
    odd = by["ZZ-SETTLEMENT 77/ADJ"]
    assert (odd["needs_review"], odd["category"], odd["candidates"]) == (True, "other_debit", [])
    s = client.get(f"/api/cases/{case_id}/transactions/summary", headers=headers).json()
    assert (s["by_model"], s["by_rule"], s["unsettled"]) == (3, 1, 2)


def test_a_category_of_the_wrong_direction_is_not_taken(ready):
    client, headers, case_id, root = ready
    model_pass(root, case_id, FakeModel(answers={"orchid mart": ("salary", "high"), "mehta agro": ("supplier_payment", "high")}))
    r = rows(client, headers, case_id)["BY TRANSFER 402211009988 ORCHID MART PAYMENT"]
    assert (r["needs_review"], r["category"]) == (True, "other_credit")


def test_the_answers_are_kept_and_the_model_is_not_asked_again(ready):
    client, headers, case_id, root = ready
    model_pass(root, case_id, FakeModel())
    again = FakeModel()
    assert model_pass(root, case_id, again) == {"asked": 0, "answered": 0, "error": None} and again.requests == []


def test_the_review_item_counts_only_what_is_still_open(ready):
    client, headers, case_id, root = ready
    rows(client, headers, case_id)
    queue = lambda: [i for i in client.get("/api/review", params={"case_id": case_id}, headers=headers).json() if i["kind"] == "transactions"]
    assert queue()[0]["summary"] == "5 transactions on Lotuscrest Bank ·1234 could not be classified"
    model_pass(root, case_id, FakeModel())
    assert queue()[0]["summary"] == "2 transactions on Lotuscrest Bank ·1234 could not be classified"


def test_a_person_decides_over_the_model_and_a_decided_row_is_not_asked(ready):
    client, headers, case_id, root = ready
    txn = rows(client, headers, case_id)["ZZ-SETTLEMENT 77/ADJ"]["txn_id"]
    client.put(f"/api/cases/{case_id}/transactions/{txn}/category", headers=headers, json={"category": "bank_charges", "reason": "Passbook entry"})
    fake = FakeModel()
    assert model_pass(root, case_id, fake)["asked"] == 3 and all("zz-settlement" not in i["narration"].lower() for i in fake.requests[0]["items"])
    mine = rows(client, headers, case_id)["ZZ-SETTLEMENT 77/ADJ"]
    assert (mine["category"], mine["method"]) == ("bank_charges", "manual")


def test_a_failed_call_leaves_the_rows_open_and_is_reported_not_raised(ready):
    client, headers, case_id, root = ready
    result = model_pass(root, case_id, FakeModel(fail=IngestError("ingest service answered 502: replay_miss")))
    assert result["answered"] == 0 and "replay_miss" in result["error"]
    s = client.get(f"/api/cases/{case_id}/transactions/summary", headers=headers).json()
    assert (s["unsettled"], s["by_model"]) == (5, 0) and "replay_miss" in s["model_error"]
    model_pass(root, case_id, FakeModel())                              # the next attempt succeeds and clears it
    assert client.get(f"/api/cases/{case_id}/transactions/summary", headers=headers).json()["model_error"] is None


def test_a_malformed_answer_is_an_error_not_a_label(ready):
    client, headers, case_id, root = ready

    class Bad(FakeModel):
        def classify_transactions(self, request):
            return {"model": "fake", "calls": 1, "results": [{"key": "oops"}]}

    result = model_pass(root, case_id, Bad())
    assert result["answered"] == 0 and rows(client, headers, case_id)["BY 004419 AMBER OILS"]["needs_review"]


def test_a_new_configuration_version_asks_again(ready):
    client, headers, case_id, root = ready
    model_pass(root, case_id, FakeModel())
    conn = db.connect(root)
    try:
        conn.execute("UPDATE txn_model_labels SET config_version = 'an-earlier-version' WHERE case_id = ?", (case_id,))
        conn.commit()
    finally:
        conn.close()
    assert all(r["needs_review"] for n, r in rows(client, headers, case_id).items() if n in OPEN)    # the old answers no longer apply
    again = FakeModel()
    assert model_pass(root, case_id, again)["asked"] == 4


def test_one_case_asks_for_no_more_narrations_than_the_cap(ready, monkeypatch):
    client, headers, case_id, root = ready
    real = bank_txns.reader.load_txn_classification

    def capped(r):
        cfg = real(r).model_copy(deep=True)
        cfg.model.max_narrations = 2
        return cfg

    monkeypatch.setattr(bank_txns.reader, "load_txn_classification", capped)
    fake = FakeModel()
    assert model_pass(root, case_id, fake)["asked"] == 2 and len(fake.requests[0]["items"]) == 2


def test_the_model_pass_can_be_switched_off_in_configuration(ready, monkeypatch):
    client, headers, case_id, root = ready
    real = bank_txns.reader.load_txn_classification

    def off(r):
        cfg = real(r).model_copy(deep=True)
        cfg.model.enabled = False
        return cfg

    monkeypatch.setattr(bank_txns.reader, "load_txn_classification", off)
    fake = FakeModel()
    assert model_pass(root, case_id, fake) == {"asked": 0, "answered": 0, "error": None} and fake.requests == []


def test_processing_asks_the_model_but_a_decision_elsewhere_does_not(ready):
    client, headers, case_id, root = ready
    fake = FakeModel()
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)                       # a review decision, case creation: rules only
        assert fake.requests == []
        pipeline.refresh_case(conn, root, case_id, client=fake)          # documents were processed
        assert len(fake.requests) == 1
    finally:
        conn.close()
    assert rows(client, headers, case_id)["TO TRANSFER-INB 8841 K MEHTA AGRO"]["method"] == "model"


def test_the_stub_service_has_no_model_so_rows_stay_for_a_person(ready):
    client, headers, case_id, root = ready
    result = model_pass(root, case_id, StubIngestClient())
    assert result["answered"] == 0 and "no model" in result["error"]
    assert rows(client, headers, case_id)["ZZ-SETTLEMENT 77/ADJ"]["needs_review"]


def test_a_category_only_the_case_can_decide_is_never_offered_to_the_model(ready):
    client, headers, case_id, root = ready
    fake = FakeModel()
    model_pass(root, case_id, fake)
    offered = {c["id"] for c in fake.requests[0]["categories"]}
    assert not offered & {"own_transfer_in", "own_transfer_out"} and "supplier_payment" in offered


def test_a_category_that_takes_money_out_of_business_inflow_needs_the_model_to_be_sure(ready):
    client, headers, case_id, root = ready
    model_pass(root, case_id, FakeModel(answers={"amber oils": ("loan_disbursal", "medium"), "orchid mart": ("loan_disbursal", "high")}))
    by = rows(client, headers, case_id)
    amber = by["BY 004419 AMBER OILS"]
    assert (amber["needs_review"], amber["category"], amber["candidates"]) == (True, "other_credit", ["loan_disbursal"])
    orchid = by["BY TRANSFER 402211009988 ORCHID MART PAYMENT"]
    assert (orchid["needs_review"], orchid["category"], orchid["method"], orchid["confidence"]) == (False, "loan_disbursal", "model", 0.9)
