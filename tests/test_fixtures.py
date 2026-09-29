"""AD-6: the canned sidecar results validate against the contract
(contracts/ingest-result.schema.json is generated from IngestResult), and
every synthetic file has its fixture."""

import hashlib
import json
from pathlib import Path

from engine.contracts import IngestResult

HERE = Path(__file__).resolve().parent / "fixtures"


def test_every_ingest_fixture_validates_against_the_contract():
    fixtures = sorted((HERE / "ingest").glob("*.json"))
    assert fixtures
    for path in fixtures:
        IngestResult.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_every_fixture_file_has_a_canned_result():
    for path in sorted((HERE / "files").iterdir()):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert (HERE / "ingest" / f"{sha}.json").is_file(), path.name


def test_the_published_schema_matches_the_model():
    schema = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "ingest-result.schema.json").read_text())
    assert schema == IngestResult.model_json_schema()
