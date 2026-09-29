"""Parallel requests, as the screens send them, never fail (regression:
a request's connection opened in one threadpool thread and used in another
raised sqlite3.ProgrammingError and returned 500)."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, new_case, sign_in


def test_parallel_case_reads_all_succeed(client: TestClient):
    headers = sign_in(client, ANALYST)
    case_id = client.post("/api/cases", json=new_case(), headers=headers).json()["id"]
    paths = [
        "/api/cases",
        f"/api/cases/{case_id}",
        f"/api/cases/{case_id}/checklist",
        f"/api/cases/{case_id}/documents",
        f"/api/cases/{case_id}/files",
        f"/api/cases/{case_id}/queries",
        "/api/review",
        "/api/meta",
    ] * 6

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(lambda p: client.get(p, headers=headers).status_code, paths))

    assert statuses == [200] * len(paths)
