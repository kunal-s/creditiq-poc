"""The PD question note (FRD F-24; test plan TC-27): questions for the personal discussion with the
promoter, from the findings, the deviations and the gaps, each the bare question with why it is asked
(its finding's explanation, or its norm) and its evidence; findings that ask the same asked once, the
checks not completed asked together by topic; asked by topic, ranked and numbered; with the header,
the people to meet, the record of the discussion, the documents to collect and the sign-off. Every
name is fictional."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from engine.configstore import reader
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

SEVERITY = {"serious": 0, "moderate": 1, "mild": 2}
SOURCE = {"finding": 0, "deviation": 1, "gap": 2}
TOPICS = ["identity", "turnover", "accounts", "obligations", "policy"]
TOPIC = {"identity": "identity", "authority": "identity", "turnover": "turnover", "tax": "turnover",
         "financials": "turnover", "accounts": "accounts", "obligations": "obligations"}
VERSION_LABEL = re.compile(r"Version \d+ \(published \d{1,2} [A-Z][a-z]{2} \d{4}\)")
# A bare question that leans on a sentence it no longer follows.
UNRESOLVED = re.compile(r"\b(?:explains? it|provide it|is it expected)\b|the difference\?|the documents be available")


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _pd(client: TestClient, headers: dict, root: Path, case_id: str) -> dict:
    _refresh(root, case_id)
    response = client.get(f"/api/cases/{case_id}/pd-note", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _note(client: TestClient, headers: dict, root: Path, case_id: str) -> list[dict]:
    return _pd(client, headers, root, case_id)["questions"]


def _board(client: TestClient, headers: dict, case_id: str) -> dict:
    return client.get(f"/api/cases/{case_id}/cross-verification", headers=headers).json()


def _case(client: TestClient, analyst: dict, root: Path) -> str:
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=40_000_000)
    # Long-term borrowings of 10 cr: debt / equity 2.67x, a deviation.
    audited(root, case_id, set_rows={"(a) Long-term borrowings": 100_000_000}, page=4)
    bank(root, case_id, [{"date": f"{p}-05", "description": "NACH DR ASHWOOD FINSERV", "debit": 145_000} for p in months((2025, 4), 6)])
    add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(root, case_id, "income_tax_return", {"pan": "AAACK9876Q"})  # a second PAN: a serious finding
    return case_id


def _directors(root: Path, case_id: str) -> None:
    """The memorandum names Tarun Velankar and Sunil Karve; only Tarun Velankar has a KYC."""
    add_doc(root, case_id, "memorandum_articles_of_association", {
        "directors": [{"name": "Tarun Velankar", "din": "01234567"}, {"name": "Sunil Karve", "din": "09123456"}]})
    add_doc(root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567", "pan": "ABCPV1234K",
                                            "designation": "Director"})


def _asked(questions: list[dict]) -> set[str]:
    """Every board reference the note asks about, merged or not."""
    return {q["xv_ref"] for q in questions if q["xv_ref"]} | {a["xv_ref"] for q in questions for a in q["also"] if a["xv_ref"]}


def test_tc27_questions_come_from_findings_deviations_and_gaps(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    questions = _note(client, analyst, published_data_root, case_id)
    finding = next(i["finding"] for i in _board(client, analyst, case_id)["items"] if i["finding"]["rule_id"] == "ID-01")
    pan = next(q for q in questions if q["rule"] == "ID-01")
    assert (pan["source"], pan["severity"], pan["area"], pan["status"], pan["target"]) == (
        "finding", "serious", "identity", "Open", "cross_verification")
    assert (pan["ref"], pan["xv_ref"], pan["title"]) == (finding["id"], finding["ref"], "Entity PAN differs between documents")
    # The bare question; why it is asked is the finding's explanation (the reference is beside it).
    assert pan["question"] == "Which PAN is the entity's, and why does the other document show a different one?"
    assert pan["context"] == finding["explanation"]
    assert "AAACK9876Q" in pan["context"] and pan["text"] == f"{pan['context']} {pan['question']}"
    assert pan["evidence"] and pan["also"] == []
    de = next(q for q in questions if q["rule"] == "FR-05")
    assert (de["source"], de["area"], de["xv_ref"], de["status"]) == ("deviation", "policy", None, None)
    assert de["context"] == "Debt / equity is 2.67x in FY 2025-26 against a norm of at most 2.00x."
    # The question names what it asks about.
    assert "debt / equity" in de["question"] and not UNRESOLVED.search(de["question"])
    gaps = [q for q in questions if q["source"] == "gap"]
    assert gaps and all(q["severity"] == "mild" for q in gaps if q["target"] == "policy")
    # What is not on file is named inside the sentence, as the memo says it.
    vintage = next(q for q in gaps if q["rule"] == "EL-01")
    assert vintage["context"] == "Business vintage could not be assessed: the date of incorporation is not on file."


def test_questions_are_asked_by_topic_ranked_within_it_and_numbered_across_the_note(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    _directors(published_data_root, case_id)
    note = _pd(client, analyst, published_data_root, case_id)
    questions = note["questions"]
    assert [q["number"] for q in questions] == list(range(1, len(questions) + 1))
    topics = note["topics"]
    assert [t["area"] for t in topics] == [a for a in TOPICS if any(q["area"] == a for q in questions)]
    assert {t["area"]: t["title"] for t in topics}.items() <= {
        "identity": "Identity and KYC", "turnover": "Turnover, tax and sales", "accounts": "Bank accounts",
        "obligations": "Existing borrowings", "policy": "Policy norms"}.items()
    assert [i for t in topics for i in t["question_ids"]] == [q["id"] for q in questions]
    for t in topics:
        asked = [q for q in questions if q["id"] in t["question_ids"]]
        assert all(q["area"] == t["area"] for q in asked)
        keys = [(SEVERITY[q["severity"]], SOURCE[q["source"]]) for q in asked]
        assert keys == sorted(keys), t["area"]
    assert {"identity", "policy"} <= {t["area"] for t in topics}


def test_a_finding_found_not_valid_is_not_asked(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    _note(client, analyst, published_data_root, case_id)
    item = next(i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
                if i["kind"] == "finding" and "ID-01" in i["summary"])
    client.post(f"/api/review/{item['id']}/decision",
                json={"decision": "waive", "reason": "The second PAN is a typing error in the return"}, headers=analyst)
    assert not [q for q in _note(client, analyst, published_data_root, case_id) if q["rule"] == "ID-01"]


def test_an_accepted_or_escalated_finding_is_asked_with_its_status(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    _directors(published_data_root, case_id)
    _refresh(published_data_root, case_id)
    failed = {i["finding"]["rule_id"]: i["finding"]["id"] for i in _board(client, analyst, case_id)["items"]
              if i["finding"]["outcome"] == "fail"}
    for rule, decision in (("ID-01", "escalate"), ("ID-08", "accept")):
        response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{failed[rule]}/decision",
                               json={"decision": decision, "comment": "Reviewed with the documents"}, headers=analyst)
        assert response.status_code == 200, response.text
    questions = {q["rule"]: q for q in _note(client, analyst, published_data_root, case_id)}
    # Accept means a valid finding, still to be discussed.
    assert (questions["ID-01"]["status"], questions["ID-08"]["status"]) == ("Escalated", "Accepted as valid")


def test_a_question_names_who_it_is_about(client: TestClient, published_data_root: Path):
    """ID-08's question names the director the explanation is about."""
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root,
                        header={"promoters": {"value": "Tarun Velankar", "source": "person"}})
    _directors(published_data_root, case_id)
    q = next(q for q in _note(client, analyst, published_data_root, case_id) if q["rule"] == "ID-08")
    assert "Sunil Karve" in q["question"] and q["question"].endswith("?")
    assert q["context"] == next(i["finding"]["explanation"] for i in _board(client, analyst, case_id)["items"]
                                if i["finding"]["rule_id"] == "ID-08")


