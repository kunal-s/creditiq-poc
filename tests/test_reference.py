"""RBL's reference record for a case (FRD F-25.1): import, validation and confirmation."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cli, db, reference, xlsx
from engine.store import cases_dir
from tests.conftest import ANALYST, MANAGER, RM, make_case, sign_in

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "TC-30" / "reference_record.json"
IMPORTER = "ananya-krishnan"   # the analyst, on behalf of the delivery team
REVIEWER = "meenal-kulkarni"   # the RBL reviewer (Credit Manager)


def record_json(case_id: str, **changes) -> dict:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    record["case_id"] = case_id
    record.update(changes)
    return record


def write_json(tmp: Path, record: dict, name: str = "record.json") -> Path:
    path = tmp / name
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def workbook_rows(record: dict, borrower: str | None = "Example Tools Pvt Ltd", version: str | None = None) -> dict:
    deviations = [reference.DEVIATION_COLUMNS]
    by_row = {d["row"]: d for d in record["deviations"]}
    for row in range(2, max(by_row, default=1) + 1):
        d = by_row.get(row)
        deviations.append([d.get("norm_id"), d["description"], d.get("category"), d.get("recorded_value"),
                           d.get("approved_by_text"), d["source_ref"], d.get("notes")] if d else [])
    authority = [reference.AUTHORITY_COLUMNS]
    if record.get("approval"):
        a = record["approval"]
        authority.append([a["authority_text"], a["authority_key"] or "not_in_matrix", a["decision"], a.get("decided_on"),
                          a["source_ref"], a.get("notes")])
    return {
        reference.CASE: [["Field", "Value"], ["Appraisal number", record["case_id"]], ["Borrower", borrower],
                         ["Record date", record.get("record_date")],
                         ["Deviations recorded", "yes" if record["deviations_recorded"] else "none"],
                         ["Template version", version]],
        reference.DEVIATIONS: deviations,
        reference.AUTHORITY: authority,
        **{name: [headers] for name, headers in reference.OTHER_SHEETS.items()},
    }


def write_workbook(tmp: Path, sheets: dict, name: str = "record.xlsx") -> Path:
    path = tmp / name
    path.write_bytes(xlsx.write_workbook(sheets))
    return path


def do_import(root: Path, case_id: str, path: Path, author: str = IMPORTER):
    conn = db.connect(root)
    try:
        return reference.import_record(conn, root, case_id, path, author)
    finally:
        conn.close()


def _rows(root: Path, sql: str, *args) -> list:
    conn = db.connect(root)
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def case_id(client: TestClient, published_data_root: Path) -> str:
    return make_case(client, sign_in(client, ANALYST), published_data_root)


def test_json_and_workbook_imports_store_the_same_items(client, published_data_root: Path, case_id: str, tmp_path: Path):
    record = record_json(case_id)
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, record))
    assert stored is not None and not [p for p in problems if p.blocking]
    from_json = _rows(published_data_root, "SELECT area, item_key, data, source_ref, ord FROM reference_items WHERE case_id = ? ORDER BY area, ord", case_id)
    assert [r["item_key"] for r in from_json if r["area"] == "deviations"] == ["FR-05", "FR-06", "EL-02", "REC-5", "FR-01"]

    stored, problems = do_import(published_data_root, case_id, write_workbook(tmp_path, workbook_rows(record)))
    assert stored is not None, problems
    from_book = _rows(published_data_root, "SELECT area, item_key, data, source_ref, ord FROM reference_items WHERE case_id = ? ORDER BY area, ord", case_id)
    assert from_book == from_json
    assert stored.record_date == "2026-09-30" and stored.deviations_recorded and stored.approval.decided_on == "2026-10-02"
    assert stored.areas_not_compared == reference.AREAS_NOT_COMPARED

    logs = _rows(published_data_root, "SELECT actor, detail FROM decision_log WHERE case_id = ? AND action = 'reference.imported'", case_id)
    assert len(logs) == 2
    detail = json.loads(logs[-1]["detail"])
    assert logs[-1]["actor"] == IMPORTER and detail["sha256"] == stored.workbook_sha256
    assert detail["counts"] == {"deviations": 5, "approving_authority": 1}
    assert (cases_dir(published_data_root) / case_id / "reference" / f"{stored.workbook_sha256}.xlsx").is_file()


def test_date_serials_are_read_in_the_workbook(client, published_data_root: Path, case_id: str, tmp_path: Path):
    sheets = workbook_rows(record_json(case_id))
    sheets[reference.CASE][3][1] = 46295.0   # 2026-09-30
    sheets[reference.AUTHORITY][1][3] = 46297.0
    stored, problems = do_import(published_data_root, case_id, write_workbook(tmp_path, sheets))
    assert stored is not None, problems
    assert stored.record_date == "2026-09-30" and stored.approval.decided_on == "2026-10-02"


def _broken(case_id: str, kind: str) -> tuple[dict, dict]:
    record = record_json(case_id)
    sheets = workbook_rows(record)
    if kind == "unknown_norm":
        sheets[reference.DEVIATIONS][1][0] = "FR-99"
    elif kind == "unknown_category":
        sheets[reference.DEVIATIONS][1][2] = "pricing"
    elif kind == "unknown_key":
        sheets[reference.AUTHORITY][1][1] = "branch_head"
    elif kind == "duplicate_norm":
        sheets[reference.DEVIATIONS][2][0] = "FR-05"
    elif kind == "no_source":
        sheets[reference.DEVIATIONS][1][5] = None
    elif kind == "two_approvals":
        sheets[reference.AUTHORITY].append(list(sheets[reference.AUTHORITY][1]))
    elif kind == "wrong_case":
        sheets[reference.CASE][1][1] = "CIQ-OTHER"
    elif kind == "none_with_rows":
        sheets[reference.CASE][4][1] = "none"
    elif kind == "yes_without_rows":
        sheets[reference.DEVIATIONS] = [reference.DEVIATION_COLUMNS]
    elif kind == "bad_date":
        sheets[reference.AUTHORITY][1][3] = "next tuesday"
    elif kind == "bad_decision":
        sheets[reference.AUTHORITY][1][2] = "maybe"
    elif kind == "approval_on_row_3":
        row = list(sheets[reference.AUTHORITY][1])
        row[1] = "branch_head"
        sheets[reference.AUTHORITY][1:] = [[], row]
    return record, sheets


@pytest.mark.parametrize("kind,sheet,row,column", [
    ("unknown_norm", "Deviations", 2, "Norm"),
    ("unknown_category", "Deviations", 2, "Category"),
    ("unknown_key", "Approving authority", 2, "Matrix authority"),
    ("duplicate_norm", "Deviations", 3, "Norm"),
    ("no_source", "Deviations", 2, "Where in the record"),
    ("two_approvals", "Approving authority", 3, None),
    ("wrong_case", "Case", 2, "Appraisal number"),
    ("none_with_rows", "Case", 5, "Deviations recorded"),
    ("yes_without_rows", "Case", 5, "Deviations recorded"),
    ("approval_on_row_3", "Approving authority", 3, "Matrix authority"),
    ("bad_date", "Approving authority", 2, "Date"),
    ("bad_decision", "Approving authority", 2, "Decision"),
])
def test_each_problem_is_refused_at_its_cell_and_nothing_is_stored(client, published_data_root: Path, case_id: str,
                                                                  tmp_path: Path, kind, sheet, row, column):
    _, sheets = _broken(case_id, kind)
    stored, problems = do_import(published_data_root, case_id, write_workbook(tmp_path, sheets))
    assert stored is None
    blocking = [p for p in problems if p.blocking]
    assert any((p.sheet, p.row, p.column) == (sheet, row, column) for p in blocking), blocking
    assert _rows(published_data_root, "SELECT * FROM reference_records WHERE case_id = ?", case_id) == []
    assert _rows(published_data_root, "SELECT * FROM reference_items WHERE case_id = ?", case_id) == []


def test_json_problems_are_refused_too(client, published_data_root: Path, case_id: str, tmp_path: Path):
    record = record_json(case_id)
    record["deviations"][0]["norm_id"] = "FR-99"
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, record))
    assert stored is None and any(p.column == "Norm" and "FR-99" in p.message for p in problems)
    bad = record_json(case_id)
    del bad["deviations_recorded"]
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, bad))
    assert stored is None and problems[0].sheet == "JSON"


def test_a_borrower_mismatch_and_another_version_only_warn(client, published_data_root: Path, case_id: str, tmp_path: Path):
    sheets = workbook_rows(record_json(case_id), borrower="Larkspur Castings Ltd", version="v-older")
    stored, problems = do_import(published_data_root, case_id, write_workbook(tmp_path, sheets))
    assert stored is not None
    warnings = [p for p in problems if not p.blocking]
    assert {p.column for p in warnings} == {"Borrower", "Template version"}
    same = workbook_rows(record_json(case_id), borrower="EXAMPLE TOOLS PRIVATE LIMITED")
    assert not [p for p in do_import(published_data_root, case_id, write_workbook(tmp_path, same))[1] if p.column == "Borrower"]


def test_rows_in_other_areas_are_reported_not_compared(client, published_data_root: Path, case_id: str, tmp_path: Path):
    sheets = workbook_rows(record_json(case_id))
    sheets["Queries"].append(["Explain the stock statement gap", "Borrower", "CAM p.20", None])
    stored, problems = do_import(published_data_root, case_id, write_workbook(tmp_path, sheets))
    assert stored is not None
    assert any(p.sheet == "Queries" and not p.blocking and "not compared yet" in p.message for p in problems)


def test_a_reimport_replaces_the_items_and_clears_confirmation(client, published_data_root: Path, case_id: str, tmp_path: Path):
    do_import(published_data_root, case_id, write_json(tmp_path, record_json(case_id)))
    manager = sign_in(client, MANAGER)
    assert client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager).status_code == 200
    shorter = record_json(case_id)
    shorter["deviations"] = shorter["deviations"][:2]
    stored, _ = do_import(published_data_root, case_id, write_json(tmp_path, shorter, "second.json"))
    assert [d.norm_id for d in stored.deviations] == ["FR-05", "FR-06"]
    assert stored.confirmed_by is None and stored.confirmed_at is None


def test_the_reviewer_confirms_and_it_is_logged(client, published_data_root: Path, case_id: str, tmp_path: Path):
    do_import(published_data_root, case_id, write_json(tmp_path, record_json(case_id)))
    manager = sign_in(client, MANAGER)
    response = client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confirmed_by"] == REVIEWER and body["confirmed_by_name"] == "Meenal Kulkarni" and body["confirmed_at"]
    assert _rows(published_data_root, "SELECT actor FROM decision_log WHERE case_id = ? AND action = 'reference.confirmed'",
                 case_id) == [{"actor": REVIEWER}]
    assert client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager).status_code == 409


def test_the_importer_cannot_confirm(client, published_data_root: Path, case_id: str, tmp_path: Path):
    do_import(published_data_root, case_id, write_json(tmp_path, record_json(case_id)), author=REVIEWER)
    manager = sign_in(client, MANAGER)
    response = client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager)
    assert response.status_code == 409 and "imported" in response.json()["detail"]


def test_confirm_needs_a_record_and_the_permission(client, published_data_root: Path, case_id: str, tmp_path: Path):
    manager = sign_in(client, MANAGER)
    assert client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager).status_code == 404
    do_import(published_data_root, case_id, write_json(tmp_path, record_json(case_id)))
    for email in (RM, ANALYST):
        assert client.post(f"/api/cases/{case_id}/reference/confirm", headers=sign_in(client, email)).status_code == 403


def test_an_unknown_author_or_file_type_is_refused(client, published_data_root: Path, case_id: str, tmp_path: Path):
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, record_json(case_id)), author="nobody")
    assert stored is None and "unknown author" in problems[0].message
    text = tmp_path / "record.txt"
    text.write_text("x", encoding="utf-8")
    assert do_import(published_data_root, case_id, text)[0] is None


def test_cli_import_and_show(client, published_data_root: Path, case_id: str, tmp_path: Path, capsys):
    good = write_json(tmp_path, record_json(case_id))
    root = str(published_data_root)
    assert cli.main(["reference", "import", case_id, str(good), "--author", IMPORTER, "--data-root", root]) == 0
    assert "5 deviation row(s)" in capsys.readouterr().out
    bad = record_json(case_id)
    bad["deviations"][0]["norm_id"] = "FR-99"
    assert cli.main(["reference", "import", case_id, str(write_json(tmp_path, bad, "bad.json")),
                     "--author", IMPORTER, "--data-root", root]) == 1
    err = capsys.readouterr().err
    assert "unknown norm 'FR-99'" in err and "nothing was stored" in err
    assert cli.main(["reference", "show", case_id, "--data-root", root]) == 0
    assert json.loads(capsys.readouterr().out)["case_id"] == case_id


def test_cli_template_writes_the_workbook(published_data_root: Path, tmp_path: Path):
    out = tmp_path / "baseline.xlsx"
    assert cli.main(["reference", "template", "--out", str(out), "--data-root", str(published_data_root)]) == 0
    assert reference.DEVIATIONS in xlsx.read_workbook(out.read_bytes())


def test_json_rows_given_twice_are_refused_and_nothing_is_left_behind(client, published_data_root: Path, case_id: str,
                                                                    tmp_path: Path):
    record = record_json(case_id)
    record["deviations"].append({**record["deviations"][3], "description": "Tenor above the norm"})  # row 5 again
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, record))
    assert stored is None
    assert any(p.blocking and p.sheet == "Deviations" and p.row == 5 and "twice" in p.message for p in problems)
    assert _rows(published_data_root, "SELECT * FROM reference_items WHERE case_id = ?", case_id) == []
    folder = cases_dir(published_data_root) / case_id / "reference"
    assert not folder.exists() or not any(folder.iterdir())


def test_json_takes_not_in_matrix_as_the_workbook_does(client, published_data_root: Path, case_id: str, tmp_path: Path):
    record = record_json(case_id)
    record["approval"]["authority_key"] = reference.NOT_IN_MATRIX   # as the template's Lists sheet offers it
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, record))
    assert stored is not None, problems
    assert stored.approval.authority_key is None
    sheets = workbook_rows(record_json(case_id))
    sheets[reference.AUTHORITY][1][1] = reference.NOT_IN_MATRIX
    from_book, problems = do_import(published_data_root, case_id, write_workbook(tmp_path, sheets))
    assert from_book is not None, problems
    assert from_book.approval == stored.approval


def test_json_dates_are_checked_too(client, published_data_root: Path, case_id: str, tmp_path: Path):
    record = record_json(case_id, record_date="next tuesday")
    record["approval"]["decided_on"] = "sometime in October"
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, record))
    assert stored is None
    assert {(p.sheet, p.column) for p in problems if p.blocking} >= {("Case", "Record date"),
                                                                      ("Approving authority", "Date")}


def test_a_failed_store_leaves_no_file(client, published_data_root: Path, case_id: str, tmp_path: Path, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(reference, "_store", broken)
    with pytest.raises(RuntimeError):
        do_import(published_data_root, case_id, write_json(tmp_path, record_json(case_id)))
    folder = cases_dir(published_data_root) / case_id / "reference"
    assert not folder.exists() or not any(folder.iterdir())


def test_the_template_keeps_free_text_as_typed(published_data_root: Path):
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(reference.template(published_data_root))) as z:
        names = {n: z.read(n).decode() for n in z.namelist()}
    workbook = names["xl/workbook.xml"]
    order = [m for m in __import__("re").findall(r'<sheet name="([^"]+)"', workbook)]
    deviations = names[f"xl/worksheets/sheet{order.index(reference.DEVIATIONS) + 1}.xml"]
    authority = names[f"xl/worksheets/sheet{order.index(reference.AUTHORITY) + 1}.xml"]
    assert deviations.count('style="2"') == len(reference.DEVIATION_COLUMNS)
    # The date column stays a date column.
    assert authority.count('style="2"') == len(reference.AUTHORITY_COLUMNS) - 1
    assert 'numFmtId="49"' in names["xl/styles.xml"]


def test_the_analyst_sees_that_the_record_was_imported_never_what_it_says(client, published_data_root: Path,
                                                                         case_id: str, tmp_path: Path):
    do_import(published_data_root, case_id, write_json(tmp_path, record_json(case_id)))
    manager = sign_in(client, MANAGER)
    assert client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager).status_code == 200

    def entries(email: str) -> dict:
        page = client.get(f"/api/audit?case_id={case_id}", headers=sign_in(client, email)).json()
        return {e["action"]: e["detail"] for e in page["entries"]}

    analyst = entries(ANALYST)
    assert analyst["reference.imported"] == {} and analyst["reference.confirmed"] == {}
    reviewer = entries(MANAGER)
    assert reviewer["reference.imported"]["counts"] == {"deviations": 5, "approving_authority": 1}
