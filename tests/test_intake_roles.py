"""F-03.1 role-by-endpoint matrix for the Wave 1 intake endpoints: 401
without a session, 403 without the permission (config/roles.yaml), and the
permitted roles get through."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import ANALYST, MANAGER, RM, fixture_file, make_case, run_jobs, sign_in

ROLES = {"rm": RM, "analyst": ANALYST, "credit-manager": MANAGER}

# endpoint -> the roles config/roles.yaml grants its permission to.
MATRIX = {
    "propose": {"rm", "analyst"},  # case.create
    "upload": {"rm", "analyst"},  # document.upload
    "page": {"rm", "analyst", "credit-manager"},  # case.read
    "parties": {"rm", "analyst", "credit-manager"},  # case.read
    "decide": {"analyst", "credit-manager"},  # review.decide
}


@pytest.fixture()
def world(client: TestClient, published_data_root):
    """A case of the RM's own (so the RM may read it), processed, with one
    open field review item."""
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Heronbay Polymers Pvt Ltd")
    client.post(
        f"/api/cases/{case_id}/files",
        files=[("files", ("gst_sep_photo.pdf", fixture_file("gst_sep_photo.pdf"), "application/pdf"))],
        headers=rm,
    )
    run_jobs(published_data_root)
    doc = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()[0]
    analyst = sign_in(client, ANALYST)
    items = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json() if i["kind"] == "field"]
    return {"case_id": case_id, "doc_id": doc["id"], "items": items}


def _call(client: TestClient, name: str, world: dict, headers: dict):
    case_id = world["case_id"]
    if name == "propose":
        return client.post("/api/cases/proposals", json={"channel": "email", "text": "CC 50L"}, headers=headers)
    if name == "upload":
        return client.post(
            f"/api/cases/{case_id}/files",
            files=[("files", ("a.csv", b"a,b\n1,2\n", "text/csv"))],
            headers=headers,
        )
    if name == "page":
        return client.get(f"/api/cases/{case_id}/documents/{world['doc_id']}/pages/1", headers=headers)
    if name == "parties":
        return client.get(f"/api/cases/{case_id}/parties", headers=headers)
    if name == "decide":
        item = world["items"][0]
        response = client.post(f"/api/review/{item['id']}/decision", json={"decision": "confirm"}, headers=headers)
        if response.status_code < 400:
            world["items"].pop(0)  # decided: the next permitted role takes the next item
        return response
    raise AssertionError(name)


@pytest.mark.parametrize("endpoint", sorted(MATRIX))
def test_role_matrix(client: TestClient, world: dict, endpoint: str):
    assert _call(client, endpoint, world, {}).status_code == 401
    assert _call(client, endpoint, world, {"Authorization": "Bearer not-a-token"}).status_code == 401
    for role, email in ROLES.items():
        status = _call(client, endpoint, world, sign_in(client, email)).status_code
        if role in MATRIX[endpoint]:
            assert status < 400, f"{role} on {endpoint}: {status}"
        else:
            assert status == 403, f"{role} on {endpoint}: {status}"