def test_a_check_with_nothing_to_ask_the_promoter_is_not_asked(client: TestClient, published_data_root: Path):
    """A check left incomplete only because a value waits for a person's review is an internal step."""
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"}, pending={"pan"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK9876Q"})
    _refresh(published_data_root, case_id)
    board = _board(client, analyst, case_id)
    pan = next(i["finding"] for i in board["items"] if i["finding"]["rule_id"] == "ID-01")
    assert pan["outcome"] == "incomplete" and pan["request"] is None
    questions = _note(client, analyst, published_data_root, case_id)
    assert not [q for q in questions if q["rule"] == "ID-01" or pan["id"] in {a["ref"] for a in q["also"]}]
    for gap in (q for q in questions if q["source"] == "gap" and q["target"] == "cross_verification"):
        assert gap["title"] in gap["context"] and gap["text"] == f"{gap['context']} {gap['question']}"
        asked = [i["finding"] for i in board["items"] if i["finding"]["id"] in {gap["ref"], *(a["ref"] for a in gap["also"])}]
        assert asked and all(f["outcome"] == "incomplete" and f["request"] for f in asked)


def test_the_gaps_of_a_topic_are_asked_together_naming_what_would_complete_them(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(root, case_id, "2026-03-31")
    for period in ("April 2025", "May 2025", "June 2025", "July 2025", "August 2025", "September 2025", "October 2025"):
        gstr(root, case_id, period, 10_000_000)
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 9_000_000}
                         for ym in months((2025, 4), 7)], end="2025-10-31")
    questions = _note(client, analyst, root, case_id)
    board = _board(client, analyst, case_id)
    findings = {i["finding"]["id"]: i["finding"] for i in board["items"]}
    # Months short: nothing the documents to collect already ask for.
    turnover = [f for f in findings.values() if f["outcome"] == "incomplete" and f["request"] and not f["missing"]
                and TOPIC[f["area"]] == "turnover"]
    assert len(turnover) > 1
    gaps = [q for q in questions if q["source"] == "gap" and q["target"] == "cross_verification"]
    # One question a topic, the most severe check first, the others beside it.
    assert len({q["area"] for q in gaps}) == len(gaps)
    [gap] = [q for q in gaps if q["area"] == "turnover"]
    asked = [findings[r] for r in (gap["ref"], *(a["ref"] for a in gap["also"]))]
    assert {f["id"] for f in turnover} <= {f["id"] for f in asked}
    assert SEVERITY[gap["severity"]] == min(SEVERITY[f["severity"]] for f in asked)
    # What would complete them, each named once.
    if "{request}" in reader.load_crosschecks(root).pd_incomplete:
        for f in turnover:
            assert f["request"] in gap["question"] or any(
                f["request"] in other["request"] for other in turnover if other is not f), f["rule_id"]
    assert all(f["title"] in gap["context"] for f in asked)


