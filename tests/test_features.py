"""A feature switched off in config/app.yaml `features:` (the integrity checks, F-07A): the screens
are told it is off, and the counts they show leave it out; what the engine recorded is kept."""

from pathlib import Path

from fastapi.testclient import TestClient

from engine import db
from engine.review_items import raise_item
from tests.conftest import RM, make_case, sign_in


def _case_with_integrity_item(client: TestClient, root: Path) -> tuple[dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower="Heronbay Polymers Pvt Ltd", facilities=["cash_credit"],
                        amount_inr=30000000, collateral_present=False)
    conn = db.connect(root)
    try:
        with db.transaction(conn):
            raise_item(conn, case_id=case_id, kind="integrity", ref="file:F-TEST", summary="integrity",
                       detail={"file_id": "F-TEST"})
    finally:
        conn.close()
    return rm, case_id


def _open_items(client, headers, case_id) -> int:
    return next(c for c in client.get("/api/cases", headers=headers).json() if c["id"] == case_id)["open_review_items"]


def test_the_screens_are_told_whether_the_integrity_checks_are_on(client: TestClient, features_on: dict):
    rm = sign_in(client, RM)
    assert client.get("/api/meta", headers=rm).json()["features"] == {"integrity_checks": True}
    features_on["integrity_checks"] = False
    assert client.get("/api/meta", headers=rm).json()["features"] == {"integrity_checks": False}


def test_switched_off_their_items_are_not_counted_and_are_kept(client: TestClient, published_data_root: Path,
                                                               features_on: dict):
    rm, case_id = _case_with_integrity_item(client, published_data_root)
    assert _open_items(client, rm, case_id) == 1
    features_on["integrity_checks"] = False
    assert _open_items(client, rm, case_id) == 0
    # Switched back on, the item is there again: nothing was removed.
    features_on["integrity_checks"] = True
    assert _open_items(client, rm, case_id) == 1


def test_the_deployment_file_names_the_switch():
    from engine.config import REPO_ROOT
    import yaml

    cfg = yaml.safe_load((REPO_ROOT / "config" / "app.yaml").read_text(encoding="utf-8"))
    assert "integrity_checks" in cfg["features"]
