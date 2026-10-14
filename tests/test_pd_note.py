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
from engine.cam import plain
from engine.configstore import reader
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

SEVERITY = {"serious": 0, "moderate": 1, "mild": 2}
SOURCE = {"finding": 0, "deviation": 1, "observation": 2, "gap": 3}
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
    # It names the values its sides give, in side order, where the configured wording asks for them.
    values = " and ".join(dict.fromkeys(str(side["value"]) for side in finding["sides"]))
    worded = next(r for r in reader.load_crosschecks(published_data_root).rules if r.id == "ID-01").pd_question
    assert pan["question"] == worded.replace("{explanation}", "").replace("{values}", values).strip()
    assert "{values}" not in worded or ("AAACK1234F" in pan["question"] and "AAACK9876Q" in pan["question"])
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
    # Named as the memo names them: business credits, never cleansed bank credits.
    assert all(plain(f["title"]) in gap["context"] for f in asked)
    assert "cleansed" not in gap["context"]


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
    assert questions["DOC-01"]["context"] == (f"Blocking checklist items open: {norms['DOC-01']['actual_text']}; "
                                              "the norm allows none.")
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
    # {s}: the plural ending for how far the actual is from the norm ("the year not on file").
    ratio = next((r for r in policy.ratios if r.key == config.ratio), None)
    shortfall = abs((config.threshold if config.threshold is not None else ratio.acceptable) - n["actual"])
    worded = template
    for key, value in (("label", n["label"]), ("subject", n["label"][:1].lower() + n["label"][1:]),
                       ("actual", n["actual_text"]), ("required", n["required"]), ("period", "FY 2025-26"),
                       ("s", "" if shortfall == 1 else "s")):
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
    """GST returns and the books well above the business credits for FY 2025-26: the checks that come to
    the same question for the year are asked once."""
    from tests.test_cam import FY26, PERIODS

    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(root, case_id)
    for period in PERIODS:
        gstr(root, case_id, period, 10_000_000)
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 7_500_000}
                         for ym in FY26])
    questions = _note(client, analyst, root, case_id)
    failed = [i["finding"] for i in _board(client, analyst, case_id)["items"] if i["finding"]["outcome"] == "fail"]
    rules = {r.id: r for r in reader.load_crosschecks(root).rules}
    alike: dict[tuple[str, str], list[dict]] = {}
    for f in failed:
        # The question as worded for the finding: its year or months where the wording names them.
        asked = (rules[f["rule_id"]].pd_question or "").replace("{explanation}", "").replace(
            "{period}", f["scope"] or "").strip()
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
    # Statements are named by their year even where the case has one set.
    statements = next(s for s in note["sources"] if s["label"] == "Audited financial statements · FY 2025-26")
    assert statements["pages"] == [4] and statements["file_name"].startswith("audited_financial_statements-")


def test_the_same_case_gives_the_same_note(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    _directors(published_data_root, case_id)
    first = _pd(client, analyst, published_data_root, case_id)
    again = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)


# --- Observations: material facts the memo states that need the promoter's answer ---

CO = "Kestrel Tools Private Limited"
TIDEWATER = {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12_000_000,
             "outstanding": 7_500_000, "emi": 250_000}


def _observed(note: dict) -> dict[str, dict]:
    """The note's observations by their key."""
    return {q["ref"]: q for q in note["questions"] if q["source"] == "observation"}


def _memo(client: TestClient, headers: dict, case_id: str, section_id: str) -> list[str]:
    cam = client.get(f"/api/cases/{case_id}/cam", headers=headers).json()
    section = next(s for s in cam["sections"] if s["id"] == section_id)
    return [b["paragraph"]["text"] for b in section["blocks"] if b["kind"] == "paragraph"]


def _asked_as_observation(q: dict, *, area: str, section: int, severity: str = "moderate") -> None:
    assert (q["source"], q["rule"], q["target"], q["area"], q["severity"]) == ("observation", "OBS", "cam", area, severity)
    # Its status names the memo section that states it; the question asks, the context is the memo's sentence.
    assert q["status"] == f"section {section}" and q["xv_ref"] is None and q["also"] == []
    assert q["question"].endswith("?") and q["text"] == f"{q['context']} {q['question']}" and q["title"]