def test_a_gap_whose_documents_are_to_be_collected_is_not_asked_again(client, published_data_root):
    """No memorandum and no KYC: the identity checks wait for them, and so do the documents to collect."""
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, header={"promoters": {"value": "Tarun Velankar", "source": "person"}})
    add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F", "company_name": "Kestrel Tools Private Limited"})
    note = _pd(client, analyst, root, case_id)
    board = _board(client, analyst, case_id)
    waiting = [i["finding"] for i in board["items"] if i["finding"]["outcome"] == "incomplete"
               and i["finding"]["area"] == "identity" and i["finding"]["request"]]
    assert any("Director KYC" in f["missing"] for f in waiting)
    collect = " ".join(d["text"] for d in note["documents_to_collect"])
    assert "KYC" in collect and "Memorandum" in collect
    asked = {q["ref"] for q in note["questions"]} | {a["ref"] for q in note["questions"] for a in q["also"]}
    collected = [f for f in waiting if f["missing"] and all(m in ("Director KYC", "Memorandum and articles of association")
                                                             for m in f["missing"])]
    assert collected and not {f["id"] for f in collected} & asked


def test_a_norm_not_assessed_is_asked_with_the_reason_the_memo_gives(client, published_data_root):
    """The term loan's instalment is not on file: the DSCR question says so in the memo's words."""
    from tests.test_cam import _full_case

    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, _ = _full_case(client, analyst, root)
    questions = _note(client, analyst, root, case_id)
    cam = client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()
    unassessed = {i["ref"]: i["text"] for i in cam["summary"] if i["kind"] == "unassessed"}
    gaps = [q for q in questions if q["source"] == "gap" and q["target"] == "policy"]
    assert gaps and all(q["context"] == unassessed[q["rule"]] for q in gaps)
    dscr = next(q for q in gaps if q["rule"] == "FR-03")
    assert dscr["context"] == "DSCR could not be assessed: the proposed term loan's instalment is not on file."
    assert dscr["question"].startswith("What will the term loan finance")


