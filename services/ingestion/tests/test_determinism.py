"""Principle 6: same bytes, same configuration, same answer, byte for byte."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor, run_id_for
from ingestion.store import Store
from ingestion.util import canonical_json

from . import model_answers
from .conftest import IN_SCOPE, OUT_OF_SCOPE, fixture_doc, spec

ALL = [*IN_SCOPE, *OUT_OF_SCOPE]


def run(cfg, name, store=None, model=None):
    return Ingestor(cfg, store or Store(), model, None).process_file("CASE", spec(name, fixture_doc(name)), fixture_doc(name))


@pytest.mark.parametrize("name", ALL)
def test_two_fresh_runs_are_byte_identical(cfg, name):
    assert run(cfg, name).model_dump_json() == run(cfg, name).model_dump_json()


def test_concurrent_runs_agree_with_serial_runs(cfg):
    serial = {n: run(cfg, n).model_dump_json() for n in ALL}
    store = Store()
    with ThreadPoolExecutor(6) as ex:
        par = dict(zip(ALL, ex.map(lambda n: run(cfg, n, store).model_dump_json(), ALL)))
    assert par == serial


def test_rerunning_the_same_inputs_replaces_the_run_with_the_same_answer(cfg):
    store = Store()
    a = run(cfg, "Southgate_Entity_PAN.pdf", store)
    b = run(cfg, "Southgate_Entity_PAN.pdf", store)
    assert a.run_id == b.run_id and a.model_dump_json() == b.model_dump_json()
    assert store._q("SELECT count(*) FROM runs")[0][0] == 1 and store._q("SELECT count(*) FROM stage_results")[0][0] == 8


def test_run_id_depends_on_case_bytes_and_configuration(cfg):
    from ingestion.config.loader import load_dir
    from .conftest import CONFIG
    base = run_id_for("C", "a" * 64, cfg)
    assert base == run_id_for("C", "a" * 64, cfg)
    assert base != run_id_for("D", "a" * 64, cfg) and base != run_id_for("C", "b" * 64, cfg) and base != run_id_for("C", "a" * 64, load_dir(CONFIG, version="x"))


def test_the_stage_trace_chains_hashes(cfg):
    r = run(cfg, "Southgate_Certificate_of_Incorporation.pdf")
    t = r.trace
    assert [x.stage for x in t] == ["quality_gate", "read", "route", "classify", "instances", "extract", "validate", "score"]
    assert t[0].input_hash == r.sha256
    assert all(a.output_hash == b.input_hash for a, b in zip(t, t[1:]))


def test_the_result_contains_no_clock_or_timing(cfg):
    text = run(cfg, "Southgate_Entity_PAN.pdf").model_dump_json()
    for needle in ("created_at", "received_at", "duration", '"ms"', "timestamp"):
        assert needle not in text


def test_output_with_a_model_in_replay_equals_output_when_recorded(cfg):
    store = Store()
    rec = ModelClient(FixtureProvider(cfg.llm, model_answers.answerer), "record", store)
    a = run(cfg, "Southgate_Audited_FS_FY2025.pdf", store, rec)
    rep = ModelClient(FixtureProvider(cfg.llm, lambda r: 1 / 0), "replay", store)
    b = run(cfg, "Southgate_Audited_FS_FY2025.pdf", store, rep)
    assert a.model_dump_json() == b.model_dump_json() and rep.calls == 0


def test_config_hash_is_stable_and_order_independent(cfg):
    from ingestion.config.loader import load_dir
    from .conftest import CONFIG, OVERLAY
    assert load_dir(CONFIG, overlay=OVERLAY).hash == cfg.hash
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
