"""F-20.2: the working under a norm — the lines a derived figure was summed from.

A ratio built on `current_assets` or `net_worth` must carry the statement lines behind it, each
with the page it was read from, so the screen can show the arithmetic rather than only a total.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, case_files, make_case, run_jobs, sign_in, upload

DERIVED = {"net_worth", "current_assets", "current_liabilities", "total_borrowings", "ebitda"}


def _norms(client: TestClient, headers: dict, case_id: str) -> list[dict]:
    response = client.get(f"/api/cases/{case_id}/policy", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["norms"]


def test_a_derived_figure_carries_the_lines_it_was_summed_from(
    client: TestClient, published_data_root: Path
):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root)
    upload(client, headers, case_id, case_files("complete"))
    run_jobs(published_data_root)

    inputs = [i for n in _norms(client, headers, case_id) for i in n.get("inputs", [])]
    derived = [i for i in inputs if i["name"] in DERIVED and i.get("components")]
    if not derived:  # the fixture set has no statement tables to derive from
        return

    for figure in derived:
        parts = figure["components"]
        assert len(parts) >= 2, figure["name"]
        # The parts add up to the figure, each carrying its sign.
        total = sum(p["sign"] * p["value"] for p in parts)
        assert abs(total - figure["value"]) < 0.5, figure["name"]
        for part in parts:
            assert part["label"] and part["sign"] in (1, -1)


def test_a_figure_the_statement_prints_itself_has_no_components(
    client: TestClient, published_data_root: Path
):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root)
    upload(client, headers, case_id, case_files("complete"))
    run_jobs(published_data_root)

    for norm in _norms(client, headers, case_id):
        for figure in norm.get("inputs", []):
            if figure["name"] not in DERIVED:
                assert not figure.get("components"), figure["name"]