def test_a_norm_in_words_is_asked_as_the_memo_states_it(client: TestClient, published_data_root: Path):
    """Positive net worth and no blocking item open read "where the norm is positive", never "against a
    norm of positive"."""
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(root, case_id, set_rows={"(b) Reserves and surplus": -150_000_000})
    questions = {q["rule"]: q for q in _note(client, analyst, root, case_id)}
    norms = {n["id"]: n for n in client.get(f"/api/cases/{case_id}/policy", headers=analyst).json()["norms"]}
    assert norms["EL-03"]["outcome"] == norms["DOC-01"]["outcome"] == "deviation"
    assert questions["EL-03"]["context"] == (f"Net worth is {norms['EL-03']['actual_text']} in FY 2025-26, where the "
                                             "norm is positive.")
    assert questions["DOC-01"]["context"] == (f"Blocking checklist items open: {norms['DOC-01']['actual_text']}, "
                                              "where the norm is none.")
    assert not any(re.search(r"a norm of (?:positive|no loss|none)\b", q["text"]) for q in questions.values())


@pytest.mark.parametrize("rule", ["EL-01", "FR-05", "DOC-02"])
def test_each_deviation_family_has_its_question(client: TestClient, published_data_root: Path, rule):
    from engine import pd_note

    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    q = next(q for q in _note(client, analyst, published_data_root, case_id) if q["rule"] == rule)
    assert q["severity"] == "moderate" and q["source"] == "deviation" and q["evidence"] and q["target"] == "policy"
    # The question as configured (the norm's own, else its family's), naming what it asks about.
    policy = reader.load_policy(published_data_root)
    n = next(n for n in client.get(f"/api/cases/{case_id}/policy", headers=analyst).json()["norms"] if n["id"] == rule)
    config = next(c for c in policy.norms if c.id == rule)
    template = config.pd_question or policy.pd_questions[n["family"]]
    worded = template
    for key, value in (("label", n["label"]), ("subject", n["label"][:1].lower() + n["label"][1:]),
                       ("actual", n["actual_text"]), ("required", n["required"]), ("period", "FY 2025-26")):
        worded = worded.replace("{" + key + "}", value)
    assert q["question"] == pd_note.split(worded)[1] and not UNRESOLVED.search(q["question"])


def test_question_template_prefers_the_norms_own_question(published_data_root: Path):
    from engine import pd_note
    from engine.contracts import NormResult

    policy_config = reader.load_policy(published_data_root)
    configured = {n.id: n for n in policy_config.norms}

    def result(norm_id, outcome, reason=None):
        n = configured[norm_id]
        return NormResult(id=norm_id, family=n.family, label=norm_id, formula="", required="", outcome=outcome,
                          category=n.category, category_label=n.category, reason=reason)

    own = configured["FR-05"].model_copy(update={"pd_question": "Own question about {label}."})
    assert pd_note.question_template(own, policy_config, result("FR-05", "deviation")) == "Own question about {label}."
    assert pd_note.question_template(configured["EL-02"], policy_config, result("EL-02", "cannot_evaluate")) is None
    assert pd_note.question_template(configured["FR-02"], policy_config, result("FR-02", "cannot_evaluate", "awaiting_review")) is None
    assert pd_note.question_template(configured["FR-04"], policy_config, result("FR-04", "cannot_evaluate", "zero_denominator")) \
        == policy_config.pd_questions["zero_denominator"]
    # A norm's own question for when it cannot be evaluated; else the general one.
    gap = configured["FR-04"].model_copy(update={"pd_gap_question": "What will the loan finance?"})
    assert pd_note.question_template(gap, policy_config, result("FR-04", "cannot_evaluate")) == "What will the loan finance?"
    plain = configured["FR-04"].model_copy(update={"pd_gap_question": None})
    assert pd_note.question_template(plain, policy_config, result("FR-04", "cannot_evaluate")) \
        == policy_config.pd_questions["cannot_evaluate"]


def test_a_worded_question_splits_into_why_and_what_is_asked():
    from engine.pd_note import split

    assert split("Debt / equity is 2.67x in FY 2025-26 against a norm of at most 2.00x. What explains it, and how is "
                 "it expected to move?") == ("Debt / equity is 2.67x in FY 2025-26 against a norm of at most 2.00x.",
                                             "What explains it, and how is it expected to move?")
    assert split("Revenue fell. Why? Will it recover?") == ("Revenue fell.", "Why? Will it recover?")
    assert split("No question here.") == ("No question here.", "")