def test_only_what_the_data_shows_is_observed(client: TestClient, published_data_root: Path):
    """Revenue up, no bureau or declaration to hold borrowings against, no year-end balances, no loan
    paid in, no facility only the message names: of the observations, only the collateral offered at
    intake with nothing on file about it."""
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    assert set(_observed(_pd(client, analyst, published_data_root, case_id))) == {"proposal:collateral"}
    assert not any(p.startswith("Net worth fell") for p in _memo(client, analyst, case_id, "financials"))


def test_a_fall_in_revenue_and_net_worth_is_asked_in_the_memos_words(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=30_000_000)
    statements = audited(root, case_id, scale=0.42)  # the comparatives print the earlier, larger year
    note = _pd(client, analyst, root, case_id)
    revenue = ("Revenue from operations fell 50.6% to INR 4.96 cr in FY 2025-26, from INR 10.03 cr in FY 2024-25 "
               "(the comparatives in the FY 2025-26 statements).")
    worth = ("Net worth fell from INR 3.57 cr to INR 1.76 cr despite a profit of INR 26.88 lakh; share capital fell from "
             "INR 85.00 lakh to INR 42.00 lakh and reserves and surplus from INR 2.72 cr to INR 1.34 cr.")
    assert _memo(client, analyst, case_id, "financials")[:2] == [revenue, worth]
    q = _observed(note)["financials:fall"]
    # Half the revenue gone is serious, and asked first in its topic.
    _asked_as_observation(q, area="turnover", section=5, severity="serious")
    assert q["title"] == "Revenue and net worth fell" and q["context"] == f"{revenue} {worth}"
    assert q["question"] == ("Why did revenue and net worth fall, what turnover is expected for the current year, and why "
                             "did the share capital and reserves fall (a capital reduction, a buy-back or a write-off)?")
    assert {e["document_id"] for e in q["evidence"]} == {statements}
    turnover = next(t for t in note["topics"] if t["area"] == "turnover")
    assert turnover["question_ids"][0] == q["id"]


def test_a_smaller_fall_in_revenue_alone_is_moderate(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=30_000_000)
    audited(root, case_id, set_rows={"I. Revenue from operations": 60_000_000})  # 40.2% down; net worth up
    q = _observed(_pd(client, analyst, root, case_id))["financials:fall"]
    _asked_as_observation(q, area="turnover", section=5)
    assert q["title"] == "Revenue fell" and q["context"].startswith("Revenue from operations fell 40.2% to INR 6.00 cr")
    assert q["question"] == "Why did revenue fall, and what turnover is expected for the current year?"
    assert not any(p.startswith("Net worth fell") for p in _memo(client, analyst, case_id, "financials"))


def _borrowings(client: TestClient, analyst: dict, root: Path, *, outstanding: int = 7_500_000, **case) -> tuple[str, str]:
    """Statements with borrowings of 2.70 cr; a declaration and the bureau with one facility."""
    case_id = make_case(client, analyst, root, **case)
    audited(root, case_id)
    tidewater = {**TIDEWATER, "outstanding": outstanding}
    add_doc(root, case_id, "existing_facilities_declaration", {"company_name": CO, "declaration_date": "2026-09-15",
                                                               "facilities": [tidewater]})
    bureau = add_doc(root, case_id, "commercial_bureau_report", {
        "company_name": CO, "report_date": "2026-09-20", "credit_rank": "3",
        "credit_facilities": [{**tidewater, "overdue": 0, "status": "Standard"}]})
    return case_id, bureau


