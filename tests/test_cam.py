"""The draft CAM (FRD F-23; test plan TC-26): the assumed layout section by section, every figure
cited, the summary of findings, checks not completed, deviations and open queries, the empty
recommendation with its prompts and sign-off, and the documents cited numbered by first citation.
Every name is fictional."""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from engine import cam as cam_module, db, pipeline
from engine.configstore import reader
from engine.configstore.schema import CamSectionConfig
from engine.contracts import CaseFacts, Evidence, IdentityFacts, PersonEntry, PersonSet
from tests.conftest import ANALYST, RM, case_files, make_case, run_jobs, sign_in, upload
from tests.test_pd_note import _case
from tests.triangulation import add_doc, audited, bank, gstr, months

CO = "Kestrel Tools Private Limited"
CIN = "U28990MH2015PTC123456"
SECTIONS = ["snapshot", "borrower", "promoters", "proposal", "financials", "working_capital", "turnover", "banking",
            "obligations", "verification", "policy", "documentation"]
FY26 = months((2025, 4), 12)
MONTH_NAMES = ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January",
               "February", "March"]
PERIODS = [f"{m} {2025 if i < 9 else 2026}" for i, m in enumerate(MONTH_NAMES)]  # FY 2025-26
TIDEWATER = {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12_000_000,
             "outstanding": 7_500_000, "emi": 250_000}
LOTUSCREST = {"lender": "Lotuscrest Bank", "facility": "Cash credit", "sanctioned_amount": 20_000_000,
              "outstanding": 18_500_000}
BANKING = "Current account with Lotuscrest Bank a/c 90100001234 and cash credit a/c 90100005678"
MESSAGE = (f"Kestrel Tools Pvt Ltd needs CC and TL of 6.5 cr. Turnover 12 cr. Promoters Tarun Velankar, Ishita Barve "
           f"and Sunil Karve. {BANKING}.")
VERSION_LABEL = re.compile(r"Version \d+ \(published \d{1,2} [A-Z][a-z]{2} \d{4}\)")


def _span(text: str) -> str:
    start = MESSAGE.index(text)
    return f"message:{start}-{start + len(text)}"


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _get(client: TestClient, headers: dict, case_id: str, path: str):
    response = client.get(f"/api/cases/{case_id}/{path}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _cam(client: TestClient, headers: dict, root: Path, case_id: str) -> dict:
    _refresh(root, case_id)
    return _get(client, headers, case_id, "cam")


def _section(cam: dict, section_id: str) -> dict:
    return next(s for s in cam["sections"] if s["id"] == section_id)


def _blocks(section: dict, kind: str) -> list[dict]:
    return [b for b in section["blocks"] if b["kind"] == kind]


def _paragraphs(section: dict) -> list[str]:
    return [b["paragraph"]["text"] for b in _blocks(section, "paragraph")]


def _facts(block: dict) -> dict[str, dict]:
    return {f["label"]: f["value"] for f in block["facts"]}


def _table(section: dict, title: str | None = None) -> dict:
    return next(b["table"] for b in _blocks(section, "table") if title is None or b["table"]["title"] == title)


def _rows(table: dict) -> list[list[str]]:
    return [[c["text"] for c in row] for row in table["rows"]]


def _cited(text: dict) -> set[str]:
    return {e["document_id"] for e in text["citations"]}


def _texts(cam: dict) -> list[str]:
    """Every statement of the memo: paragraphs, facts, table cells, notes and the summary."""
    out = []
    for s in cam["sections"]:
        for b in s["blocks"]:
            out += [b["paragraph"]["text"]] if b["paragraph"] else []
            out += [f["value"]["text"] for f in b["facts"]]
            out += [c["text"] for row in (b["table"]["rows"] if b["table"] else []) for c in row]
            out += [b["text"]] if b["text"] else []
    return out + [i["text"] for i in cam["summary"]]


def _full_case(client: TestClient, analyst: dict, root: Path) -> tuple[str, dict[str, str]]:
    """Something in every section: the sourcing message; the certificate, the memorandum (three
    directors), the company PAN and two KYCs (none for Sunil Karve, and Ishita Barve's DIN differs
    from the memorandum's); two years of statements; eight months of GST returns; an income tax
    return with a second PAN (ID-01 fails, serious and blocking); a bank statement with a loan
    disbursal and instalments to a lender nobody declared, an account declared without a statement; a
    declaration, a sanction letter and the bureau report. Returns the case and its documents by name."""
    header = {"borrower": {"value": "Kestrel Tools Pvt Ltd", "source": _span("Kestrel Tools Pvt Ltd")},
              "amount_inr": {"value": "65000000", "source": _span("6.5 cr")},
              "declared_turnover_inr": {"value": "120000000", "source": _span("Turnover 12 cr")},
              "promoters": {"value": "Tarun Velankar; Ishita Barve; Sunil Karve",
                            "source": _span("Tarun Velankar, Ishita Barve and Sunil Karve")},
              "existing_banking": {"value": BANKING, "source": _span(BANKING)}}
    case_id = make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd", message_text=MESSAGE, header=header)
    docs = {
        "certificate": add_doc(root, case_id, "certificate_of_incorporation", {
            "company_name": CO, "cin": CIN, "date_of_incorporation": "2015-06-12",
            "company_type": "Company limited by shares", "registered_address": "Plot 7, Industrial Estate, Pune 411019"}),
        "memorandum": add_doc(root, case_id, "memorandum_articles_of_association", {"company_name": CO, "cin": CIN, "directors": [
            {"name": "Tarun Velankar", "din": "01234567"}, {"name": "Ishita Barve", "din": "07654321"},
            {"name": "Sunil Karve", "din": "09123456"}]}),
        "kyc_tarun": add_doc(root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567",
                                                             "pan": "ABCPV1234K", "designation": "Director"}),
        "kyc_ishita": add_doc(root, case_id, "director_kyc", {"person_name": "Ishita Barve", "din": "07654322",
                                                              "pan": "ABCPB5678M", "designation": "Director"}),
        "resolution": add_doc(root, case_id, "board_resolution_borrowing",
                              {"company_name": CO, "purpose_of_borrowing": "Working capital and term loan"}),
        "pan": add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F", "company_name": CO}),
        "itr": add_doc(root, case_id, "income_tax_return", {
            "pan": "AAACK9876Q", "taxpayer_name": CO, "assessment_year": "2025-26",
            "income_computation": [{"particulars": "Turnover", "amount": 94_400_000}]}),
        "fy26": audited(root, case_id, "2026-03-31"),
        "fy25": audited(root, case_id, "2025-03-31", scale=0.8),
        "gst": [gstr(root, case_id, period, 12_000_000) for period in PERIODS[:8]][0],
        "bank": bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 9_000_000}
                                     for ym in FY26]
                     + [{"date": "2025-06-20", "description": "LOAN DISB TIDEWATER", "credit": 5_000_000}]
                     + [{"date": f"{ym}-05", "description": "NACH DR TIDEWATER FIN", "debit": 250_000} for ym in FY26]),
        "declaration": add_doc(root, case_id, "existing_facilities_declaration", {
            "company_name": CO, "declaration_date": "2026-09-15", "facilities": [LOTUSCREST],
            "bank_accounts": [{"bank": "Lotuscrest Bank", "account_number": "90100001234", "account_type": "Current account"}]}),
        "sanction": add_doc(root, case_id, "sanction_letter", {
            "lender_name": "Tidewater Finance Limited", "borrower_name": CO, "sanction_date": "2024-04-12",
            "facilities": [{"facility": "Term loan", "sanctioned_amount": 12_000_000, "emi": 250_000}]}),
        "bureau": add_doc(root, case_id, "commercial_bureau_report", {
            "company_name": CO, "pan": "AAACK1234F", "report_date": "2026-09-20", "credit_rank": "4",
            "credit_facilities": [{**f, "overdue": 0, "status": "Standard"} for f in (TIDEWATER, LOTUSCREST)],
            "related_parties": [{"name": n, "relationship": "Director", "pan": p} for n, p in (
                ("Tarun Velankar", "ABCPV1234K"), ("Ishita Barve", "ABCPB5678M"), ("Sunil Karve", "ABCPK9012L"))]}),
    }
    documents = _get(client, analyst, case_id, "documents")
    docs["message"] = next(d["id"] for d in documents if d["classification"]["types"] == ["application_message"])
    return case_id, docs


