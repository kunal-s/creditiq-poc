import json

import pytest

from ingestion.llm import provider as P
from ingestion.llm.openai import FixtureProvider, OpenAIProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.store import Store

from . import model_answers
from .conftest import fixture_doc, spec, values

BR = "Southgate_Board_Resolution_draft.pdf"
FS = "Southgate_Audited_FS_FY2025.pdf"
PROV = "Southgate_Provisional_FY2026.pdf"


def run(cfg, store, mode, name, answerer=model_answers.answerer):
    client = ModelClient(FixtureProvider(cfg.llm, answerer), mode, store)
    r = Ingestor(cfg, store, client, None).process_file("C", spec(name, fixture_doc(name)), fixture_doc(name))
    return r, client


def test_model_fills_only_what_the_page_pattern_pass_left_empty(cfg):
    r, client = run(cfg, Store(), "record", BR)
    d = r.documents[0]
    assert d.fields["authorized_signatories"].method == "model" and d.fields["authorized_signatories"].value == ["Lakshmi Iyer", "Venkat Iyer"]
    assert d.fields["authorized_signatories"].source.page == 1 and d.fields["authorized_signatories"].source.bbox
    assert d.fields["borrowing_limit"].method == "pattern"          # not re-read by the model
    assert d.fields["purpose_of_borrowing"].status == "missing"      # the model said it is not stated
    assert d.fields["resolution_date"].status == "missing"           # no derivation: stays missing
    assert client.calls == 1


def test_a_value_the_model_invents_is_rejected_on_the_page(cfg):
    model_answers.HALLUCINATE["purpose_of_borrowing"] = "To fund the purchase of a yacht"
    try:
        r, _ = run(cfg, Store(), "record", BR)
    finally:
        model_answers.HALLUCINATE.clear()
    f = r.documents[0].fields["purpose_of_borrowing"]
    assert f.status == "missing" and f.reason == "not_found_on_page" and f.value is None


def test_record_then_replay_is_identical_and_makes_no_live_call(cfg):
    store = Store()
    first, c1 = run(cfg, store, "record", FS)
    rec = store.get_llm_call(next(iter(k for (k,) in store._q("SELECT key FROM llm_calls"))))
    assert rec["origin"] == "fixture" and rec["task"] == "extract"

    def boom(_):
        raise AssertionError("a live call was made during replay")

    second, c2 = run(cfg, store, "replay", FS, answerer=boom)
    assert c2.calls == 0
    assert first.model_dump_json() == second.model_dump_json()
    assert first.documents[0].fields["accounting_standard"].method == "model"


def test_replay_miss_is_an_explicit_error_not_a_guess(cfg):
    r, _ = run(cfg, Store(), "replay", FS)
    f = r.documents[0].fields["accounting_standard"]
    assert f.status == "missing" and f.reason == "model_unavailable:replay_miss"
    r2, _ = run(cfg, Store(), "replay", PROV)
    assert r2.classification.type is None and "replay_miss" in r2.classification.reason and r2.classification.model_error == "replay_miss"
    assert r2.decision == "human_review"


def test_tier2_classification_can_say_none_of_these(cfg):
    r, _ = run(cfg, Store(), "record", PROV)
    c = r.classification
    assert c.type is None and c.tier == "none" and c.reason.startswith("the model found none of the listed types")


def test_requests_carry_exactly_the_configured_sampling_parameters(cfg):
    assert (cfg.llm.temperature, cfg.llm.seed) == (0, 1)
    store = Store()
    run(cfg, store, "record", FS)
    for (k,) in store._q("SELECT key FROM llm_calls"):
        body = store.get_llm_call(k)["request"]
        P.assert_sampling(body, {"temperature": 0, "seed": 1})
        assert body["temperature"] == 0 and body["seed"] == 1
        assert body["response_format"]["json_schema"]["strict"] is True


def test_a_sampling_parameter_that_is_not_configured_is_refused():
    with pytest.raises(ValueError, match="top_p"):
        P.assert_sampling({"model": "x", "top_p": 0.2}, {"temperature": 0, "seed": 1})
    with pytest.raises(ValueError, match="temperature"):
        P.assert_sampling({"model": "x", "temperature": 0.7}, {"temperature": 0})   # a value other than the configured one
    with pytest.raises(ValueError, match="temperature"):
        P.assert_sampling({"model": "x", "temperature": 0})                          # none configured
    P.assert_sampling({"model": "x", "temperature": 0}, {"temperature": 0})


def test_the_client_refuses_a_provider_that_sends_more_than_it_declares(cfg):
    class Sneaky(FixtureProvider):
        def build(self, req):
            call = super().build(req)
            call.body["top_p"] = 0.1
            return call

    client = ModelClient(Sneaky(cfg.llm, model_answers.answerer), "record", Store())
    with pytest.raises(ValueError, match="top_p"):
        client.call(P.ModelRequest("classify", "s", "u", {"type": "object"}))


def test_sampling_is_omitted_when_not_configured(cfg):
    plain = cfg.model_copy(deep=True)
    plain.llm.temperature = plain.llm.seed = None
    body = OpenAIProvider(plain.llm, "k").build(P.ModelRequest("classify", "s", "u", {"type": "object"})).body
    assert "temperature" not in body and "seed" not in body


def test_the_model_is_swappable_without_touching_the_pipeline(cfg):
    class AcmeProvider:
        """A different vendor: its own body shape and reply shape."""
        name, model = "acme", "acme-small"

        def build(self, req):
            body = {"prompt": req.system + "\n" + req.user, "schema": req.schema}
            return P.NativeCall(body, lambda b: {"out": json.dumps(model_answers.answerer(req))}, lambda resp: json.loads(resp["out"]))

    store = Store()
    client = ModelClient(AcmeProvider(), "record", store)
    r = Ingestor(cfg, store, client, None).process_file("C", spec(BR, fixture_doc(BR)), fixture_doc(BR))
    assert values(r.documents[0])["authorized_signatories"] == ["Lakshmi Iyer", "Venkat Iyer"]
    assert r.documents[0].fields["authorized_signatories"].method == "model"
    assert client.name == "acme:acme-small"


def test_openai_adapter_builds_a_strict_schema_request_and_handles_a_refusal(cfg):
    p = OpenAIProvider(cfg.llm, "k")
    call = p.build(P.ModelRequest("classify", "s", "u", {"type": "object"}))
    assert call.body["model"] == cfg.llm.model and set(call.body) == {"model", "messages", "response_format", "temperature", "seed"}
    with pytest.raises(P.ModelError) as e:
        call.parse({"choices": [{"message": {"refusal": "no"}}]})
    assert e.value.code == "refusal"
    assert call.parse({"choices": [{"message": {"content": "{\"type\": \"x\"}"}}]}) == {"type": "x"}
    with pytest.raises(P.ModelError) as e:
        OpenAIProvider(cfg.llm, None)._send({})
    assert e.value.code == "not_configured"