def test_borrowings_no_facility_on_file_explains_are_asked(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, bureau = _borrowings(client, analyst, root)
    q = _observed(_pd(client, analyst, root, case_id))["obligations:borrowings"]
    memo = _memo(client, analyst, case_id, "obligations")
    assert any(p.endswith("Borrowings of INR 2.70 cr against INR 75.00 lakh outstanding on the facilities on file; "
                          "INR 1.95 cr is not explained.") for p in memo)
    # One lender: said in the singular.
    assert ("Existing sanctioned facilities with Tidewater Finance Limited total INR 1.20 cr; the commercial bureau "
            "report shows INR 75.00 lakh outstanding." in memo)
    _asked_as_observation(q, area="obligations", section=9)
    assert q["context"] == ("The FY 2025-26 balance sheet shows borrowings of INR 2.70 cr against INR 75.00 lakh "
                            "outstanding on the facilities on file; INR 1.95 cr is not explained.")
    assert q["question"].startswith("Who are the lenders for the INR 1.95 cr of borrowings")
    assert bureau in {e["document_id"] for e in q["evidence"]}


def test_borrowings_are_not_asked_about_when_the_facilities_on_file_explain_them_or_cannot(client, published_data_root):
    """Outstanding within INR 25 lakh of the borrowings; a facility named only in the sourcing message,
    whose outstanding nobody states; no declaration or bureau report to say what is outstanding."""
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    near, _ = _borrowings(client, analyst, root, outstanding=26_000_000, borrower="Kestrel Tools Pvt Ltd")
    banking = "cash credit with Lotuscrest Bank a/c 90100005678"
    unknown, _ = _borrowings(client, analyst, root, borrower="Heronbay Moulds Pvt Ltd",
                             header={"existing_banking": {"value": banking, "source": "person"}})
    bare = make_case(client, analyst, root, borrower="Marigold Presses Pvt Ltd")
    audited(root, bare)
    add_doc(root, bare, "sanction_letter", {"lender_name": "Tidewater Finance Limited", "facilities": [
        {"facility": "Term loan", "sanctioned_amount": 12_000_000, "emi": 250_000}]})
    for case_id in (near, unknown, bare):
        assert "obligations:borrowings" not in _observed(_pd(client, analyst, root, case_id))
        assert not any("is not explained" in p for p in _memo(client, analyst, case_id, "obligations"))


def test_a_loan_no_facility_matches_and_a_facility_without_a_limit_are_asked(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    banking = ("current account with Lotuscrest Bank a/c 90100001234 and cash credit with Lotuscrest Bank a/c "
               "90100005678")
    case_id = make_case(client, analyst, root, header={"existing_banking": {"value": banking, "source": "person"}})
    ashwood = {"lender": "Ashwood Finserv Limited", "facility": "Term loan", "sanctioned_amount": 9_500_000,
               "emi": 145_000, "outstanding": 6_000_000}
    add_doc(root, case_id, "existing_facilities_declaration", {"company_name": CO, "facilities": [ashwood]})
    add_doc(root, case_id, "commercial_bureau_report", {"company_name": CO, "credit_facilities": [ashwood]})
    statement = bank(root, case_id, [{"date": "2025-06-20", "description": "TL DISBURSAL LN 778812", "credit": 5_000_000}]
                     + [{"date": f"{ym}-05", "description": "NACH DR ASHWOOD FINSERV", "debit": 145_000}
                        for ym in months((2025, 4), 12)])
    observed = _observed(_pd(client, analyst, root, case_id))
    memo = _memo(client, analyst, case_id, "obligations")
    loan = observed["obligations:disbursal-2025-06-20-5000000"]
    _asked_as_observation(loan, area="obligations", section=9)
    assert loan["context"] == ("A loan of INR 50.00 lakh was disbursed into Lotuscrest Bank ·1234 on 20 Jun 2025 "
                               "(TL DISBURSAL LN 778812); no facility on file matches it and no instalment for it "
                               "appears in the statements.") and loan["context"] in memo
    assert loan["question"] == ("Which lender disbursed this loan, on what terms, and why is no instalment for it seen "
                                "in the statements?")
    assert [e["document_id"] for e in loan["evidence"]] == [statement]
    facility = observed["obligations:facility-lotuscrest-bank-cash-credit"]
    _asked_as_observation(facility, area="obligations", section=9)
    assert facility["context"] in memo and facility["context"].endswith("its limit is not on file.")
    assert facility["question"] == ("What are the limit and the outstanding of the cash credit with Lotuscrest Bank, and "
                                    "can the lender's sanction letter be provided?")


def test_a_loan_a_facility_on_file_accounts_for_and_a_facility_with_its_limit_are_not_asked(client, published_data_root):
    """A loan whose narration names a lender on file, one of the amount of a facility on file, and a
    facility the sourcing message names whose sanction letter states its limit."""
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    banking = "cash credit with Lotuscrest Bank a/c 90100005678"
    case_id = make_case(client, analyst, root, header={"existing_banking": {"value": banking, "source": "person"}})
    for lender, amount in (("Tidewater Finance Limited", 12_000_000), ("Ironleaf Capital Limited", 5_000_000),
                           ("Lotuscrest Bank", 20_000_000)):
        add_doc(root, case_id, "sanction_letter", {"lender_name": lender, "facilities": [
            {"facility": "Cash credit" if lender == "Lotuscrest Bank" else "Term loan", "sanctioned_amount": amount}]})
    bank(root, case_id, [{"date": "2025-06-20", "description": "TL DISBURSAL LN 778812", "credit": 5_000_000},
                         {"date": "2025-07-10", "description": "LOAN DISB TIDEWATER", "credit": 3_000_000}])
    observed = _observed(_pd(client, analyst, root, case_id))
    assert not [k for k in observed if k.startswith(("obligations:disbursal", "obligations:facility"))]
    memo = _memo(client, analyst, case_id, "obligations")
    assert any(p.endswith("(TL DISBURSAL LN 778812); a facility of that amount with Ironleaf Capital Limited is on file.")
               for p in memo)
    assert any(p.endswith("the narration names Tidewater Finance Limited, a lender on file.") for p in memo)


@pytest.mark.parametrize("balances,ending,question", [
    # The statements hold more than the balance sheet says: asked why.
    ([9_000_000, 1_100_000], "; the statements' balances exceed the audited figure by INR 41.00 lakh.",
     "Why do the year-end statement balances exceed the audited cash and bank balance by INR 41.00 lakh"),
    # Part of the audited balance is in no statement: asked where it is held.
    ([3_000_000], "; INR 30.00 lakh of the audited balance is not in any statement on file.",
     "Where is the INR 30.00 lakh of the audited cash and bank balance that is in no statement on file held"),
    # Stated, but too small to ask about.
    ([5_800_000], "; INR 2.00 lakh of the audited balance is not in any statement on file.", None),
])
def test_year_end_balances_apart_from_the_audited_figure_are_asked_either_way(client, published_data_root, balances,
                                                                              ending, question):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root)
    audited(root, case_id)  # cash and bank balances of 60 lakh
    for (last4, name), balance in zip((("1234", "Lotuscrest Bank"), ("7777", "Ironleaf Bank")), balances):
        bank(root, case_id, [{"date": "2026-03-20", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 50_000,
                              "balance": balance}], last4=last4, bank_name=name)
    stated = next(p for p in _memo(client, analyst, case_id, "banking") if p.startswith("At 31 Mar 2026"))
    assert stated.endswith(ending)
    q = _observed(_pd(client, analyst, root, case_id)).get("banking:cash")
    if question is None:
        assert q is None
        return
    _asked_as_observation(q, area="accounts", section=8)
    assert q["context"] == stated and q["question"].startswith(question)


@pytest.mark.parametrize("offered", [True, False])
def test_collateral_offered_with_nothing_on_file_is_asked(client: TestClient, published_data_root: Path, offered):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, collateral_present=offered)
    q = _observed(_pd(client, analyst, published_data_root, case_id)).get("proposal:collateral")
    if not offered:
        assert q is None
        return
    _asked_as_observation(q, area="policy", section=4)
    assert q["context"] == "Collateral is offered, as recorded on the case at intake; its nature and value are not on file."
    assert q["question"].startswith("What collateral is offered (the asset, its owner and its value)")
    assert q["evidence"] == []


