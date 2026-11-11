"""The second pass (F-08.1, F-08.2): other documents of the classified type's category found in the same
file, each read on its own pages. The bundle is the reference COI, PAN letter and MoA scanned as one PDF."""

import io
import json
import re

import pypdfium2 as pdfium
import pytest

from ingestion.llm.openai import FixtureProvider
from ingestion.llm.provider import ModelRequest
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.stages.siblings import group_of
from ingestion.store import Store

from .conftest import fixture_doc, spec

COI = "Southgate_Certificate_of_Incorporation.pdf"
PAN = "Southgate_Entity_PAN.pdf"
MOA = "Southgate_MOA_AOA.pdf"
NAME = "Southgate Textiles Private Limited"


def merged(*names: str) -> bytes:
    out = pdfium.PdfDocument.new()
    for n in names:
        out.import_pages(pdfium.PdfDocument(fixture_doc(n)))
    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue()


def run(cfg, data: bytes, assigned: str | None = "certificate_of_incorporation", model=None, store=None):
    sp = spec("kyc_bundle.pdf", data)
    sp.assigned_type = assigned
    store = store or Store()
    return Ingestor(cfg, store, model, None).process_file("CASE", sp, data), store


def siblings_trace(store: Store, run_id: str) -> list[dict]:
    return next(s["payload"] for s in store.get_stages(run_id) if s["stage"] == "siblings")


def edited(cfg, **siblings):
    c = cfg.model_copy(deep=True)
    for k, v in siblings.items():
        setattr(c.llm.siblings, k, v)
    return c


def test_the_group_is_the_other_types_of_the_category(cfg):
    assert group_of(cfg, "certificate_of_incorporation") == [
        "memorandum_articles_of_association", "company_pan", "director_kyc", "board_resolution_borrowing"]
    assert group_of(cfg, "audited_financial_statements") == ["income_tax_return"]


def test_a_bundle_becomes_one_document_per_type_each_on_its_own_pages(cfg):
    r, _ = run(cfg, merged(COI, PAN, MOA))
    got = [(d.document_type, d.origin, d.pages) for d in r.documents]
    assert got == [("certificate_of_incorporation", "classified", [1]),
                   ("company_pan", "sibling", [2]),
                   ("memorandum_articles_of_association", "sibling", [3, 4, 5, 6, 7, 8])]
    coi, pan, moa = r.documents
    assert coi.classification is None and coi.fields["cin"].value == "U17291TZ2016PTC027431"
    assert pan.classification.tier == "sibling" and pan.classification.type == "company_pan"
    assert pan.fields["pan"].value == "AAHCS6612M" and pan.fields["date_of_issue"].value == "2016-03-24"
    assert pan.fields["pan"].source.page == 2 and pan.identity == {"name": NAME, "pan": "AAHCS6612M"}
    assert moa.fields["authorized_share_capital"].value == 15000000 and moa.page_from == 3 and moa.page_to == 8
    assert [d.instance_no for d in r.documents] == [1, 2, 3]


def test_a_document_that_only_mentions_another_type_does_not_create_it(results):
    # The certificate prints the company's PAN, but no page of it is headed as a PAN letter.
    r = results[COI]
    assert [(d.document_type, d.origin) for d in r.documents] == [("certificate_of_incorporation", "classified")]
    assert r.documents[0].fields["pan"].value == "AAHCS6612M"


def test_switched_off_the_file_is_read_as_before(cfg):
    r, store = run(edited(cfg, enabled=False), merged(COI, PAN, MOA))
    assert [(d.document_type, d.pages) for d in r.documents] == [("certificate_of_incorporation", list(range(1, 9)))]
    assert siblings_trace(store, r.run_id) == []


def test_a_part_without_its_key_fields_is_dropped_and_its_pages_stay(cfg):
    r, store = run(edited(cfg, min_key_fields=99), merged(COI, PAN, MOA))
    assert [(d.document_type, d.pages) for d in r.documents] == [("certificate_of_incorporation", list(range(1, 9)))]
    assert {(t["type"], t["outcome"], t["reason"]) for t in siblings_trace(store, r.run_id)} == {
        ("company_pan", "dropped", "key_fields_not_found"), ("memorandum_articles_of_association", "dropped", "key_fields_not_found")}


def test_parts_that_would_take_every_page_leave_the_classification_standing(cfg):
    r, store = run(cfg, fixture_doc(MOA))     # an MoA a person assigned as a certificate
    assert [(d.document_type, d.origin) for d in r.documents] == [("certificate_of_incorporation", "classified")]
    assert [(t["type"], t["outcome"], t["reason"]) for t in siblings_trace(store, r.run_id)] == [
        ("memorandum_articles_of_association", "dropped", "whole_file")]


