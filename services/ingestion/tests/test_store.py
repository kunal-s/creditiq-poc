import json
import sqlite3

from ingestion.pipeline import Ingestor
from ingestion.store import Store

from .conftest import fixture_doc, spec

N = "Southgate_Certificate_of_Incorporation.pdf"


def test_sqlite_supports_jsonb():
    assert sqlite3.sqlite_version_info >= (3, 45, 0)


def test_stage_output_and_extracted_text_are_stored_as_jsonb(cfg):
    store = Store()
    r = Ingestor(cfg, store, None, None).process_file("CASE", spec(N, fixture_doc(N)), fixture_doc(N))
    assert store._q("SELECT typeof(words), typeof(lines), typeof(summary) FROM pages")[0] == ("blob", "blob", "blob")
    assert store._q("SELECT typeof(payload) FROM stage_results LIMIT 1")[0] == ("blob",)
    assert store._q("SELECT typeof(result) FROM runs")[0] == ("blob",)
    page = store.get_page(r.run_id, 1)
    assert page["grade"] == "A" and any("Incorporation" in l["text"] for l in page["lines"]) and "CERTIFICATE OF INCORPORATION" in page["text"]
    assert page["lines"][0]["words"][0][1:5] and len(page["lines"][0]["words"][0]) == 7  # text, x0, y0, x1, y1, conf, cell


def test_the_jsonb_can_be_queried_in_sql(cfg):
    store = Store()
    r = Ingestor(cfg, store, None, None).process_file("CASE", spec(N, fixture_doc(N)), fixture_doc(N))
    assert store.query_words(r.run_id, "AAHCS6612M") == [{"page": 1, "count": 2}]
    row = store._q("SELECT result ->> '$.classification.type', result ->> '$.documents[0].fields.cin.value' FROM runs WHERE id=?", (r.run_id,))[0]
    assert row == ("certificate_of_incorporation", "U17291TZ2016PTC027431")
    assert store._q("SELECT type, tier FROM classifications")[0] == ("certificate_of_incorporation", "signals")
    assert store._q("SELECT json_extract(fields,'$.cin.confidence') FROM extractions")[0][0] > 0.9
    assert json.loads(store._q("SELECT json(missing) FROM extractions")[0][0]) == []


def test_result_round_trips_through_the_database(cfg):
    store = Store()
    r = Ingestor(cfg, store, None, None).process_file("CASE", spec(N, fixture_doc(N)), fixture_doc(N))
    assert store.get_run(r.run_id)["result"] == json.loads(r.model_dump_json())
    assert store.list_runs("CASE")[0]["decision"] == "auto_accept"


def test_stages_are_recorded_in_order_with_timings_outside_the_result(cfg):
    store = Store()
    r = Ingestor(cfg, store, None, None).process_file("CASE", spec(N, fixture_doc(N)), fixture_doc(N))
    st = store.get_stages(r.run_id)
    assert [s["stage"] for s in st][:3] == ["quality_gate", "read", "route"] and all(isinstance(s["ms"], int) for s in st)


def test_the_database_persists_across_connections(cfg, tmp_path):
    p = tmp_path / "i.sqlite3"
    s1 = Store(p)
    r = Ingestor(cfg, s1, None, None).process_file("CASE", spec(N, fixture_doc(N)), fixture_doc(N))
    s2 = Store(p)
    assert s2.get_run(r.run_id)["status"] == "processed"
