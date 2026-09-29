from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.config import load_roles_config
from engine.configstore import writer

RM = "arjun.deshpande@rblbank.com"
ANALYST = "ananya.krishnan@rblbank.com"
MANAGER = "meenal.kulkarni@rblbank.com"


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


def make_case(client: TestClient, headers: dict, root: Path, **overrides) -> str:
    response = client.post("/api/cases", json=new_case(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    case_id = response.json()["id"]
    set_as_of(root, case_id)
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
