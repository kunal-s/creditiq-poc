"""Read-only administration and audit views."""

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, new_case, sign_in


def test_rm_cannot_read_administration_or_audit(client: TestClient):
    rm = sign_in(client, RM)
    for path in ("/api/config/versions", "/api/users", "/api/audit"):
        assert client.get(path, headers=rm).status_code == 403


def test_config_versions_list_the_published_version_as_current(client: TestClient):
    headers = sign_in(client, ANALYST)
    versions = client.get("/api/config/versions", headers=headers).json()
    assert len(versions) == 1
    assert versions[0]["current"] is True
    assert versions[0]["prior_version"] is None
    assert versions[0]["sections_changed"], "the first version changes every section"
    assert versions[0]["version"] == client.get("/api/config/version", headers=headers).json()["version"]


def test_user_directory_has_roles_and_permissions(client: TestClient):
    headers = sign_in(client, ANALYST)
    users = client.get("/api/users", headers=headers).json()
    roles = {u["role"] for u in users}
    assert {"rm", "analyst", "credit-manager"} <= roles
    rm = next(u for u in users if u["role"] == "rm")
    assert "case.create" in rm["permissions"] and "config.read" not in rm["permissions"]


def test_audit_trail_shows_actions_newest_first_and_filters(client: TestClient):
    headers = sign_in(client, ANALYST)
    assert client.post("/api/cases", json=new_case(), headers=headers).status_code in (200, 201)
    page = client.get("/api/audit", headers=headers).json()
    actions = [e["action"] for e in page["entries"]]
    assert "session.signed_in" in actions and "case.created" in actions
    seqs = [e["seq"] for e in page["entries"]]
    assert seqs == sorted(seqs, reverse=True)
    assert page["entries"][0]["actor_name"]
    only = client.get("/api/audit", params={"action": "case.created"}, headers=headers).json()
    assert {e["action"] for e in only["entries"]} == {"case.created"}
    paged = client.get("/api/audit", params={"limit": 1}, headers=headers).json()
    assert len(paged["entries"]) == 1 and paged["next_before"] == paged["entries"][0]["seq"]
