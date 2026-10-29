"""The golden set replays from recorded model answers: no key, no network, the same outcome every run."""

import json

import pytest

from copilot.config import load_dir
from copilot.store import Store
from tests import golden

CFG = load_dir(golden.ROOT / "config")
SPEC = golden.load()
ALL = [(cases.stem, case) for cases, _ in golden.SETS for case in golden.load(cases)["cases"]]


@pytest.mark.parametrize("name,case", ALL, ids=lambda v: v if isinstance(v, str) else v["id"])
async def test_case_behaves_as_expected(name, case, monkeypatch):
    monkeypatch.delenv(CFG.llm.api_key_env, raising=False)
    cases_file, recordings_file = next(s for s in golden.SETS if s[0].stem == name)
    spec = golden.load(cases_file)
    store = Store(":memory:")
    for r in json.loads(recordings_file.read_text()):
        store.put_llm_call(r["request_key"], r["model"], golden.NOW(), r["request"], r["response"])
    try:
        res, trace = await golden.run_case(CFG, spec, case, store, "replay")
    except Exception as e:
        pytest.fail(f"{type(e).__name__}: {e}. A prompt, example or tool description changed? Re-record: scripts/record_golden.py --write")
    assert golden.problems(CFG, case, res, trace) == []


def test_every_use_case_has_positive_cases_and_every_expectation_names_a_real_use_case():
    covered = {c["expect"].get("use_case") for c in SPEC["cases"] if c["expect"]["terminal"] in ("answer", "confirm")}
    assert {u.id for u in CFG.registry.use_cases} <= covered
    named = {c["expect"]["use_case"] for c in SPEC["cases"] if c["expect"].get("use_case")}
    assert named <= {u.id for u in CFG.registry.use_cases}
    assert len({c["id"] for c in SPEC["cases"]}) == len(SPEC["cases"])