def _decide(client: TestClient, headers: dict, case_id: str, rule_id: str, decision: str) -> dict:
    board = _get(client, headers, case_id, "cross-verification")
    item = next(i for i in board["items"] if i["finding"]["rule_id"] == rule_id and i["finding"]["outcome"] == "fail")
    response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{item['finding']['id']}/decision",
                           json={"decision": decision, "comment": f"Reviewed: {decision}"}, headers=headers)
    assert response.status_code == 200, response.text
    return item["finding"]


def _summary_finding(cam: dict, rule_id: str) -> dict:
    return next(i for i in cam["summary"] if i["kind"] == "finding" and i["rule"] == rule_id)


# --- The layout ---


def test_tc26_sections_follow_the_assumed_layout_numbered_then_the_summary_and_the_recommendation(
        client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id, _ = _full_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    assert [s["id"] for s in cam["sections"]] == SECTIONS
    assert [s["number"] for s in cam["sections"]] == list(range(1, len(SECTIONS) + 1))
    assert [s["title"] for s in cam["sections"]][:3] == ["Proposal at a glance", "Borrower profile", "Promoters and management"]
    assert _section(cam, "turnover")["title"] == "Turnover across sources (GST, income tax and banking)"
    assert (cam["summary_number"], cam["recommendation_number"]) == (13, 14)
    assert cam["summary_title"] == "Summary of findings, deviations and open queries"
    assert cam["title"] == "Credit Approval Memo" and cam["borrower"] == "Kestrel Tools Pvt Ltd"
    assert cam["interim_template"] is True and cam["template_note"].startswith("Draft — layout assumed")
    assert cam["as_of"] == "2026-09-29" and cam["config_version"] == reader.published_version(published_data_root)["version"]
    assert cam["run_id"] == _get(client, analyst, case_id, "cross-verification")["run"]["id"]
    # Every section has something on file for this case.
    assert all(s["blocks"] and s["empty"] is None for s in cam["sections"])


def test_the_configuration_is_named_as_administration_numbers_it(client: TestClient, published_data_root: Path):
    """"Version N (published D Mon YYYY)", counted from the publish log; the hash where the log has no record."""
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    history = reader.publish_history(published_data_root)
    assert VERSION_LABEL.fullmatch(cam["config_label"]) and cam["config_label"].startswith(f"Version {len(history)} ")
    (published_data_root / "config_store" / "publish_log.jsonl").unlink()
    assert cam_module.config_label(published_data_root) == cam["config_version"][:8]


def test_the_downloads_wording_comes_from_configuration(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    cam = _cam(client, analyst, published_data_root, _case(client, analyst, published_data_root))
    assert cam["labels"] == reader.load_cam(published_data_root).labels


def test_tc26_the_recommendation_is_left_empty_with_its_prompts_and_the_sign_off(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    cam = _cam(client, analyst, published_data_root, _case(client, analyst, published_data_root))
    assert cam["recommendation_title"] == "Recommendation" and cam["recommendation"] == ""
    assert cam["recommendation_prompts"] == ["Recommendation", "Terms and conditions",
                                             "Deviations recommended for approval", "Decision of the approving authority"]
    assert [s["role"] for s in cam["sign_off"]] == ["Prepared by", "Recommended by", "Approved by"]


def test_an_empty_case_still_drafts(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    assert [s["id"] for s in cam["sections"]] == SECTIONS
    assert _section(cam, "financials")["empty"] == "Nothing on file yet." and not _section(cam, "financials")["blocks"]
    assert _facts(_blocks(_section(cam, "snapshot"), "facts")[0])["PAN"]["text"] == "Not on file"
    assert cam["sources"] == []


def test_the_cam_needs_the_outputs_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/cam", headers=rm).status_code == 403


def test_the_same_case_gives_the_same_memo(client: TestClient, published_data_root: Path):
    """No clock in the memo: the same data and the same run of the checks give the same memo."""
    analyst = sign_in(client, ANALYST)
    case_id, _ = _full_case(client, analyst, published_data_root)
    first = _cam(client, analyst, published_data_root, case_id)
    assert json.dumps(first, sort_keys=True) == json.dumps(_get(client, analyst, case_id, "cam"), sort_keys=True)


def test_a_version_published_before_the_assumed_layout_drafts_with_its_own_sections(client, published_data_root):
    """The title, template note, prompts, sign-off, labels and PD note wording are new to the section:
    a version published before them reads them as their defaults."""
    root = published_data_root
    version = reader.published_version(root)["version"]
    path = root / "config_store" / "versions" / version / "cam.json"
    path.write_text(json.dumps({
        "interim_template": True, "summary_title": "Summary", "recommendation_title": "Recommendation",
        "sections": [{"id": "borrower", "kind": "borrower_profile", "title": "Borrower profile"},
                     {"id": "policy", "kind": "policy", "title": "Compliance with policy norms"}]}), encoding="utf-8")
    reader._load_section_json.cache_clear()
    try:
        analyst = sign_in(client, ANALYST)
        cam = _cam(client, analyst, root, _case(client, analyst, root))
        assert [(s["id"], s["number"]) for s in cam["sections"]] == [("borrower", 1), ("policy", 2)]
        assert (cam["title"], cam["template_note"], cam["recommendation_prompts"], cam["sign_off"], cam["labels"]) == (
            "Credit Approval Memo", None, [], [], {})
        assert (cam["summary_number"], cam["recommendation_number"]) == (3, 4)
        assert reader.load_cam(root).pd_note.topics["identity"] == "Identity and KYC"
    finally:
        reader._load_section_json.cache_clear()


def test_the_configured_section_reads_the_new_fields_as_optional():
    old = CamSectionConfig.model_validate({"interim_template": True, "sections": [], "summary_title": "S",
                                           "recommendation_title": "R"})
    assert (old.title, old.template_note, old.recommendation_prompts, old.sign_off) == ("Credit Approval Memo", None, [], [])
    assert old.pd_note.title == "Personal discussion — question note" and old.pd_note.record_fields == []
    assert list(old.pd_note.topics) == ["identity", "turnover", "accounts", "obligations", "policy"]
    assert getattr(old, "labels", {}) == {} and getattr(old.pd_note, "labels", {}) == {}
    assert getattr(old.pd_note, "sign_off", ["Discussion held by"]) == ["Discussion held by"]


# --- Section by section ---


def test_the_snapshot_states_the_proposal_at_a_glance(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    [block] = _section(cam, "snapshot")["blocks"]
    facts = _facts(block)
    assert list(facts) == ["Borrower", "Constitution", "PAN", "GSTIN", "CIN", "Incorporated", "Facilities proposed",
                           "Amount requested", "Board resolution limit", "Collateral offered",
                           "Turnover declared in the sourcing message", "Relationship manager and branch",
                           "Approving authority", "Cross-checks", "Policy norms", "Documentation", "Case ID"]
    assert facts["Borrower"]["text"] == "Kestrel Tools Pvt Ltd" and _cited(facts["Borrower"]) == {docs["message"]}
    assert facts["Constitution"]["text"] == "Private limited"
    assert facts["PAN"]["text"] == "AAACK1234F" and _cited(facts["PAN"]) == {docs["pan"]}
    assert facts["GSTIN"]["text"] == "27AAACK1234F1Z0"
    assert facts["CIN"]["text"] == CIN and _cited(facts["CIN"]) == {docs["certificate"]}
    # Completed years and months at the case's as-of date (29 Sep 2026).
    assert facts["Incorporated"]["text"] == "12 Jun 2015 (11 years 3 months)"
    assert _cited(facts["Incorporated"]) == {docs["certificate"]}
    assert facts["Facilities proposed"]["text"] == "Cash credit and term loan"
    assert facts["Amount requested"]["text"] == "INR 6.50 cr" and _cited(facts["Amount requested"]) == {docs["message"]}
    # The resolution on file states no limit.
    assert facts["Board resolution limit"]["text"] == "Not stated in the resolution"
    # Collateral is a flag set on the case at intake; no document backs it.
    assert facts["Collateral offered"]["text"] == "Offered (case record; details not on file)"
    assert not facts["Collateral offered"]["citations"]
    assert facts["Turnover declared in the sourcing message"]["text"] == "INR 12.00 cr"
    assert facts["Relationship manager and branch"]["text"] == "Ananya Krishnan, Mumbai hub"
    authority = _get(client, analyst, case_id, "approving-authority")
    assert facts["Approving authority"]["text"] == f"At least {authority['required']['label']} (provisional matrix)"
    board = _get(client, analyst, case_id, "cross-verification")
    counts = board["counts"]
    incomplete = sum(a["incomplete"] for a in board["areas"])
    assert counts["total"] > 1 and counts["adjudicated"] == 0 and counts["blocking_open"]
    assert facts["Cross-checks"]["text"] == (
        f"{board['run']['rules']} run; {counts['total']} discrepancies (all open, {counts['blocking_open']} blocking "
        f"submission)" + (f"; {incomplete} could not be completed" if incomplete else ""))
    policy = _get(client, analyst, case_id, "policy")["counts"]
    assert facts["Policy norms"]["text"] == f"{policy['deviations']} deviations, {policy['cannot_evaluate']} not assessed"
    readiness = _get(client, analyst, case_id, "checklist")
    assert facts["Documentation"]["text"] == (f"{readiness['score_pct']:g}% ready against a gate of {readiness['gate_pct']}%; "
                                              f"{readiness['blocking_open']} blocking items open")
    assert facts["Case ID"]["text"] == case_id


def test_the_snapshot_says_where_the_checks_stand_accepted_meaning_a_valid_finding(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, _ = _full_case(client, analyst, root)
    _refresh(root, case_id)
    _decide(client, analyst, case_id, "OB-01", "accept")
    _decide(client, analyst, case_id, "TO-03", "dismiss")
    cam = _get(client, analyst, case_id, "cam")
    board = _get(client, analyst, case_id, "cross-verification")
    counts = board["counts"]
    incomplete = sum(a["incomplete"] for a in board["areas"])
    open_ = counts["total"] - counts["adjudicated"]
    facts = _facts(_section(cam, "snapshot")["blocks"][0])
    assert facts["Cross-checks"]["text"] == (
        f"{board['run']['rules']} run; {counts['total']} discrepancies: {open_} open "
        f"({counts['blocking_open']} blocking submission), 1 accepted as valid, 1 found not valid"
        + (f"; {incomplete} could not be completed" if incomplete else ""))


def test_the_borrower_profile_reads_the_certificate_and_points_to_the_identity_discrepancies(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    profile = _section(cam, "borrower")
    [text] = _paragraphs(profile)
    assert text == (f"{CO} is a private limited company (limited by shares) incorporated on 12 Jun 2015, "
                    "11 years 3 months in business.")
    facts = _facts(_blocks(profile, "facts")[0])
    assert {k: v["text"] for k, v in facts.items()} == {
        "Legal name": CO, "CIN": CIN, "Date of incorporation": "12 Jun 2015", "Company type": "Company limited by shares",
        "PAN": "AAACK1234F", "GSTIN": "27AAACK1234F1Z0 (Maharashtra)",
        "Registered office": "Plot 7, Industrial Estate, Pune 411019"}
    assert _cited(facts["Legal name"]) == {docs["certificate"]}
    pan = next(i for i in _get(client, analyst, case_id, "cross-verification")["items"] if i["finding"]["rule_id"] == "ID-01")
    [note] = _blocks(profile, "note")
    assert note["text"] == (f"Identity checks found discrepancies: Entity PAN differs between documents "
                            f"({pan['finding']['ref']}). See section 10.")


def test_the_vintage_sentence_never_rounds_up(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2023-10-17"})
    profile = _section(_cam(client, analyst, published_data_root, case_id), "borrower")
    assert "incorporated on 17 Oct 2023, 2 years 11 months in business." in _paragraphs(profile)[0]


def test_promoters_are_grouped_as_the_cross_checks_group_people_with_each_kyc_gap(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    promoters = _section(_cam(client, analyst, published_data_root, case_id), "promoters")
    table = _table(promoters)
    assert table["columns"] == ["Name", "Role", "DIN", "PAN", "KYC on file", "Named in"]
    named = ("Memorandum and articles of association, Director KYC, Commercial bureau report, Sourcing message")
    assert _rows(table) == [
        ["Tarun Velankar", "Director", "01234567", "ABCPV1234K", "Yes", named],
        ["Ishita Barve", "Director", "07654321 (Memorandum and articles of association); 07654322 (Director KYC)",
         "ABCPB5678M", "Yes", named],
        ["Sunil Karve", "Director", "09123456", "ABCPK9012L", "No",
         "Memorandum and articles of association, Commercial bureau report, Sourcing message"],
    ]
    assert _cited(table["rows"][0][4]) == {docs["kyc_tarun"]}
    gaps = _blocks(promoters, "paragraph")
    assert [b["paragraph"]["text"] for b in gaps] == ["No KYC has been received for Sunil Karve."]
    assert _cited(gaps[0]["paragraph"]) == {docs["memorandum"], docs["bureau"], docs["message"]}
    [note] = _blocks(promoters, "note")
    assert "Promoter missing from a source (XV-" in note["text"] and "Director identifiers disagree (XV-" in note["text"]


def _named(source: str, *names: str, one_document: bool = True, typed: bool = False) -> PersonSet:
    """A source naming people: from one document, or (a KYC each) one document per person; typed on the
    case, with no page."""
    return PersonSet(source=source, label=source, names=list(names), entries=[
        PersonEntry(name=n, evidence=[] if typed else [
            Evidence(document_id=f"DOC-{source}" if one_document else f"DOC-{source}-{n}", page=1)]) for n in names])


def _facts_of(*persons: PersonSet) -> CaseFacts:
    return CaseFacts(case_id="BBG-2026-000001", identities=IdentityFacts(), turnover=[], credits=[], obligations=[],
                     accounts=[], facilities=[], declaration_received=False, persons=list(persons))


def test_a_name_given_with_an_initial_is_the_same_person(published_data_root: Path):
    people = cam_module.people(published_data_root, _facts_of(
        _named("board_resolution_borrowing", "T. Velankar"),
        _named("memorandum_articles_of_association", "Tarun Velankar", "Sunil Karve")))
    # The memorandum is read first; "T. Velankar" is Tarun Velankar by the parts of the name.
    assert [(p.name, [s for s, _ in p.entries]) for p in people] == [
        ("Tarun Velankar", ["memorandum_articles_of_association", "board_resolution_borrowing"]),
        ("Sunil Karve", ["memorandum_articles_of_association"])]


def test_two_directors_with_similar_names_in_one_document_are_two_people(published_data_root: Path):
    """"Rajesh Shah" and "Ramesh Shah" are alike enough to be one name (0.91), but one memorandum lists
    them separately: two people, and the KYC received joins the one it names exactly."""
    people = cam_module.people(published_data_root, _facts_of(
        _named("memorandum_articles_of_association", "Rajesh Shah", "Ramesh Shah"),
        _named("director_kyc", "Rajesh Shah", one_document=False),
        _named("application_message", "Rajesh Shah", "Ramesh Shah")))
    assert [(p.name, p.kyc, [s for s, _ in p.entries]) for p in people] == [
        ("Rajesh Shah", True, ["memorandum_articles_of_association", "director_kyc", "application_message"]),
        ("Ramesh Shah", False, ["memorandum_articles_of_association", "application_message"])]


def test_two_similar_names_in_a_list_typed_on_the_case_are_two_people(published_data_root: Path):
    """A list typed on the case has no page to tell its names apart by, and still names two people."""
    people = cam_module.people(published_data_root, _facts_of(
        _named("memorandum_articles_of_association", "Rajesh Shah"),
        _named("director_kyc", "Rajesh Shah", one_document=False),
        _named("application_message", "Rajesh Shah", "Ramesh Shah", typed=True)))
    assert [(p.name, p.kyc, [s for s, _ in p.entries]) for p in people] == [
        ("Rajesh Shah", True, ["memorandum_articles_of_association", "director_kyc", "application_message"]),
        ("Ramesh Shah", False, ["application_message"])]


def test_the_memo_counts_people_as_the_cross_checks_do(client: TestClient, published_data_root: Path):
    """The promoters typed on the case name Ramesh Shah beside Rajesh Shah: the memo lists him with his
    KYC gap, as the promoter check finds him."""
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root,
                        header={"promoters": {"value": "Rajesh Shah; Ramesh Shah", "source": "person"}})
    add_doc(root, case_id, "memorandum_articles_of_association", {"company_name": CO, "directors": [
        {"name": "Rajesh Shah", "din": "01112223"}]})
    add_doc(root, case_id, "director_kyc", {"person_name": "Rajesh Shah", "din": "01112223", "pan": "ABCPS1234K",
                                            "designation": "Director"})
    promoters = _section(_cam(client, analyst, root, case_id), "promoters")
    assert [r[0] for r in _rows(_table(promoters))] == ["Rajesh Shah", "Ramesh Shah"]
    assert "No KYC has been received for Ramesh Shah." in _paragraphs(promoters)
    board = _get(client, analyst, case_id, "cross-verification")
    promoter_set = next(i["finding"] for i in board["items"] if i["finding"]["rule_id"] == "ID-04")
    assert promoter_set["outcome"] == "fail" and "Ramesh Shah has no KYC on file" in promoter_set["explanation"]


def test_a_director_with_a_similar_name_and_no_kyc_keeps_the_gap(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root)
    add_doc(root, case_id, "memorandum_articles_of_association", {"company_name": CO, "directors": [
        {"name": "Rajesh Shah", "din": "01112223"}, {"name": "Ramesh Shah", "din": "04445556"}]})
    kyc = add_doc(root, case_id, "director_kyc", {"person_name": "Rajesh Shah", "din": "01112223", "pan": "ABCPS1234K",
                                                  "designation": "Director"})
    promoters = _section(_cam(client, analyst, root, case_id), "promoters")
    assert [r[:5] for r in _rows(_table(promoters))] == [["Rajesh Shah", "Director", "01112223", "ABCPS1234K", "Yes"],
                                                         ["Ramesh Shah", "Director", "04445556", "—", "No"]]
    assert _cited(_table(promoters)["rows"][0][4]) == {kyc}
    assert "No KYC has been received for Ramesh Shah." in _paragraphs(promoters)
    note = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()
    assert [p["name"] for p in note["people"]] == ["Rajesh Shah", "Ramesh Shah"]


def test_the_proposal_names_each_facility_the_resolution_the_collateral_and_the_amounts_used(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    proposal = _section(_cam(client, analyst, published_data_root, case_id), "proposal")
    assert _rows(_table(proposal)) == [["Cash credit", "Working capital"], ["Term loan", "Term loan"]]
    assert _paragraphs(proposal) == [
        "The proposal is for cash credit and term loan of INR 6.50 cr in total. The sourcing message states annual "
        "turnover of INR 12.00 cr.",
        "The board resolution authorises borrowing for working capital and term loan. The borrowing limit is not on file.",
        # The flag set at intake, outside any cited statement.
        "Collateral: offered, as recorded on the case at intake; nature and value not on file.",
        # The message sets the facilities out; the case records only the total.
        "Amounts per facility are not captured on the case; the sourcing message sets out the facilities asked for. "
        "The working-capital method (section 6), the policy norms and the approving authority (section 11) therefore "
        "use the total of INR 6.50 cr, including the term loan."]
    paragraphs = [b["paragraph"] for b in _blocks(proposal, "paragraph")]
    assert [_cited(p) for p in paragraphs] == [{docs["message"]}, {docs["resolution"]}, set(), {docs["message"]}]
    assert not _blocks(proposal, "note")
    assert not any("not on file; the total is used" in t for t in _texts({"sections": [proposal], "summary": []}))


def test_the_board_resolution_limit_is_set_against_the_amount_requested(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root)
    resolution = add_doc(root, case_id, "board_resolution_borrowing", {
        "company_name": CO, "resolution_date": "2026-09-01", "borrowing_limit": 50_000_000, "lender_name": "RBL Bank",
        "purpose_of_borrowing": "Working capital and term loan",
        "authorized_signatories": ["Tarun Velankar", "Ishita Barve"]})
    cam = _cam(client, analyst, root, case_id)
    stated = next(b["paragraph"] for b in _blocks(_section(cam, "proposal"), "paragraph")
                  if b["paragraph"]["text"].startswith("The board resolution"))
    assert stated["text"] == ("The board resolution of 1 Sep 2026 authorises borrowing from RBL Bank up to INR 5.00 cr "
                              "for working capital and term loan; signatories: Tarun Velankar and Ishita Barve. It covers "
                              "INR 5.00 cr of the INR 6.50 cr requested; a fresh resolution is needed.")
    assert _cited(stated) == {resolution}
    limit = _facts(_section(cam, "snapshot")["blocks"][0])["Board resolution limit"]
    assert limit["text"] == "INR 5.00 cr (below the INR 6.50 cr requested)" and _cited(limit) == {resolution}


def test_financial_performance_tabulates_the_spread_and_sets_each_figure_against_its_norm(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    financials = _section(_cam(client, analyst, published_data_root, case_id), "financials")
    table = _table(financials)
    assert table["columns"] == ["Particulars", "FY 2024-25 (audited)", "FY 2025-26 (audited)"]
    assert table["numeric"] == [1, 2]
    rows = {r[0]: r[1:] for r in _rows(table)}
    assert list(rows) == ["Revenue from operations", "Growth in revenue (%)", "EBITDA", "EBITDA margin (%)",
                          "Profit after tax", "PAT margin (%)", "Net worth", "Total borrowings", "Current ratio",
                          "TOL / TNW", "Debt / equity", "Interest coverage", "Working-capital cycle (days)"]
    assert rows["Revenue from operations"] == ["INR 9.44 cr", "INR 11.80 cr"]
    assert rows["Growth in revenue (%)"] == ["—", "25.0"]
    assert rows["Current ratio"] == ["1.59x", "1.59x"] and rows["Working-capital cycle (days)"] == ["90", "90"]
    for row in table["rows"]:
        for i, cell in enumerate(row[1:]):
            if cell["text"] != "—":
                assert _cited(cell) <= {docs["fy25"], docs["fy26"]} and cell["citations"], row[0]["text"]
    revenue, profit, leverage, liquidity, restated = _paragraphs(financials)
    assert revenue == "Revenue from operations rose 25.0% to INR 11.80 cr in FY 2025-26, from INR 9.44 cr in FY 2024-25."
    assert "Interest coverage was 3.14x, within the norm of at least 2.50x." in profit
    assert "Debt / equity was 0.64x, within the norm of at most 2.00x" in leverage
    # A norm in rupees is named rather than quoted ("positive").
    assert "meeting the norm for profit in the latest year." in profit
    assert "meeting the norm for positive net worth, against total borrowings of" in leverage
    assert "at least INR" not in profit + leverage
    assert liquidity.endswith("The working-capital cycle was 90 days, a deviation from the norm of at most 75 days "
                              "(see section 11).")
    # The FY 2025-26 statements print other figures for FY 2024-25 than its own statements.
    assert restated == ("The FY 2025-26 statements give different figures for FY 2024-25: revenue from operations "
                        "INR 10.03 cr against INR 9.44 cr, profit after tax INR 54.40 lakh against INR 51.20 lakh and "
                        "net worth INR 3.57 cr against INR 3.36 cr in the FY 2024-25 statements.")
    assert _cited(_blocks(financials, "paragraph")[4]["paragraph"]) == {docs["fy26"], docs["fy25"]}
    assert [b["text"] for b in _blocks(financials, "note")] == ["Figures as on the spread (interim layout)."]


def test_without_the_previous_years_statements_their_comparatives_give_the_trend(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)  # the FY 2025-26 statements only
    statements = next(d["id"] for d in _get(client, analyst, case_id, "documents")
                      if d["classification"]["types"] == ["audited_financial_statements"])
    financials = _section(_cam(client, analyst, published_data_root, case_id), "financials")
    table = _table(financials)
    assert table["columns"] == ["Particulars", "FY 2024-25 (comparatives in the FY 2025-26 statements)",
                                "FY 2025-26 (audited)"]
    rows = {r[0]: r[1:] for r in _rows(table)}
    assert rows["Revenue from operations"] == ["INR 10.03 cr", "INR 11.80 cr"]
    assert rows["Profit after tax"] == ["INR 54.40 lakh", "INR 64.00 lakh"] and rows["Growth in revenue (%)"] == ["—", "17.6"]
    assert rows["Current ratio"][0] == "—"
    assert _cited(table["rows"][0][1]) == {statements}
    assert _paragraphs(financials)[0] == ("Revenue from operations rose 17.6% to INR 11.80 cr in FY 2025-26, from "
                                          "INR 10.03 cr in FY 2024-25 (the comparatives in the FY 2025-26 statements).")


def test_statements_in_another_name_are_noted_beside_the_figures_and_the_years_counted(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=40_000_000)
    add_doc(root, case_id, "certificate_of_incorporation", {"company_name": CO, "date_of_incorporation": "2015-06-12"})
    add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F", "company_name": CO})
    audited(root, case_id, "2026-03-31")
    audited(root, case_id, "2025-03-31", scale=0.8, company_name="Kestrel Engineering Works Private Limited")
    cam = _cam(client, analyst, root, case_id)
    name = next(i["finding"] for i in _get(client, analyst, case_id, "cross-verification")["items"]
                if i["finding"]["rule_id"] == "ID-03")
    assert name["outcome"] == "fail"
    caveat = f"The FY 2024-25 statements are in the name of Kestrel Engineering Works Private Limited ({name['ref']})."
    assert caveat in [b["text"] for b in _blocks(_section(cam, "financials"), "note")]
    assert _table(_section(cam, "policy"))["note"] == (
        f"DOC-02 counts the FY 2024-25 statements, which are in the name of Kestrel Engineering Works Private Limited "
        f"({name['ref']}).")


def test_the_working_capital_assessment_and_the_term_loan(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id, _ = _full_case(client, analyst, published_data_root)
    section = _section(_cam(client, analyst, published_data_root, case_id), "working_capital")
    table = _table(section)
    assert table["columns"] == ["Step", "Amount", "Basis"] and table["numeric"] == [1]
    assert all(row[1]["citations"] for row in table["rows"])
    reason, verdict, term = _paragraphs(section)
    assert reason == "The request is above INR 5.00 cr, so the MPBF method (second method) applies."
    assert verdict.startswith("On the figures for FY 2025-26 (audited), eligible bank finance is ")
    assert verdict.endswith("The comparison uses the total request, including the term loan; on a working-capital "
                            "amount of INR 5.00 cr or less the turnover method would apply.")
    # The DSCR gap is stated once.
    assert term == "DSCR could not be assessed: the proposed term loan's instalment is not on file."


def test_turnover_across_sources_by_year_with_partial_months_and_the_filing_position(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    turnover = _section(cam, "turnover")
    table = _table(turnover)
    assert table["columns"] == ["Financial year", "Audited", "GST outward supplies (GSTR-3B)", "Income tax return",
                                "Business credits (bank)", "Declared"]
    assert table["numeric"] == [1, 2, 3, 4, 5]
    assert _rows(table) == [
        ["FY 2025-26", "INR 11.80 cr", "INR 9.60 cr (8 of 12 months)", "—", "INR 10.80 cr", "INR 12.00 cr"],
        ["FY 2024-25", "INR 9.44 cr", "—", "INR 9.44 cr", "—", "—"],
    ]
    assert len(table["rows"][0][2]["citations"]) == 8 and _cited(table["rows"][1][3]) == {docs["itr"]}
    board = _get(client, analyst, case_id, "cross-verification")
    failed = [i["finding"] for i in board["items"] if i["finding"]["outcome"] == "fail"
              and i["finding"]["area"] in ("turnover", "tax")]
    assert {"TO-03", "TO-05"} <= {f["rule_id"] for f in failed}
    listed, filing = _paragraphs(turnover)
    # Each finding is named here and explained once, in section 10.
    titles = "; ".join(f"{f['finding_title']}{' · ' + f['scope'] if f['scope'] else ''} ({f['ref']})" for f in failed)
    assert listed == f"The cross-checks found {len(failed)} discrepancies on turnover and tax, set out in section 10: {titles}."
    assert not any(f["explanation"] in p for f in failed for p in _paragraphs(turnover))
    returns = next(i["finding"] for i in board["items"] if i["finding"]["rule_id"] == "TX-01")
    # The FY 2025-26 return falls due on 31 Oct 2026, after the case's as-of date.
    assert filing == ("GST returns (GSTR-3B) are on file for 8 months, Apr 2025 to Nov 2025; an income tax return for "
                      f"AY 2025-26. {returns['explanation']} The return for AY 2026-27 is not yet due.")


def test_business_credits_over_two_accounts_cite_both_statements(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd")
    audited(root, case_id, "2026-03-31")
    first = bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 6_000_000}
                                 for ym in FY26])
    second = bank(root, case_id, [{"date": f"{ym}-18", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 1_500_000}
                                  for ym in FY26], last4="7777", bank_name="Ironleaf Bank")
    cam = _cam(client, analyst, root, case_id)
    turnover = _section(cam, "turnover")
    credits = next(r for r in _table(turnover)["rows"] if r[0]["text"] == "FY 2025-26")[4]
    assert credits["text"] == "INR 9.00 cr" and _cited(credits) == {first, second}
    # A finding on the business credits cites both statements, not the first account's only.
    finding = _summary_finding(cam, "TO-03")
    assert {first, second} <= {e["document_id"] for e in finding["citations"]}


def test_banking_tabulates_each_account_with_its_exclusions_and_the_accounts_without_statements(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    banking = _section(_cam(client, analyst, published_data_root, case_id), "banking")
    table = _table(banking)
    assert table["columns"] == ["Account", "Months", "Gross credits", "Excluded", "Business credits", "Average a month"]
    assert _rows(table) == [["Lotuscrest Bank ·1234", "12 (Apr 2025 to Mar 2026)", "INR 11.30 cr", "INR 50.00 lakh",
                             "INR 10.80 cr", "INR 90.00 lakh"]]
    assert all(_cited(c) == {docs["bank"]} for c in table["rows"][0][2:])
    assert _paragraphs(banking) == [
        "In Lotuscrest Bank ·1234, INR 50.00 lakh of credits is excluded from business credits: loan disbursal "
        "INR 50.00 lakh (1 credit).",
        # What the sourcing message says the account is.
        "No statement has been received for Account ·5678 (cash credit), which was declared and appears in the sourcing "
        "message."]


def test_year_end_balances_are_set_against_the_audited_cash_and_bank_balance(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root)
    fy26 = audited(root, case_id, "2026-03-31")
    first = bank(root, case_id, [{"date": "2026-03-20", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 100_000,
                                  "balance": 9_000_000}])
    second = bank(root, case_id, [{"date": "2026-03-25", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 50_000,
                                   "balance": 1_100_000}], last4="7777", bank_name="Ironleaf Bank")
    paragraph = next(b["paragraph"] for b in _blocks(_section(_cam(client, analyst, root, case_id), "banking"), "paragraph")
                     if b["paragraph"]["text"].startswith("At 31 Mar 2026"))
    assert paragraph["text"] == ("At 31 Mar 2026 the statements show INR 90.00 lakh in Lotuscrest Bank ·1234 and "
                                 "INR 11.00 lakh in Ironleaf Bank ·7777, INR 1.01 cr in all, against cash and bank "
                                 "balances of INR 60.00 lakh in the FY 2025-26 balance sheet; the statements' balances "
                                 "exceed the audited figure by INR 41.00 lakh.")
    assert _cited(paragraph) == {first, second, fy26}


def test_existing_facilities_by_lender_as_obligations_reconcile_them(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    obligations = _section(_cam(client, analyst, published_data_root, case_id), "obligations")
    table = _table(obligations)
    assert table["columns"] == ["Lender", "Facility", "Declared", "Sanction letter", "Bureau", "Instalment",
                                "Seen in the bank (a month)"]
    assert _rows(table) == [
        ["Lotuscrest Bank", "Cash credit", "INR 2.00 cr", "—", "INR 2.00 cr; outstanding INR 1.85 cr", "—", "—"],
        ["Tidewater Finance Limited", "Term loan", "Not declared", "INR 1.20 cr",
         "INR 1.20 cr; outstanding INR 75.00 lakh", "INR 2.50 lakh", "INR 2.50 lakh (12 months)"],
    ]
    tidewater = table["rows"][1]
    assert [_cited(c) for c in tidewater[3:7]] == [{docs["sanction"]}, {docs["bureau"]}, {docs["sanction"]}, {docs["bank"]}]
    assert _paragraphs(obligations) == [
        "The commercial bureau report gives the borrower rank 4, within the norm of at most rank 6.",
        "Existing sanctioned facilities total INR 3.20 cr across 2 lenders; the commercial bureau report shows "
        "INR 2.60 cr outstanding.",
        "The FY 2025-26 balance sheet shows borrowings of INR 2.70 cr: INR 1.50 cr long-term and INR 1.20 cr short-term.",
        "The commercial bureau report shows no overdue amount.",
        "Instalments seen in the bank total about INR 2.50 lakh a month; the facilities on file state instalments of "
        "INR 2.50 lakh a month.",
        "Debits of about INR 2.50 lakh a month to Tidewater Finance Limited (TIDEWATER FIN in the statement) appear "
        "in Lotuscrest Bank ·1234 in 12 months; the lender is not declared.",
        "A loan of INR 50.00 lakh was disbursed into Lotuscrest Bank ·1234 on 20 Jun 2025 (LOAN DISB TIDEWATER); the "
        "narration names Tidewater Finance Limited, a lender on file."]


def test_the_instalment_of_a_lender_with_two_facilities_is_their_sum(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root)
    declaration = add_doc(root, case_id, "existing_facilities_declaration", {"company_name": CO, "facilities": [
        {"lender": "Ashwood Finserv Limited", "facility": "Term loan", "sanctioned_amount": 9_500_000, "emi": 145_000},
        {"lender": "Ashwood Finserv Limited", "facility": "Equipment loan", "sanctioned_amount": 4_000_000,
         "emi": 90_000}]})
    table = _table(_section(_cam(client, analyst, root, case_id), "obligations"))
    [row] = table["rows"]
    assert [c["text"] for c in row[:3]] == ["Ashwood Finserv Limited", "Term loan and Equipment loan", "INR 1.35 cr"]
    assert row[5]["text"] == "INR 2.35 lakh (2 facilities)" and _cited(row[5]) == {declaration}
    # The DSCR counts the same two instalments.
    fr03 = next(n for n in _get(client, analyst, case_id, "policy")["norms"] if n["id"] == "FR-03")
    assert next(i for i in fr03["inputs"] if i["name"] == "annual_instalments")["value"] == 235_000 * 12


def test_a_facility_only_the_sourcing_message_declares_and_a_loan_no_facility_explains(client, published_data_root):
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
                     + [{"date": f"{ym}-05", "description": "NACH DR ASHWOOD FINSERV", "debit": 145_000} for ym in FY26])
    cam = _cam(client, analyst, root, case_id)
    obligations = _section(cam, "obligations")
    lotuscrest = next(r for r in _rows(_table(obligations)) if r[0] == "Lotuscrest Bank")
    assert lotuscrest == ["Lotuscrest Bank", "Cash credit", "In the sourcing message; limit not on file", "—", "—", "—", "—"]
    paragraphs = _paragraphs(obligations)
    assert ("The cash credit with Lotuscrest Bank (account ·5678) is declared only in the sourcing message: neither the "
            "declaration of existing facilities nor the commercial bureau report shows it; its limit is not on file."
            in paragraphs)
    disbursal = next(b["paragraph"] for b in _blocks(obligations, "paragraph")
                     if b["paragraph"]["text"].startswith("A loan of"))
    assert disbursal["text"] == ("A loan of INR 50.00 lakh was disbursed into Lotuscrest Bank ·1234 on 20 Jun 2025 "
                                 "(TL DISBURSAL LN 778812); no facility on file matches it and no instalment for it "
                                 "appears in the statements.")
    assert _cited(disbursal) == {statement}
    assert ("No statement has been received for Lotuscrest Bank ·5678 (cash credit), which was declared and appears in "
            "the sourcing message." in _paragraphs(_section(cam, "banking")))


def test_short_term_borrowings_without_a_working_capital_facility_on_file_are_noted(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)  # long-term borrowings of 10 cr; no facility on file
    paragraphs = _paragraphs(_section(_cam(client, analyst, published_data_root, case_id), "obligations"))
    assert ("The FY 2025-26 balance sheet shows borrowings of INR 11.20 cr: INR 10.00 cr long-term and INR 1.20 cr "
            "short-term. No working-capital facility is on file to account for the short-term borrowings." in paragraphs)
    assert ("Instalments seen in the bank total about INR 1.45 lakh a month; no facility on file states an instalment."
            in paragraphs)


def test_cross_verification_by_area_and_each_discrepancy_with_its_decision(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, _ = _full_case(client, analyst, root)
    _refresh(root, case_id)
    escalated = _decide(client, analyst, case_id, "ID-01", "escalate")
    dismissed = _decide(client, analyst, case_id, "TO-03", "dismiss")
    accepted = _decide(client, analyst, case_id, "OB-01", "accept")
    cam = _get(client, analyst, case_id, "cam")
    board = _get(client, analyst, case_id, "cross-verification")
    section = _section(cam, "verification")
    assert _paragraphs(section)[0] == (f"The latest cross-check run, {board['run']['id']}, applied "
                                       f"{board['run']['rules']} checks to {board['run']['sources']} types of source document.")
    areas = _table(section, "Checks by area")
    assert areas["columns"] == ["Area", "Checks", "Discrepancies", "Accepted as valid", "Open", "Could not be completed"]
    names = {"identity": "Identity consistency", "turnover": "Turnover", "accounts": "Bank accounts",
             "obligations": "Existing obligations"}
    assert _rows(areas) == [
        [names[a["area"]], str(a["rules"]), str(a["discrepancies"]), str(1 if a["area"] == "obligations" else 0),
         str(a["open"]), str(a["incomplete"])] for a in board["areas"]]
    found = _table(section, "Discrepancies")
    assert found["columns"] == ["Ref", "Severity", "Finding", "Detail", "Status"]
    failed = [i["finding"] for i in board["items"] if i["finding"]["outcome"] == "fail"]
    assert [r[0] for r in _rows(found)] == [f["ref"] for f in failed]
    status = {r[0]: r[4] for r in _rows(found)}
    assert status[escalated["ref"]] == "Escalated; blocks submission"
    # Accept means a valid finding, not one cleared.
    assert status[dismissed["ref"]] == "Not valid" and status[accepted["ref"]] == "Accepted as valid"
    promoter = next(f for f in failed if f["rule_id"] == "ID-04")
    assert status[promoter["ref"]] == "Open; blocks submission"
    detail = next(r for r in found["rows"] if r[0]["text"] == escalated["ref"])
    assert detail[1]["text"] == "Serious" and detail[2]["text"] == escalated["finding_title"]
    assert detail[3]["text"] == escalated["explanation"] and detail[3]["citations"]
    # The title leaves out the year or months its explanation, beside it, states.
    scoped = [f for f in failed if f["scope"] and f["scope"] in f["explanation"]]
    assert scoped and all(next(r for r in found["rows"] if r[0]["text"] == f["ref"])[2]["text"] == f["finding_title"]
                          for f in scoped)
    # A finding found not valid is not stated as a discrepancy anywhere else.
    assert not any(dismissed["explanation"] in p for p in _paragraphs(_section(cam, "turnover")))


def test_the_checks_not_completed_are_listed_with_what_would_complete_them(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, header={"promoters": {"value": "Tarun Velankar", "source": "person"}})
    audited(root, case_id, "2026-03-31")
    for period in PERIODS[:7]:
        gstr(root, case_id, period, 10_000_000)
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 9_000_000}
                         for ym in FY26[:7]], end="2025-10-31")
    cam = _cam(client, analyst, root, case_id)
    board = _get(client, analyst, case_id, "cross-verification")
    incomplete = [i["finding"] for i in board["items"] if i["finding"]["outcome"] == "incomplete"]
    assert any(f["request"] for f in incomplete)
    table = _table(_section(cam, "verification"), "Checks not completed")
    assert table["columns"] == ["Check", "Why", "What would complete it"]
    assert _rows(table) == [[f["title"], f["explanation"],
                             (f["request"][:1].upper() + f["request"][1:]) if f["request"] else "—"] for f in incomplete]
    items = [i for i in cam["summary"] if i["kind"] == "incomplete"]
    assert [(i["ref"], i["title"], i["request"], i["text"], i["severity"]) for i in items] == [
        (f["rule_id"], f["title"], f["request"], f["explanation"], f["severity"]) for f in incomplete]
    facts = _facts(_section(cam, "snapshot")["blocks"][0])
    assert facts["Cross-checks"]["text"].endswith(f"; {len(incomplete)} could not be completed")


def test_the_summary_lists_findings_not_dismissed_as_a_register(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, _ = _full_case(client, analyst, root)
    _refresh(root, case_id)
    escalated = _decide(client, analyst, case_id, "ID-01", "escalate")
    dismissed = _decide(client, analyst, case_id, "TO-03", "dismiss")
    accepted = _decide(client, analyst, case_id, "OB-01", "accept")
    cam = _get(client, analyst, case_id, "cam")
    board = _get(client, analyst, case_id, "cross-verification")
    findings = {i["ref"]: i for i in cam["summary"] if i["kind"] == "finding"}
    expected = [i["finding"]["ref"] for i in board["items"] if i["finding"]["outcome"] == "fail"
                and i["finding"]["ref"] != dismissed["ref"]]
    assert list(findings) == expected
    pan = findings[escalated["ref"]]
    assert (pan["rule"], pan["title"], pan["severity"], pan["status"], pan["blocking"]) == (
        "ID-01", "Entity PAN differs between documents", "serious", "Escalated", True)
    # A register: reference, severity, title, status and blocking, cited; the explanation is in section 10.
    assert pan["text"] == "" and pan["citations"]
    facilities = findings[accepted["ref"]]
    assert (facilities["status"], facilities["blocking"]) == ("Accepted as valid", False)
    scoped = [i["finding"] for i in board["items"] if i["finding"]["ref"] in findings and i["finding"]["scope"]]
    assert scoped and all(findings[f["ref"]]["title"] == f"{f['finding_title']} · {f['scope']}" for f in scoped)
    kinds = [i["kind"] for i in cam["summary"]]
    assert kinds == sorted(kinds, key=["finding", "incomplete", "deviation", "unassessed", "query"].index)
    queries = [i for i in cam["summary"] if i["kind"] == "query"]
    open_queries = [q for q in _get(client, analyst, case_id, "queries") if not q["resolved"]]
    assert [(q["ref"], q["text"], q["group"]) for q in queries] == [(q["id"], q["text"], q["group"]) for q in open_queries]
    assert all(q["title"] is None for q in queries)


def test_each_finding_is_explained_once_in_the_memo(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id, _ = _full_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    texts = _texts(cam)
    failed = [i["finding"] for i in _get(client, analyst, case_id, "cross-verification")["items"]
              if i["finding"]["outcome"] == "fail"]
    for f in failed:
        assert sum(t.count(f["explanation"]) for t in texts) == 1, f["rule_id"]


def test_finding_citations_follow_the_rows_the_finding_is_about(client: TestClient, published_data_root: Path):
    """ID-06 cites the flagged director's KYC, not the first KYC; BA-01 the sourcing message that
    declares the account; a query raised by a finding cites the finding's pages; DOC-02 both years."""
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id, docs = _full_case(client, analyst, root)
    cam = _cam(client, analyst, root, case_id)
    identifiers = {e["document_id"] for e in _summary_finding(cam, "ID-06")["citations"]}
    assert docs["kyc_ishita"] in identifiers and docs["kyc_tarun"] not in identifiers
    assert docs["memorandum"] in identifiers
    declared = _summary_finding(cam, "BA-01")
    assert docs["message"] in {e["document_id"] for e in declared["citations"]}
    board = {i["finding"]["id"]: i["finding"] for i in _get(client, analyst, case_id, "cross-verification")["items"]}
    queries = {q["id"]: q for q in _get(client, analyst, case_id, "queries")}
    registered = {i["ref"]: i for i in cam["summary"] if i["kind"] == "finding"}
    raised = 0
    for item in cam["summary"]:
        q = queries.get(item["ref"]) if item["kind"] == "query" else None
        if q and q["source_kind"] == "finding" and q["source_ref"].split(":", 1)[-1] in board:
            f = board[q["source_ref"].split(":", 1)[-1]]
            assert item["citations"] == registered[f["ref"]]["citations"], f["rule_id"]
            raised += 1
    assert raised
    years = next(r for r in _table(_section(cam, "policy"))["rows"] if r[0]["text"].endswith("(DOC-02)"))
    assert _cited(years[2]) == {docs["fy25"], docs["fy26"]}


def test_an_undeclared_account_is_cited_to_its_own_statement(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root, header={
        "existing_banking": {"value": "current account with Lotuscrest Bank a/c 90100001234", "source": "person"}})
    declared = bank(root, case_id, [{"date": "2025-10-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 100_000}])
    undeclared = bank(root, case_id, [{"date": "2025-10-18", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 50_000}],
                      last4="7777", bank_name="Ironleaf Bank")
    finding = _summary_finding(_cam(client, analyst, root, case_id), "BA-02")
    cited = [e["document_id"] for e in finding["citations"]]
    assert undeclared in cited and declared not in cited[1:]


def test_the_summary_lists_exactly_the_policy_deviations(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    cam = _cam(client, analyst, published_data_root, case_id)
    norms = _get(client, analyst, case_id, "policy")["norms"]
    deviations = {n["id"]: n for n in norms if n["outcome"] == "deviation"}
    items = [i for i in cam["summary"] if i["kind"] == "deviation"]
    assert {i["ref"] for i in items} == set(deviations)
    for i in items:
        n = deviations[i["ref"]]
        assert i["text"].startswith(n["category_label"]) and n["actual_text"] in i["text"] and n["required"] in i["text"]
        assert (i["rule"], i["title"]) == (n["id"], n["label"])
        if i["ref"] != "DOC-01":
            assert i["citations"], i["ref"]
    texts = {i["ref"]: i["text"] for i in items}
    assert texts["DOC-02"] == "Documentation: Audited financial statements cover 1 year against a norm of at least 2 years."
    assert texts["DOC-01"].startswith("Documentation: Blocking checklist items open: ")
    assert texts["DOC-01"].endswith(", where the norm is none.")
    applicable = [n for n in norms if n["outcome"] != "not_applicable"]
    counts = {o: sum(1 for n in applicable if n["outcome"] == o) for o in ("deviation", "cannot_evaluate", "pass")}
    policy = _section(cam, "policy")
    assert _paragraphs(policy)[0] == (
        f"{len(applicable)} norms apply, on the FY 2025-26 statements: {counts['deviation']} deviations, "
        f"{counts['cannot_evaluate']} not assessed and {counts['pass']} met.")


def test_unassessed_norms_are_summarised(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    unassessed = {i["ref"]: i["text"] for i in cam["summary"] if i["kind"] == "unassessed"}
    assert unassessed["EL-01"] == "Business vintage could not be assessed: the date of incorporation is not on file."
    assert unassessed["EL-02"] == ("The commercial bureau report is not on file, so the commercial bureau rank could not "
                                   "be assessed.")


def test_the_policy_table_and_the_approving_authority(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id, _ = _full_case(client, analyst, published_data_root)
    policy = _section(_cam(client, analyst, published_data_root, case_id), "policy")
    norms = [n for n in _get(client, analyst, case_id, "policy")["norms"] if n["outcome"] != "not_applicable"]
    table = _table(policy)
    assert table["columns"] == ["Norm", "Required", "Actual", "Result", "Category"]
    result = {"deviation": "Deviation", "pass": "Met", "cannot_evaluate": "Not assessed"}
    assert _rows(table) == [[f"{n['label']} ({n['id']})", n["required"], n["actual_text"] or "—", result[n["outcome"]],
                             n["category_label"]] for n in norms]
    required = {r[0]: r[1] for r in _rows(table)}
    assert (required["Positive net worth (EL-03)"], required["Profit in the latest year (EL-04)"],
            required["Blocking checklist items open (DOC-01)"]) == ("positive", "no loss", "none")
    assert table["note"] is None
    paragraphs = _paragraphs(policy)
    assert "Working-capital cycle is 90 days against a norm of at most 75 days (Financial norms)." in paragraphs
    assert "DSCR could not be assessed: the proposed term loan's instalment is not on file." in paragraphs
    assert [b["text"] for b in _blocks(policy, "note")] == ["Every norm is an interim proposal awaiting RBL's policy norms."]
    assert [b["text"] for b in _blocks(policy, "subheading")] == ["Approving authority"]
    authority = _facts(_blocks(policy, "facts")[0])
    assert {k: v["text"] for k, v in authority.items()} == {
        "Amount requested": "INR 6.50 cr",
        "Amounts used": "The total of INR 6.50 cr for each product (amounts per facility not captured)",
        "Amount authority, working capital": "Zonal Credit Committee (amounts above INR 5.00 cr up to INR 15.00 cr)",
        "Amount authority, term loan": "Zonal Credit Committee (amounts above INR 3.00 cr up to INR 10.00 cr)",
        "Deviation, financial norms": "Head Office Credit Committee (one level above the amount authority; "
                                      "FR-06 Working-capital cycle)",
        "Deviation, documentation": "Head Office Credit Committee (one level above the amount authority; "
                                    "DOC-01 Blocking checklist items open)",
        "Authority required": "At least Head Office Credit Committee",
        "Could rise to": "No change if DSCR proves a deviation",
        "Matrix": "Provisional matrix",
    }


def test_documentation_states_readiness_and_each_open_item_with_what_is_missing(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    section = _section(_cam(client, analyst, published_data_root, case_id), "documentation")
    readiness = _get(client, analyst, case_id, "checklist")
    facts = _facts(_blocks(section, "facts")[0])
    assert facts["Readiness"]["text"] == f"{readiness['score_pct']:g}% against a review gate of {readiness['gate_pct']}%"
    assert facts["Blocking items open"]["text"] == str(readiness["blocking_open"])
    table = _table(section)
    assert table["columns"] == ["Item", "Status", "What is missing"]
    labels = {"missing": "Missing", "insufficient": "Insufficient", "in_review": "In review"}
    open_items = [i for i in readiness["items"] if i["status"] in labels]
    assert open_items and [r[:2] for r in _rows(table)] == [[i["name"], labels[i["status"]]] for i in open_items]
    kyc = next(r for r in _rows(table) if r[0] == "KYC of directors, partners or proprietor")
    assert "Sunil Karve" in kyc[2]
    statements = next(r for r in _rows(table) if r[0].startswith("Bank statements"))
    # The account the sourcing message declares, with no statement; the outdated copy, stated once.
    assert "statement not received for declared account ·5678 (1 of 2 accounts on file)" in statements[2]
    assert "Outdated: statement for ·1234 dated 31 Mar 2026, older than the 45 days allowed at 29 Sep 2026" in statements[2]
    assert not any(p.startswith("Outdated documents: ") for p in _paragraphs(section))


def test_every_figure_in_the_memo_is_cited(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id, _ = _full_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    for section_id in ("financials", "working_capital", "turnover", "banking", "obligations"):
        for block in _blocks(_section(cam, section_id), "table"):
            table = block["table"]
            for row in table["rows"]:
                for i in table["numeric"]:
                    if row[i]["text"].startswith("INR") or row[i]["text"][:1].isdigit():
                        assert row[i]["citations"], (section_id, row[0]["text"], table["columns"][i])
    for item in cam["summary"]:
        if item["kind"] in ("finding", "deviation") and item["ref"] != "DOC-01":
            assert item["citations"], item["ref"]


def test_the_memo_says_the_norms_are_interim(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    policy = _section(_cam(client, analyst, published_data_root, case_id), "policy")
    assert any("interim proposal" in b["text"] for b in _blocks(policy, "note"))


# --- Sources ---


def _reading_order(cam: dict) -> list[dict]:
    out = []
    for s in cam["sections"]:
        for b in s["blocks"]:
            out += b["paragraph"]["citations"] if b["paragraph"] else []
            out += [e for f in b["facts"] for e in f["value"]["citations"]]
            out += [e for row in (b["table"]["rows"] if b["table"] else []) for c in row for e in c["citations"]]
    return out + [e for i in cam["summary"] for e in i["citations"]]


def test_sources_are_numbered_by_first_citation_and_named_as_the_case_lists_them(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id, docs = _full_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    cited = _reading_order(cam)
    order = list(dict.fromkeys(e["document_id"] for e in cited))
    assert [s["document_id"] for s in cam["sources"]] == order
    assert [s["number"] for s in cam["sources"]] == list(range(1, len(order) + 1))
    for s in cam["sources"]:
        assert s["pages"] == sorted({e["page"] for e in cited if e["document_id"] == s["document_id"]})
    by_id = {s["document_id"]: s for s in cam["sources"]}
    # The borrower, cited to the sourcing message, comes first.
    assert cam["sources"][0]["document_id"] == docs["message"]
    assert (by_id[docs["message"]]["label"], by_id[docs["message"]]["file_name"]) == ("Sourcing message", "application-message.txt")
    # Several of a type are told apart by year, period or person; a type the case has once is not qualified.
    assert by_id[docs["fy26"]]["label"] == "Audited financial statements · FY 2025-26"
    assert by_id[docs["fy25"]]["label"] == "Audited financial statements · FY 2024-25"
    assert by_id[docs["gst"]]["label"] == "GSTR-3B · Apr 2025"
    assert by_id[docs["kyc_tarun"]]["label"] == "Director KYC · Tarun Velankar"
    assert by_id[docs["bank"]]["label"] == "Bank statement"
    assert by_id[docs["certificate"]]["file_name"].startswith("certificate_of_incorporation-")


def test_several_statements_returns_and_letters_are_told_apart(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    root = published_data_root
    case_id = make_case(client, analyst, root)
    first = bank(root, case_id, [{"date": "2025-10-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 100_000}])
    second = bank(root, case_id, [{"date": "2025-10-18", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 50_000}],
                  last4="7777", bank_name="Ironleaf Bank")
    returns = [add_doc(root, case_id, "income_tax_return", {"pan": "AAACK1234F", "assessment_year": ay,
                                                            "income_computation": [{"particulars": "Turnover",
                                                                                    "amount": 94_400_000}]})
               for ay in ("2025-26", "2026-27")]
    letters = [add_doc(root, case_id, "sanction_letter", {"lender_name": lender, "facilities": [
        {"facility": "Term loan", "sanctioned_amount": 9_500_000, "emi": 145_000}]})
        for lender in ("Ashwood Finserv Limited", "Tidewater Finance Limited")]
    from engine import output_sources

    conn = db.connect(root)
    try:
        named = output_sources.documents(conn, root, case_id)
    finally:
        conn.close()
    assert (named[first][0], named[second][0]) == ("Bank statement · Lotuscrest Bank ·1234",
                                                   "Bank statement · Ironleaf Bank ·7777")
    assert [named[r][0] for r in returns] == ["Income tax return · AY 2025-26", "Income tax return · AY 2026-27"]
    assert [named[letter][0] for letter in letters] == ["Sanction letter · Ashwood Finserv Limited",
                                                        "Sanction letter · Tidewater Finance Limited"]


def test_the_complete_file_drafts_every_section(client: TestClient, published_data_root: Path):
    """The complete fixture file, read by the document-processing service (stub)."""
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Kestrel Fabricators Pvt Ltd", facilities=["cash_credit"],
                        amount_inr=30_000_000, collateral_present=False)
    assert upload(client, rm, case_id, case_files("complete")).status_code == 202
    run_jobs(published_data_root)
    analyst = sign_in(client, ANALYST)
    cam = _cam(client, analyst, published_data_root, case_id)
    assert all(s["blocks"] for s in cam["sections"]), [s["id"] for s in cam["sections"] if not s["blocks"]]
    assert _rows(_table(_section(cam, "promoters")))[0][:5] == ["Tarun Velankar", "Director", "01234567", "ABCPV1234K", "Yes"]
    assert _paragraphs(_section(cam, "verification"))[-1] == "No discrepancy was found."
    files = {s["file_name"] for s in cam["sources"]}
    assert {"kestrel certificate of incorporation.pdf", "kestrel audited fy2026.pdf"} <= files
    assert "Collateral: none offered, as recorded on the case at intake." in _paragraphs(_section(cam, "proposal"))
