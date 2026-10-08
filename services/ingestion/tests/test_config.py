import shutil

import pytest
import yaml

from ingestion.config.loader import ConfigError, ConfigStore, load_dir

from .conftest import CONFIG


def test_loads_every_type(cfg):
    # The nine of the PoC's first scope, then the declaration of existing facilities, the sanction
    # letter and the commercial bureau report (test plan TC-20, TC-23).
    assert len(cfg.document_types.documents) == 12
    assert cfg.document_types.by_id()["director_kyc"].schema_.fields[1].name == "din"  # added 6 Oct


def engine_publish(root, src=CONFIG, version="v1"):
    """What the engine's writer does for the ingestion sections: one JSON file per section under the
    version directory, each section's hash in _manifest.json (engine/configstore/writer.py)."""
    import hashlib
    import json
    from ingestion.config.loader import FILES, _read

    d = root / "config_store" / "versions" / version
    d.mkdir(parents=True)
    hashes = {}
    for key, fname in FILES.items():
        data = _read(src / fname)
        (d / f"ingestion.{key}.json").write_text(json.dumps(data, indent=2, sort_keys=True))
        hashes[f"ingestion.{key}"] = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (d / "_manifest.json").write_text(json.dumps({"section_hashes": hashes, "version": version}))
    return d


def test_the_published_version_loads_and_equals_the_authored_directory(tmp_path):
    engine_publish(tmp_path)
    store = ConfigStore(tmp_path)
    assert store.versions() == ["v1"]
    assert store.load("v1").hash == load_dir(CONFIG).hash


def test_a_section_changed_after_publishing_is_refused(tmp_path):
    from ingestion.config import loader

    d = engine_publish(tmp_path)
    (d / "ingestion.quality.json").write_text('{"max_pages": 1}')
    loader._load_published.cache_clear()
    with pytest.raises(ConfigError, match="modified on disk"):
        ConfigStore(tmp_path).load("v1")


def test_an_unknown_version_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="unknown configuration version"):
        ConfigStore(tmp_path).load("nope")


def _edited(tmp_path, fname, fn):
    d = tmp_path / "cfg"
    shutil.copytree(CONFIG, d)
    data = yaml.safe_load((d / fname).read_text())
    fn(data)
    (d / fname).write_text(yaml.safe_dump(data))
    return d


def test_bad_regex_is_rejected_at_load(tmp_path):
    d = _edited(tmp_path, "signals.yaml", lambda x: x["types"]["company_pan"]["required"].append("(unclosed"))
    with pytest.raises(ConfigError, match="bad regex"):
        load_dir(d)


def test_unknown_key_is_rejected(tmp_path):
    d = _edited(tmp_path, "quality.yaml", lambda x: x.update(max_pagez=1))
    with pytest.raises(ConfigError):
        load_dir(d)


def test_field_rule_for_a_field_not_in_the_schema_is_rejected(tmp_path):
    d = _edited(tmp_path, "fields.yaml", lambda x: x["types"]["company_pan"]["fields"].update(nope={"aliases": ["x"]}))
    with pytest.raises(ConfigError, match="not in the type's schema"):
        load_dir(d)


def test_weights_must_sum_to_one(tmp_path):
    d = _edited(tmp_path, "confidence.yaml", lambda x: x["weights"].update(agreement=0.5))
    with pytest.raises(ConfigError, match="sum to 1"):
        load_dir(d)


def test_a_type_without_signals_is_rejected(tmp_path):
    d = _edited(tmp_path, "signals.yaml", lambda x: x["types"].pop("gstr_3b"))
    with pytest.raises(ConfigError, match="no entry for document type gstr_3b"):
        load_dir(d)


def test_threshold_edit_changes_hash_and_behaviour(cfg, tmp_path):
    from ingestion.pipeline import Ingestor
    from ingestion.store import Store
    from .conftest import fixture_doc, spec

    d = _edited(tmp_path, "decision.yaml", lambda x: x.update(accept_min_document_confidence=0.99))
    strict = load_dir(d, overlay=__import__("tests.conftest", fromlist=["OVERLAY"]).OVERLAY)
    assert strict.hash != cfg.hash
    n = "Southgate_Certificate_of_Incorporation.pdf"
    a = Ingestor(cfg, Store(), None, None).process_file("C", spec(n, fixture_doc(n)), fixture_doc(n))
    b = Ingestor(strict, Store(), None, None).process_file("C", spec(n, fixture_doc(n)), fixture_doc(n))
    assert (a.decision, b.decision) == ("auto_accept", "human_review")
