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
    """The engine API over a fresh, published data root."""
    monkeypatch.setenv("CREDITIQ_DATA_ROOT", str(published_data_root))
    from engine.api import app

    return TestClient(app)


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
