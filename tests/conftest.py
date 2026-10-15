from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.config import load_roles_config
from engine.configstore import writer

RM = "arjun.deshpande@rblbank.com"
ANALYST = "ananya.krishnan@rblbank.com"
MANAGER = "meenal.kulkarni@rblbank.com"


@pytest.fixture(autouse=True)
def strict_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    """A card builder's error fails the test (in service the card falls back to the sides)."""
    from engine import xv_cards

    monkeypatch.setattr(xv_cards, "STRICT", True)


@pytest.fixture()
def all_rules_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every configured cross-check runs, those switched off in config/crosschecks.yaml (`enabled:
    false`) too: for the tests of the switched-off rules, which stay configured so that they can be
    switched back on. Every caller reads the published section through engine.configstore.reader,
    so replacing it there reaches the checks, the board and the PD note alike."""
    from engine.configstore import reader

    published = reader.load_crosschecks

    def every_rule_enabled(data_root: Path):
        section = published(data_root)
        return section.model_copy(update={"rules": [r.model_copy(update={"enabled": True}) for r in section.rules]})

    monkeypatch.setattr(reader, "load_crosschecks", every_rule_enabled)


@pytest.fixture()
def published_data_root(tmp_path: Path) -> Path:
    """A data root with the current authored config published into it."""
    writer.publish(data_root=tmp_path, author="test-fixture", note="test publish")
    return tmp_path


@pytest.fixture()
def client(published_data_root: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The engine API over a fresh, published data root. Jobs run only when
    a test calls run_jobs(); the sidecar is the stub (canned fixtures)."""
    monkeypatch.setenv("CREDITIQ_DATA_ROOT", str(published_data_root))
    monkeypatch.setenv("CREDITIQ_INGEST", "stub")
    monkeypatch.setenv("CREDITIQ_WORKER", "0")
    from engine.api import app

    return TestClient(app)


FIXTURE_FILES = Path(__file__).resolve().parent / "fixtures" / "files"
TEST_AS_OF = "2026-09-29"


def fixture_file(name: str) -> bytes:
    return (FIXTURE_FILES / name).read_bytes()


def case_files(case: str) -> list[tuple[str, bytes]]:
    """The files of a fixture case ("complete" or "partial"): one file per document."""
    import json

    names = json.loads((FIXTURE_FILES.parent / "cases.json").read_text())[case]
    return [(n, fixture_file(n)) for n in names]


def upload(client: TestClient, headers: dict, case_id: str, files: list[tuple[str, bytes]]):
    return client.post(
        f"/api/cases/{case_id}/files",
        files=[("files", (name, data, "application/octet-stream")) for name, data in files],
        headers=headers,
    )


def run_jobs(root: Path) -> int:
    from engine import jobs

    return jobs.run_pending(root)


def set_as_of(root: Path, case_id: str, as_of: str = TEST_AS_OF) -> None:
    """Fix a case's as_of for date-relative fixtures (principle 8: rules
    read the case's as_of, never the wall clock)."""
    from engine import db

    conn = db.connect(root)
    try:
        conn.execute("UPDATE cases SET as_of = ? WHERE id = ?", (as_of, case_id))
    finally:
        conn.close()


def open_assessment(root: Path, case_id: str, actor: str = "ananya-krishnan") -> None:
    """Open the assessment gate directly (F-13), without walking the checklist.

    Cross-verification, the policy checks and the outputs are shut until a person creates the
    case. A test about any of those is not a test of the gate, so it opens it here; the tests
    of the gate itself use `make_case(..., assessment_open=False)` and the endpoint."""
    from datetime import datetime, timezone

    from engine import db

    conn = db.connect(root)
    try:
        conn.execute(
            "UPDATE cases SET assessment_opened_at = ?, assessment_opened_by = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(timespec="milliseconds"), actor, case_id),
        )
        conn.commit()
    finally:
        conn.close()


def make_case(client: TestClient, headers: dict, root: Path, *, assessment_open: bool = True, **overrides) -> str:
    response = client.post("/api/cases", json=new_case(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    case_id = response.json()["id"]
    set_as_of(root, case_id)
    if assessment_open:
        open_assessment(root, case_id)
    return case_id


def sign_in(client: TestClient, email: str) -> dict:
    # The PoC's shared password, as configured (config/roles.yaml).
    password = load_roles_config()["auth"]["demoPassword"]
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def new_case(**overrides) -> dict:
    body = {
        "borrower": "Example Tools Pvt Ltd",
        "constitution": "private_limited",
        "facilities": ["cash_credit", "term_loan"],
        "amount_inr": 65000000,
        "channel": "email",
        "collateral_present": True,
    }
    body.update(overrides)
    return body