def test_questions_link_to_their_tab(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    questions = _note(client, analyst, published_data_root, case_id)
    assert next(q for q in questions if q["rule"] == "ID-01")["target"] == "cross_verification"
    assert next(q for q in questions if q["rule"] == "FR-05")["target"] == "policy"
    gaps = [q for q in questions if q["source"] == "gap" and not q["rule"].startswith(("EL", "FR", "DOC"))]
    assert gaps and all(q["target"] == "cross_verification" for q in gaps)


def test_the_note_names_the_people_to_meet_and_leaves_the_record_blank(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd",
                        header={"promoters": {"value": "Tarun Velankar; Sunil Karve", "source": "person"}})
    _directors(root, case_id)
    note = _pd(client, analyst, root, case_id)
    assert (note["title"], note["borrower"], note["case_id"], note["as_of"]) == (
        "Personal discussion — question note", "Kestrel Tools Pvt Ltd", case_id, "2026-09-29")
    assert note["record_fields"] == ["Date of discussion", "Place", "Bank officials present",
                                     "Promoters or representatives present"]
    assert [{k: p[k] for k in ("name", "role", "din", "sources")} for p in note["people"]] == [
        {"name": "Tarun Velankar", "role": "Director", "din": "01234567",
         "sources": ["Memorandum and articles of association", "Director KYC", "Sourcing message"]},
        {"name": "Sunil Karve", "role": "Director", "din": "09123456",
         "sources": ["Memorandum and articles of association", "Sourcing message"]},
    ]
    # Cited to the documents that name them (the sourcing message here was typed in, with no page).
    assert all(p["evidence"] for p in note["people"])


def test_the_header_and_the_sign_off_come_with_the_note(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = _case(client, analyst, root)
    note = _pd(client, analyst, root, case_id)
    config = reader.load_cam(root).pd_note
    labels = config.labels
    header = {f["label"]: f["value"]["text"] for f in note["header"]}
    assert header == {
        labels.get("borrower", "Borrower"): "Example Tools Pvt Ltd", labels.get("case_id", "Case ID"): case_id,
        labels.get("constitution", "Constitution"): "Private limited",
        labels.get("proposal", "Proposal"): "Cash credit, INR 4.00 cr",
        labels.get("data_as_of", "Data as of"): "29 Sep 2026",
        labels.get("configuration", "Configuration version"): note["config_label"]}
    assert VERSION_LABEL.fullmatch(note["config_label"])
    assert [s["role"] for s in note["sign_off"]] == config.sign_off == ["Discussion held by"]
    assert note["labels"] == labels


def test_differing_dins_are_attributed_and_cited(client: TestClient, published_data_root: Path):
    from tests.test_cam import _full_case

    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    note = _pd(client, analyst, published_data_root, case_id)
    ishita = next(p for p in note["people"] if p["name"] == "Ishita Barve")
    assert ishita["din"] == "07654321 (Memorandum and articles of association); 07654322 (Director KYC)"
    assert {docs["memorandum"], docs["kyc_ishita"]} <= {e["document_id"] for e in ishita["evidence"]}
    # The people are read before the questions: their pages are numbered first.
    assert note["sources"][0]["document_id"] == note["people"][0]["evidence"][0]["document_id"]


def test_every_finding_not_found_not_valid_is_asked_and_none_relies_on_a_sentence_it_drops(client, published_data_root):
    """Including a failed finding whose rule has no question of its own, and those asked together."""
    from tests.test_cam import _full_case

    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, _ = _full_case(client, analyst, root)
    questions = _note(client, analyst, root, case_id)
    failed = [i["finding"] for i in _board(client, analyst, case_id)["items"] if i["finding"]["outcome"] == "fail"]
    assert failed and {f["ref"] for f in failed} <= _asked(questions)
    for q in questions:
        assert q["question"].endswith("?") and not UNRESOLVED.search(q["question"]), q["question"]
    rules = {r.id: r for r in reader.load_crosschecks(root).rules}
    fallback = [f for f in failed if not rules[f["rule_id"]].pd_question]
    for f in fallback:
        q = next(q for q in questions if q["xv_ref"] == f["ref"] or f["ref"] in {a["xv_ref"] for a in q["also"]})
        assert q["question"], f["rule_id"]


def test_a_question_cites_the_rows_its_finding_is_about(client: TestClient, published_data_root: Path):
    """ID-06 cites the flagged director's KYC, not the first KYC on file; BA-01 the sourcing message that
    declares the account; as the memo cites them."""
    from tests.test_cam import _full_case

    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, docs = _full_case(client, analyst, root)
    questions = _note(client, analyst, root, case_id)
    identifiers = next(q for q in questions if q["rule"] == "ID-06")
    cited = {e["document_id"] for e in identifiers["evidence"]}
    assert {docs["kyc_ishita"], docs["memorandum"]} <= cited and docs["kyc_tarun"] not in cited
    declared = next(q for q in questions if "BA-01" in {q["rule"], *(a["rule"] for a in q["also"])})
    assert docs["message"] in {e["document_id"] for e in declared["evidence"]}


def test_a_failed_finding_whose_rule_asks_nothing_is_put_the_general_question(client, published_data_root):
    """A rule published without a question of its own: its finding is still asked (crosschecks pd_finding)."""
    from tests.test_cam import _full_case

    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, _ = _full_case(client, analyst, root)
    _refresh(root, case_id)
    path = root / "config_store" / "versions" / reader.published_version(root)["version"] / "crosschecks.json"
    section = json.loads(path.read_text(encoding="utf-8"))
    for rule in section["rules"]:
        if rule["id"] == "BA-01":
            rule.pop("pd_question", None)
    path.write_text(json.dumps(section), encoding="utf-8")
    reader._load_section_json.cache_clear()
    try:
        finding = next(i["finding"] for i in _board(client, analyst, case_id)["items"] if i["finding"]["rule_id"] == "BA-01")
        assert finding["outcome"] == "fail"
        questions = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()["questions"]
        q = next(q for q in questions if q["xv_ref"] == finding["ref"])
        general = getattr(reader.load_crosschecks(root), "pd_finding", None) or (
            "{explanation} What is the position, and what will be provided?")
        assert q["question"] == general.replace("{explanation}", "").strip()
        assert (q["context"], q["area"], q["source"]) == (finding["explanation"], "accounts", "finding")
    finally:
        reader._load_section_json.cache_clear()


def test_findings_of_a_topic_that_ask_the_same_are_asked_once(client, published_data_root):
    from tests.test_cam import _full_case

    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, _ = _full_case(client, analyst, root)
    questions = _note(client, analyst, root, case_id)
    failed = [i["finding"] for i in _board(client, analyst, case_id)["items"] if i["finding"]["outcome"] == "fail"]
    rules = {r.id: r for r in reader.load_crosschecks(root).rules}
    alike: dict[tuple[str, str], list[dict]] = {}
    for f in failed:
        asked = (rules[f["rule_id"]].pd_question or "").replace("{explanation}", "").strip()
        if asked and "{" not in asked:
            alike.setdefault((TOPIC[f["area"]], asked), []).append(f)
    shared = [found for found in alike.values() if len(found) > 1]
    assert shared, "the configuration asks one question for several findings of a topic"
    for found in shared:
        [q] = [q for q in questions if q["xv_ref"] in {f["ref"] for f in found}]
        assert {q["xv_ref"], *(a["xv_ref"] for a in q["also"])} == {f["ref"] for f in found}
        for f in found:
            assert f"{f['explanation'].rstrip('.')} ({f['ref']})." in q["context"]
        assert all(e in q["evidence"] for a in q["also"] for e in a["evidence"])


def test_the_documents_to_collect_are_the_open_requests_for_documents(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    note = _pd(client, analyst, published_data_root, case_id)
    queries = client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
    wanted = [q for q in queries if not q["resolved"] and q["group"] in ("documents_needed", "documents_to_redo")]
    assert wanted and [d["text"] for d in note["documents_to_collect"]] == [q["text"] for q in wanted]
    assert [d["citations"] for d in note["documents_to_collect"]] == [q["evidence"] for q in wanted]
    assert not {q["text"] for q in queries if q["group"] == "clarifications"} & {d["text"] for d in note["documents_to_collect"]}


def test_sources_are_numbered_by_first_citation(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    note = _pd(client, analyst, published_data_root, case_id)
    cited = ([e for f in note["header"] for e in f["value"]["citations"]] + [e for p in note["people"] for e in p["evidence"]]
             + [e for q in note["questions"] for e in q["evidence"]]
             + [e for d in note["documents_to_collect"] for e in d["citations"]])
    order = list(dict.fromkeys(e["document_id"] for e in cited))
    assert order and [(s["number"], s["document_id"]) for s in note["sources"]] == list(enumerate(order, start=1))
    for s in note["sources"]:
        assert s["pages"] == sorted({e["page"] for e in cited if e["document_id"] == s["document_id"]})
    statements = next(s for s in note["sources"] if s["label"] == "Audited financial statements")
    assert statements["pages"] == [4] and statements["file_name"].startswith("audited_financial_statements-")


def test_the_same_case_gives_the_same_note(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    _directors(published_data_root, case_id)
    first = _pd(client, analyst, published_data_root, case_id)
    again = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
