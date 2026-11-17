"""F-09.8, F-15.8: a file read as a case document type a person made. No classification; named
fields are read by the model, or with none named the model proposes them; every value is checked on
its page, and a discovered field always goes to a person (F-17.7)."""

import re

from ingestion.contracts import CaseField, CaseType
from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.store import Store

from .conftest import fixture_doc, spec

DOC = "Southgate_Entity_PAN.pdf"


def _lines(req) -> dict[str, str]:
    return dict(re.findall(r"^(p\d+\.l\d+): (.*)$", req.user, re.M))


def _find(lines: dict[str, str], rx: str) -> tuple[str, str] | None:
    for i, t in lines.items():
        m = re.search(rx, t)
        if m:
            return i, m.group(0)
    return None


PAN = r"[A-Z]{5}\d{4}[A-Z]"


def answerer(req) -> dict:
    lines = _lines(req)
    if req.task == "discover":
        out = []
        if hit := _find(lines, PAN):
            out.append({"label": "Permanent Account Number", "value": hit[1], "line_ids": [hit[0]]})
            out.append({"label": "PAN", "value": hit[1], "line_ids": [hit[0]]})  # the same fact again: dropped
        out.append({"label": "Sanction amount", "value": "Rs 99,99,999", "line_ids": [next(iter(lines))]})  # not printed
        return {"fields": out}
    fields = re.findall(r"^- (\w+) \(", req.user, re.M)
    hit = _find(lines, PAN)
    return {"fields": {f: ({"value": hit[1], "line_ids": [hit[0]]} if f == "pan_number" and hit else {"value": None, "line_ids": []})
                       for f in fields}}


def _run(cfg, ct: CaseType, model=True):
    b = fixture_doc(DOC)
    client = ModelClient(FixtureProvider(cfg.llm, answerer), "record", Store()) if model else None
    return Ingestor(cfg, Store(), client, None).process_file("C", spec("x.pdf", b).model_copy(update={"case_type": ct}), b)


def test_named_fields_are_read_and_checked_on_the_page(cfg):
    r = _run(cfg, CaseType(id="CDT-1", name="Tax registration letter",
                           fields=[CaseField(name="pan_number", hint="the PAN"), CaseField(name="issue_date")]))
    assert r.status == "processed" and r.classification.tier == "person" and r.classification.type == "CDT-1"
    d = r.documents[0]
    assert d.document_type == "CDT-1" and d.page_from == 1
    pan = d.fields["pan_number"]
    assert pan.status == "found" and pan.method == "model" and pan.origin == "named" and pan.source.page == 1
    assert re.fullmatch(PAN, pan.value)
    assert d.fields["issue_date"].status == "missing" and d.fields["issue_date"].origin == "named"


def test_with_no_fields_named_the_model_proposes_them_and_each_goes_to_review(cfg):
    r = _run(cfg, CaseType(id="CDT-2", name="Tax registration letter"))
    d = r.documents[0]
    # The repeated fact and the value not on the page are dropped; the PAN the model proposed is also the
    # gap field `pan` (F-15.9), so it is reported once, under that name, with the document's label.
    assert "permanent_account_number" not in d.fields and "sanction_amount" not in d.fields
    f = d.fields["pan"]
    assert f.origin == "gap" and f.label == "Permanent Account Number" and f.needs_review
    assert r.decision == "human_review"
    assert {"kind": "gap_field", "field": "pan", "instance": 1} in r.review_reasons


def test_without_a_model_named_fields_are_missing_and_nothing_is_invented(cfg):
    r = _run(cfg, CaseType(id="CDT-3", name="Letter", fields=[CaseField(name="pan_number")]), model=False)
    assert r.documents[0].fields["pan_number"].status == "missing" and r.documents[0].fields["pan_number"].reason == "no_model"
    r = _run(cfg, CaseType(id="CDT-4", name="Letter"), model=False)
    # Nothing is proposed without a model; the gap fields an identifier pattern finds are still read.
    assert {k: f.origin for k, f in r.documents[0].fields.items()} == {"pan": "gap", "cin": "gap"}
    assert r.decision == "human_review"


def test_the_gap_fields_are_read_from_every_such_document_and_held_for_review(cfg):
    """F-15.9: the same request for every document; a named field of the same name is read once."""
    r = _run(cfg, CaseType(id="CDT-6", name="Letter", fields=[CaseField(name="issue_date")]), model=False)
    pan = r.documents[0].fields["pan"]
    assert pan.origin == "gap" and pan.method == "identifier" and pan.needs_review and re.fullmatch(PAN, pan.value)
    r = _run(cfg, CaseType(id="CDT-7", name="Letter", fields=[CaseField(name="pan")]))
    assert r.documents[0].fields["pan"].origin == "named"
    seen = []
    def spy(req):
        seen.append(req)
        return answerer(req)
    b = fixture_doc(DOC)
    for ct in (CaseType(id="CDT-8", name="Letter A"), CaseType(id="CDT-9", name="Letter B", description="x")):
        client = ModelClient(FixtureProvider(cfg.llm, spy), "record", Store())
        Ingestor(cfg, Store(), client, None).process_file("C", spec("x.pdf", b).model_copy(update={"case_type": ct}), b)
    # The gap request is the same whatever the type or the case: field names and hints, no other value.
    asks = [q.user for q in seen if q.task == "extract"]
    assert len(asks) == 2 and asks[0] == asks[1] and "- legal_name (string)" in asks[0]


def test_a_discovery_replays_from_its_recording(cfg):
    """Principle 6: the recorded answer, not a fresh call, makes the reading repeatable."""
    b, store = fixture_doc(DOC), Store()
    s = spec("x.pdf", b).model_copy(update={"case_type": CaseType(id="CDT-5", name="Tax registration letter")})
    first = Ingestor(cfg, Store(), ModelClient(FixtureProvider(cfg.llm, answerer), "record", store), None).process_file("C", s, b)
    replay = ModelClient(FixtureProvider(cfg.llm, lambda r: 1 / 0), "replay", store)
    again = Ingestor(cfg, Store(), replay, None).process_file("C", s, b)
    assert replay.calls == 0 and again.documents[0].fields == first.documents[0].fields
