import json
import shutil

import pytest
import yaml
from fastapi.testclient import TestClient

from ingestion.api import create_app
from ingestion.contracts import IngestResult
from ingestion.settings import Settings
from ingestion.store import Store

from .conftest import CONFIG, OVERLAY, fixture_doc, spec

N = "Southgate_Certificate_of_Incorporation.pdf"


@pytest.fixture()
def dev_config(tmp_path):
    d = tmp_path / "cfg"
    shutil.copytree(CONFIG, d)
    (d / "routing.yaml").write_text(yaml.safe_dump(_merged()))
    return d


def _merged():
    r = yaml.safe_load((CONFIG / "routing.yaml").read_text())
    r["reading"]["boilerplate"] = yaml.safe_load((OVERLAY / "routing.yaml").read_text())["reading"]["boilerplate"]
    return r


def client(tmp_path, dev_config, key=""):
    s = Settings(tmp_path, dev_config, "127.0.0.1", 0, key, "replay")
    return TestClient(create_app(s, Store()))


def body(name=N, ctype="application/pdf", version="dev"):
    data = fixture_doc(name)
    sp = spec(name, data, ctype)
    return {"request": json.dumps({"case_ref": "CASE-9", "config_version": version, "files": [sp.model_dump()]})}, {"f1": (name, data, ctype)}


def test_ingest_returns_a_valid_contract_and_the_views_work(tmp_path, dev_config):
    c = client(tmp_path, dev_config)
    form, files = body()
    r = c.post("/v1/ingest", data=form, files=files)
    assert r.status_code == 200
    res = IngestResult.model_validate(r.json())
    f = res.files[0]
    assert f.decision == "auto_accept" and f.documents[0].fields["cin"].value == "U17291TZ2016PTC027431"
    assert res.config.version == "dev" and res.contract_version == "2"
    assert [s["stage"] for s in c.get(f"/v1/runs/{f.run_id}/stages").json()][-1] == "score"
    page = c.get(f"/v1/runs/{f.run_id}/pages/1").json()
    assert page["grade"] == "A" and page["lines"][0]["words"]
    assert c.get("/v1/runs", params={"case_ref": "CASE-9"}).json()[0]["id"] == f.run_id
    assert c.get(f"/v1/runs/{f.run_id}").json()["status"] == "processed"
    assert c.get("/v1/runs/nope").status_code == 404 and c.get(f"/v1/runs/{f.run_id}/pages/9").status_code == 404


def test_the_service_gives_the_same_answer_as_the_library(tmp_path, dev_config, cfg):
    from ingestion.config.loader import load_dir
    from ingestion.pipeline import Ingestor
    c = client(tmp_path, dev_config)
    form, files = body()
    api = c.post("/v1/ingest", data=form, files=files).json()["files"][0]
    lib = Ingestor(load_dir(dev_config, version="dev"), Store(), None, None).process_file("CASE-9", spec(N, fixture_doc(N)), fixture_doc(N))
    assert api == json.loads(lib.model_dump_json())


def test_unknown_config_version_is_a_conflict(tmp_path, dev_config):
    form, files = body(version="v404")
    assert client(tmp_path, dev_config).post("/v1/ingest", data=form, files=files).status_code == 409


def test_bad_request_is_a_400(tmp_path, dev_config):
    assert client(tmp_path, dev_config).post("/v1/ingest", data={"request": "{}"}).status_code == 400


def test_api_key_is_required_when_configured(tmp_path, dev_config):
    c = client(tmp_path, dev_config, key="secret")
    form, files = body()
    assert c.post("/v1/ingest", data=form, files=files).status_code == 401
    assert c.post("/v1/ingest", data=form, files=files, headers={"x-api-key": "wrong"}).status_code == 401
    assert c.post("/v1/ingest", data=form, files=files, headers={"x-api-key": "secret"}).status_code == 200
    form, files = body()
    assert c.post("/v1/ingest", data=form, files=files, headers={"authorization": "Bearer secret"}).status_code == 200
    assert c.get("/v1/health").status_code == 200  # liveness needs no key


def test_a_missing_file_part_is_reported_per_file(tmp_path, dev_config):
    form, _ = body()
    r = client(tmp_path, dev_config).post("/v1/ingest", data=form)
    assert r.status_code == 200 and r.json()["files"][0]["reject"]["code"] == "missing_part"


def test_parse_shows_what_the_extractor_will_read(tmp_path, dev_config):
    r = client(tmp_path, dev_config).post("/v1/parse", files={"file": (N, fixture_doc(N), "application/pdf")}).json()
    assert r["grade"] == "A" and "U17291TZ2016PTC027431" in r["pages"][0]["text"]


def test_types_are_listed_read_only(tmp_path, dev_config):
    r = client(tmp_path, dev_config).get("/v1/types").json()
    assert len(r["types"]) == 13 and r["config"]["version"] == "dev"


def test_stream_emits_stage_events_then_the_result(tmp_path, dev_config):
    form, files = body()
    r = client(tmp_path, dev_config).post("/v1/ingest/stream", data=form, files=files)
    events = [l.split(": ", 1)[1] for l in r.text.splitlines() if l.startswith("event:")]
    assert events[0] == "stage" and events[-1] == "result" and events.count("stage") == 8