def test_a_return_not_yet_due_is_asked_only_when_nothing_else_asks_for_it(client: TestClient, published_data_root: Path):
    """The FY 2025-26 return falls due on 31 Oct 2026. The checklist asks for it, and the documents to
    collect with it; with the checklist item waived, the note asks when it will be filed."""
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=30_000_000)
    audited(root, case_id)
    note = _pd(client, analyst, root, case_id)
    assert not [k for k in _observed(note) if k.startswith("turnover:return")]
    assert any("AY 2026-27" in d["text"] for d in note["documents_to_collect"])
    filing = next(p for p in _memo(client, analyst, case_id, "turnover") if p.startswith(("GST returns", "No GST")))
    assert filing.endswith("The return for AY 2026-27 is due by 31 Oct 2026 (not yet due); the checklist asks for it.")
    conn = db.connect(root)
    try:
        conn.execute("""INSERT INTO checklist_waivers (case_id, item_id, reason, decided_by, decided_at)
                        VALUES (?, 'itr', 'Returns to follow after the due date', 'test', '2026-09-29T00:00:00Z')""",
                     (case_id,))
    finally:
        conn.close()
    q = _observed(_pd(client, analyst, root, case_id))["turnover:return-ay-2026-27"]
    _asked_as_observation(q, area="turnover", section=7, severity="mild")
    assert q["context"] == "The return for AY 2026-27 is due by 31 Oct 2026 (not yet due)."
    assert q["question"] == "When will the income tax return for AY 2026-27 be filed?"
    filing = next(p for p in _memo(client, analyst, case_id, "turnover") if p.startswith(("GST returns", "No GST")))
    assert filing.endswith("The return for AY 2026-27 is due by 31 Oct 2026 (not yet due).")