@pytest.mark.parametrize("order, pages", [((COI, PAN), ([1], [2])), ((PAN, COI), ([2], [1]))])
def test_a_page_flagged_as_mixed_content_becomes_its_own_document(cfg, order, pages):
    r, _ = run(cfg, merged(*order), assigned=None)      # classified by its signals, not by a person
    assert r.classification.tier == "signals" and r.classification.mixed_content    # the service saw the other page ...
    assert [(d.document_type, d.pages) for d in r.documents] == [
        ("certificate_of_incorporation", pages[0]), ("company_pan", pages[1])]
    assert not any(x["kind"] == "mixed_content" for x in r.review_reasons)          # ... and it is now accounted for


# --- with a model ----------------------------------------------------------------------------------

def reader(req: ModelRequest) -> dict:
    """Answers the extract and sibling prompts with the company name where a line prints it."""
    fields = re.findall(r"^- (\w+) \(", req.user, re.M)
    lines = dict(re.findall(r"^(p\d+\.l\d+): (.*)$", req.user, re.M))
    hit = next((i for i, t in lines.items() if NAME.casefold() in t.casefold()), None)
    out = {f: {"value": NAME if f == "company_name" and hit else None, "line_ids": [hit] if f == "company_name" and hit else []} for f in fields}
    return {"fields": out}


def client(cfg, store, mode, seen=None):
    def answer(req):
        if seen is not None:
            seen.append(req)
        return reader(req)
    return ModelClient(FixtureProvider(cfg.llm, answer), mode, store)


def test_the_model_reads_a_part_with_its_own_prompt(cfg):
    seen: list[ModelRequest] = []
    store = Store()
    r, _ = run(cfg, merged(COI, PAN, MOA), model=client(cfg, store, "record", seen), store=store)
    sib = [q for q in seen if q.task == "sibling"]
    assert sib and all("found inside a file containing a Certificate of Incorporation" in q.system for q in sib)
    pan_req = next(q for q in sib if "Company PAN" in q.system)
    assert set(re.findall(r"^(p\d+)\.l\d+:", pan_req.user, re.M)) == {"p2"}    # only the part's own pages
    pan = r.documents[1]
    assert pan.fields["company_name"].method == "model" and pan.fields["company_name"].source.page == 2


def test_record_then_replay_is_byte_identical(cfg):
    store = Store()
    data = merged(COI, PAN, MOA)
    first, _ = run(cfg, data, model=client(cfg, store, "record"), store=store)
    again, _ = run(cfg, data, model=client(cfg, store, "replay"), store=store)
    assert json.loads(first.model_dump_json()) == json.loads(again.model_dump_json())


def test_without_recordings_a_part_stands_only_on_what_the_rules_verified(cfg):
    store = Store()
    r, _ = run(cfg, merged(COI, PAN, MOA), model=client(cfg, store, "replay"), store=store)
    trace = {t["type"]: t for t in siblings_trace(store, r.run_id)}
    # The PAN letter's PAN is read by its identifier rule, so the part stands; its name waits for the model.
    assert trace["company_pan"]["outcome"] == "found"
    pan = next(d for d in r.documents if d.document_type == "company_pan")
    assert pan.fields["company_name"].status == "missing" and pan.fields["company_name"].reason == "model_unavailable:replay_miss"
    # Nothing on the memorandum's pages was verified, so no half-read memorandum is reported.
    assert (trace["memorandum_articles_of_association"]["outcome"], trace["memorandum_articles_of_association"]["reason"]) == (
        "dropped", "model_unavailable:replay_miss")
    assert [d.document_type for d in r.documents] == ["certificate_of_incorporation", "company_pan"]


@pytest.mark.parametrize("order, expected", [
    ((COI, PAN, MOA), [("certificate_of_incorporation", [1]), ("company_pan", [2]), ("memorandum_articles_of_association", [3, 4, 5, 6, 7, 8])]),
    ((MOA, COI, PAN), [("memorandum_articles_of_association", [1, 2, 3, 4, 5, 6]), ("certificate_of_incorporation", [7]), ("company_pan", [8])]),
    ((PAN, MOA, COI), [("company_pan", [1]), ("memorandum_articles_of_association", [2, 3, 4, 5, 6, 7]), ("certificate_of_incorporation", [8])]),
])
def test_a_bundle_whose_whole_file_signals_contradict_is_placed_by_its_opening_document(cfg, order, expected):
    # The certificate's and the memorandum's signals rule each other out across the whole file; the opening
    # document, judged on its own pages, places the file, and the second pass finds the rest.
    r, _ = run(cfg, merged(*order), assigned=None)
    assert r.classification.tier == "signals" and "placed by the one it opens with" in r.classification.reason
    assert [(d.document_type, d.pages) for d in r.documents] == expected
    assert [d.origin for d in r.documents] == ["classified", "sibling", "sibling"]