def test_an_observation_is_asked_after_the_findings_and_deviations_of_its_severity(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    policy = [q for q in _pd(client, analyst, published_data_root, case_id)["questions"] if q["area"] == "policy"]
    collateral = next(i for i, q in enumerate(policy) if q["ref"] == "proposal:collateral")
    assert any(q["source"] == "deviation" for q in policy[:collateral])
    assert all(q["source"] == "deviation" for q in policy[:collateral])
    assert all(q["severity"] == "mild" for q in policy[collateral + 1:])


# --- What a question's wording may name ---


def test_a_findings_question_may_name_its_values_rows_and_figures():
    from engine.contracts import Finding, FindingDetail, FindingDetailRow, FindingSide
    from engine.pd_note import finding_values

    pans = Finding(id="F1", case_id="C", rule_id="ID-01", title="t", outcome="fail", severity="serious", blocking=True,
                   explanation="e", sides=[FindingSide(label="Company PAN", value="AAACK1234F"),
                                           FindingSide(label="Income tax return", value="AAACK9876Q")])
    values = finding_values(pans)
    assert (values["values"], values["left"], values["right"], values["items"], values["s"]) == (
        "AAACK1234F and AAACK9876Q", "AAACK1234F", "AAACK9876Q", "", "s")
    rows = [FindingDetailRow(label="ASHWOOD FINSERV", cells=["Lotuscrest Bank ·1234", 145_000.0, 12.0, "✓"]),
            FindingDetailRow(label="TIDEWATER FIN", cells=["Lotuscrest Bank ·1234", 250_000.0, 12.0, "—"], flagged=True)]
    lenders = Finding(id="F2", case_id="C", rule_id="OB-02", title="t", outcome="fail", severity="serious",
                      blocking=False, explanation="e", sides=[], scope="FY 2025-26",
                      detail=FindingDetail(columns=["Account", "Monthly instalment", "Months", "Declared"], rows=rows))
    values = finding_values(lenders)
    # One lender flagged: "lender", not "lenders"; its figures as the detail gives them, months as a count.
    assert (values["items"], values["lenders"], values["count"], values["s"], values["period"]) == (
        "TIDEWATER FIN", "TIDEWATER FIN", "1", "", "FY 2025-26")
    assert values["detail"] == "TIDEWATER FIN (account Lotuscrest Bank ·1234, monthly instalment INR 2.50 lakh, months 12)"
    assert values["anything else"] == ""


def test_a_norms_question_may_name_its_figures_and_the_shortfall(published_data_root: Path):
    from engine.contracts import NormInput, NormResult
    from engine.pd_note import norm_values

    policy = reader.load_policy(published_data_root)
    configured = {n.id: n for n in policy.norms}
    years = NormResult(id="DOC-02", family="documentation", label="Years of audited financial statements", formula="",
                       required="at least 2 years", unit="years", outcome="deviation", category="documentation",
                       category_label="Documentation", actual=1, actual_text="1 year")
    values = norm_values(years, configured["DOC-02"], policy, "FY 2025-26", set())
    assert (values["shortfall"], values["s"]) == ("1 year", "")
    assert values["statement"] == "Audited financial statements cover 1 year against a norm of at least 2 years."
    inputs = [NormInput(name="amount_requested", label="Amount requested", value=30_000_000),
              NormInput(name="revenue_from_operations", label="Revenue from operations", value=49_560_000)]
    request = NormResult(id="EL-05", family="eligibility", label="Total request against turnover", formula="",
                         required="at most 20%", unit="%", outcome="deviation", category="eligibility",
                         category_label="Eligibility", actual=60.5, actual_text="60.5%", inputs=inputs)
    values = norm_values(request, configured["EL-05"], policy, "FY 2025-26", set())
    assert (values["amount_requested"], values["revenue_from_operations"]) == ("INR 3.00 cr", "INR 4.96 cr")
    assert values["figures"] == "amount requested INR 3.00 cr and revenue from operations INR 4.96 cr"
