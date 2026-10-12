"""RBL's reference record for a case (docs/functional-requirements.md F-25.1, F-25.2).

The delivery team fills the baseline workbook from RBL's own record (or the JSON form, for
tests) and imports it from the command line; an RBL reviewer who did not import it confirms
it. Only the deviations and approving-authority areas are compared yet; the other F-25.1
sheets are accepted and reported as not compared.

Validation is all-or-nothing: a single blocking problem refuses the import and nothing is
stored. No processing module reads what is stored here (.importlinter contract 2).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from . import db, xlsx
from .config import find_user_by_id
from .configstore import reader
from .contracts import (
    ImportProblem,
    ReferenceApproval,
    ReferenceDeviation,
    ReferenceRecord,
    ReferenceRecordImport,
)
from .facts import same_entity
from .store import cases_dir
from .util import now_iso

CASE = "Case"
DEVIATIONS = "Deviations"
AUTHORITY = "Approving authority"
LISTS = "Lists"
DEVIATION_COLUMNS = ["Norm", "Deviation as recorded", "Category", "Value in the record", "Approved by",
                     "Where in the record", "Notes"]
AUTHORITY_COLUMNS = ["Authority as recorded", "Matrix authority", "Decision", "Date", "Where in the record", "Notes"]
CASE_KEYS = ["Appraisal number", "Borrower", "Record date", "Deviations recorded", "Template version"]
NOT_IN_MATRIX = "not_in_matrix"
DECISIONS = ("approved", "declined", "referred")
OTHER_SHEETS = {
    "Classification": ["Document", "Type as recorded", "Where in the record", "Notes"],
    "Key fields": ["Field", "Value as recorded", "Where in the record", "Notes"],
    "Discrepancies": ["Discrepancy", "Area", "Where in the record", "Notes"],
    "Queries": ["Query", "Raised to", "Where in the record", "Notes"],
    "Decision": ["Decision", "Date", "Where in the record", "Notes"],
}
AREAS_NOT_COMPARED = ["classification", "key_fields", "discrepancies", "queries", "decision"]
DATE_COLUMNS = {AUTHORITY: ["Date"]}


class ReferenceError(Exception):
    pass


class NotFound(ReferenceError):
    pass


class Conflict(ReferenceError):
    pass


@dataclass
class Catalogue:
    """What the record's rows may name, from the published configuration."""

    norms: dict[str, tuple[str, str]]   # id -> (label, category)
    categories: dict[str, str]          # key -> label
    authorities: dict[str, tuple[str, int]]  # key -> (label, level)
    version: str

    @classmethod
    def load(cls, root: Path) -> Catalogue:
        policy = reader.load_policy(root)
        ratios = {r.key: r for r in policy.ratios}
        matrix = reader.load_approval_matrix(root)
        return cls(
            norms={n.id: (n.label or (ratios[n.ratio].label if n.ratio in ratios else n.id), n.category)
                   for n in policy.norms},
            categories={c.key: c.label for c in policy.deviation_categories},
            authorities={a.key: (a.label, a.level) for a in matrix.authorities},
            version=reader.published_version(root)["version"],
        )


@dataclass
class Parsed:
    record: ReferenceRecordImport | None
    problems: list[ImportProblem] = field(default_factory=list)
    borrower: str | None = None
    template_version: str | None = None
    rows: dict[str, int | None] = field(default_factory=dict)
    """Workbook rows of the case id ("case"), the deviations flag ("flag") and the approval ("approval")."""


def template(root: Path) -> bytes:
    """The baseline workbook, its Lists sheet filled from the published version."""
    catalogue = Catalogue.load(root)
    lists: list[list] = [["Norm", "Label", "Category", None, "Category", "Label", None, "Authority", "Label", "Level",
                          None, "Decision"]]
    norms = list(catalogue.norms.items())
    categories = list(catalogue.categories.items())
    authorities = [*catalogue.authorities.items(), (NOT_IN_MATRIX, ("Not in the matrix", None))]
    for i in range(max(len(norms), len(categories), len(authorities), len(DECISIONS))):
        row: list = [None] * 12
        if i < len(norms):
            row[0:3] = [norms[i][0], norms[i][1][0], norms[i][1][1]]
        if i < len(categories):
            row[4:6] = list(categories[i])
        if i < len(authorities):
            row[7:10] = [authorities[i][0], authorities[i][1][0], authorities[i][1][1]]
        if i < len(DECISIONS):
            row[11] = DECISIONS[i]
        lists.append(row)
    return xlsx.write_workbook({
        CASE: [["Field", "Value"], ["Appraisal number", None], ["Borrower", None], ["Record date", None],
               ["Deviations recorded", None], ["Template version", catalogue.version]],
        DEVIATIONS: [DEVIATION_COLUMNS],
        AUTHORITY: [AUTHORITY_COLUMNS],
        LISTS: lists,
        **{name: [headers] for name, headers in OTHER_SHEETS.items()},
    }, text_columns={
        DEVIATIONS: range(len(DEVIATION_COLUMNS)),
        AUTHORITY: [i for i, c in enumerate(AUTHORITY_COLUMNS) if c != "Date"],
    })


def _text(value: xlsx.Cell) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return value.strip() or None


def _table(sheets: dict, name: str, columns: list[str], problems: list[ImportProblem]) -> list[tuple[int, dict]]:
    rows = sheets.get(name)
    if rows is None:
        problems.append(ImportProblem(sheet=name, row=None, column=None, message="sheet missing", blocking=True))
        return []
    header = [_text(c) or "" for c in (rows[0] if rows else [])]
    index = {h: i for i, h in enumerate(header)}
    missing = [c for c in columns if c not in index]
    for c in missing:
        problems.append(ImportProblem(sheet=name, row=1, column=c, message="column missing", blocking=True))
    if missing:
        return []
    out = []
    for number, row in enumerate(rows[1:], start=2):
        values = {c: _text(row[index[c]]) if index[c] < len(row) else None for c in columns}
        if any(v is not None for v in values.values()):
            out.append((number, values))
    return out


def _date(value: str | None) -> str | None:
    return xlsx.serial_date(value) if value else None


def parse_workbook(data: bytes) -> Parsed:
    try:
        sheets = xlsx.read_workbook(data, DATE_COLUMNS)
    except xlsx.WorkbookError as e:
        return Parsed(None, [ImportProblem(sheet="workbook", row=None, column=None, message=str(e), blocking=True)])
    problems: list[ImportProblem] = []

    case: dict[str, tuple[int, xlsx.Cell]] = {}
    for number, row in enumerate(sheets.get(CASE, [])[1:], start=2):
        if row and _text(row[0]) in CASE_KEYS:
            case[_text(row[0])] = (number, row[1] if len(row) > 1 else None)
    if CASE not in sheets:
        problems.append(ImportProblem(sheet=CASE, row=None, column=None, message="sheet missing", blocking=True))

    def case_value(key: str) -> tuple[int | None, xlsx.Cell]:
        return case.get(key, (None, None))

    record_row, record_value = case_value("Record date")
    record_date = None
    if record_value is not None:
        record_date = xlsx.serial_date(record_value)
        if record_date is None:
            problems.append(ImportProblem(sheet=CASE, row=record_row, column="Record date",
                                          message=f"not a date: {record_value!r}", blocking=True))
    flag_row, flag = case_value("Deviations recorded")
    flag_text = (_text(flag) or "").lower()
    recorded = {"yes": True, "true": True, "none": False, "no": False, "false": False}.get(flag_text)
    if recorded is None:
        problems.append(ImportProblem(sheet=CASE, row=flag_row, column="Deviations recorded",
                                      message='must be "yes" or "none"', blocking=True))

    deviations = []
    for number, v in _table(sheets, DEVIATIONS, DEVIATION_COLUMNS, problems):
        deviations.append({
            "row": number, "norm_id": v["Norm"], "description": v["Deviation as recorded"] or "",
            "category": v["Category"], "recorded_value": v["Value in the record"],
            "approved_by_text": v["Approved by"], "source_ref": v["Where in the record"] or "", "notes": v["Notes"],
        })
    approvals = []
    for number, v in _table(sheets, AUTHORITY, AUTHORITY_COLUMNS, problems):
        decided_on = v["Date"]
        if decided_on is not None and _date(decided_on) is None:
            problems.append(ImportProblem(sheet=AUTHORITY, row=number, column="Date",
                                          message=f"not a date: {decided_on!r}", blocking=True))
        key = v["Matrix authority"]
        approvals.append((number, {
            "authority_text": v["Authority as recorded"] or "", "authority_key": key,
            "decision": (v["Decision"] or "").lower(), "decided_on": _date(decided_on),
            "source_ref": v["Where in the record"] or "", "notes": v["Notes"],
        }))
    for name, headers in OTHER_SHEETS.items():
        rows = [r for r in sheets.get(name, [])[1:] if any(c not in (None, "") for c in r)]
        if rows:
            problems.append(ImportProblem(sheet=name, row=None, column=None, blocking=False,
                                          message=f"{len(rows)} row(s) not compared yet"))

    raw = {
        "case_id": _text(case_value("Appraisal number")[1]) or "",
        "record_date": record_date,
        "deviations_recorded": bool(recorded),
        "deviations": deviations,
        "approval": approvals,
    }
    return Parsed(
        _build(raw, problems, recorded is not None),
        problems,
        borrower=_text(case_value("Borrower")[1]),
        template_version=_text(case_value("Template version")[1]),
        rows={"case": case_value("Appraisal number")[0], "flag": flag_row,
              "approval": approvals[0][0] if approvals else None},
    )


def _build(raw: dict, problems: list[ImportProblem], flag_ok: bool = True) -> ReferenceRecordImport | None:
    """The record from parsed rows, with each field the model refuses reported at its row."""
    approvals = raw.pop("approval")
    if len(approvals) > 1:
        problems.append(ImportProblem(sheet=AUTHORITY, row=approvals[1][0], column=None,
                                      message="more than one approval row", blocking=True))
    deviations = []
    for d in raw.pop("deviations"):
        try:
            deviations.append(ReferenceDeviation.model_validate(d))
        except ValidationError as e:
            problems += _model_problems(DEVIATIONS, d["row"], e)
    approval = None
    if approvals:
        number, a = approvals[0]
        if a["authority_key"] == NOT_IN_MATRIX:
            a = {**a, "authority_key": None}
        elif a["authority_key"] is None:
            problems.append(ImportProblem(sheet=AUTHORITY, row=number, column="Matrix authority",
                                          message=f"a matrix authority key, or {NOT_IN_MATRIX}", blocking=True))
        try:
            approval = ReferenceApproval.model_validate(a)
        except ValidationError as e:
            problems += _model_problems(AUTHORITY, number, e)
    if not flag_ok:
        return None
    return ReferenceRecordImport(**raw, deviations=deviations, approval=approval)


_COLUMN = {"description": "Deviation as recorded", "source_ref": "Where in the record",
           "authority_text": "Authority as recorded", "decision": "Decision", "norm_id": "Norm"}


def _model_problems(sheet: str, row: int | None, error: ValidationError) -> list[ImportProblem]:
    out = []
    for e in error.errors():
        name = str(e["loc"][0]) if e["loc"] else None
        message = "required" if e["type"] in ("string_too_short", "missing") and name != "authority_text" else e["msg"]
        out.append(ImportProblem(sheet=sheet, row=row, column=_COLUMN.get(name or "", name), message=message,
                                 blocking=True))
    return out


def parse_json(data: bytes) -> Parsed:
    try:
        record = ReferenceRecordImport.model_validate_json(data)
    except ValidationError as e:
        return Parsed(None, [ImportProblem(sheet="JSON", row=None, column=".".join(str(p) for p in x["loc"]) or None,
                                           message=x["msg"], blocking=True) for x in e.errors()])
    if record.approval and record.approval.authority_key == NOT_IN_MATRIX:
        # As in the workbook, whose Lists sheet offers it: an authority the matrix does not name.
        record.approval.authority_key = None
    return Parsed(record)


def validate(record: ReferenceRecordImport, case_id: str, catalogue: Catalogue,
             rows: dict[str, int | None] | None = None) -> list[ImportProblem]:
    """What the configuration refuses in a record, every problem at its sheet, row and column
    (rows: where the workbook holds the case id, the deviations flag and the approval)."""
    rows = rows or {}
    problems: list[ImportProblem] = []
    if record.case_id != case_id:
        problems.append(ImportProblem(sheet=CASE, row=rows.get("case"), column="Appraisal number", blocking=True,
                                      message=f"the record is for {record.case_id or 'no case'!r}, not {case_id!r}"))
    if record.record_date is not None and xlsx.serial_date(record.record_date) != record.record_date:
        problems.append(ImportProblem(sheet=CASE, row=None, column="Record date", blocking=True,
                                      message=f"not a date (YYYY-MM-DD): {record.record_date!r}"))
    if record.approval and record.approval.decided_on is not None \
            and xlsx.serial_date(record.approval.decided_on) != record.approval.decided_on:
        problems.append(ImportProblem(sheet=AUTHORITY, row=rows.get("approval"), column="Date", blocking=True,
                                      message=f"not a date (YYYY-MM-DD): {record.approval.decided_on!r}"))
    keys: dict[str, int] = {}
    seen: dict[str, int] = {}
    for d in record.deviations:
        key = item_key(d)
        if d.norm_id is None and key in keys:
            problems.append(ImportProblem(sheet=DEVIATIONS, row=d.row, column=None, blocking=True,
                                          message=f"row {d.row} is given twice"))
        keys.setdefault(key, d.row)
        if d.norm_id is not None:
            if d.norm_id not in catalogue.norms:
                problems.append(ImportProblem(sheet=DEVIATIONS, row=d.row, column="Norm", blocking=True,
                                              message=f"unknown norm {d.norm_id!r}"))
            elif d.norm_id in seen:
                problems.append(ImportProblem(sheet=DEVIATIONS, row=d.row, column="Norm", blocking=True,
                                              message=f"{d.norm_id} is already on row {seen[d.norm_id]}"))
            seen.setdefault(d.norm_id, d.row)
        if d.category is not None and d.category not in catalogue.categories:
            problems.append(ImportProblem(sheet=DEVIATIONS, row=d.row, column="Category", blocking=True,
                                          message=f"unknown category {d.category!r}"))
    if record.approval and record.approval.authority_key is not None \
            and record.approval.authority_key not in catalogue.authorities:
        problems.append(ImportProblem(sheet=AUTHORITY, row=rows.get("approval"), column="Matrix authority",
                                      blocking=True,
                                      message=f"unknown matrix authority {record.approval.authority_key!r}"))
    if record.deviations_recorded and not record.deviations:
        problems.append(ImportProblem(sheet=CASE, row=rows.get("flag"), column="Deviations recorded", blocking=True,
                                      message='"yes" but no deviation rows'))
    if not record.deviations_recorded and record.deviations:
        problems.append(ImportProblem(sheet=CASE, row=rows.get("flag"), column="Deviations recorded", blocking=True,
                                      message='"none" but the Deviations sheet has rows'))
    return problems


def import_record(conn: sqlite3.Connection, root: Path, case_id: str, path: Path, author: str
                  ) -> tuple[ReferenceRecord | None, list[ImportProblem]]:
    """Validate and store a record. Nothing is stored when any problem blocks."""
    path = Path(path)
    data = path.read_bytes()
    ext = path.suffix.lower()
    if ext not in (".xlsx", ".json"):
        return None, [ImportProblem(sheet="file", row=None, column=None, blocking=True,
                                    message="the record must be an .xlsx workbook or a .json file")]
    if find_user_by_id(author) is None:
        return None, [ImportProblem(sheet="file", row=None, column=None, blocking=True,
                                    message=f"unknown author {author!r}")]
    case = conn.execute("SELECT borrower FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case is None:
        return None, [ImportProblem(sheet=CASE, row=None, column="Appraisal number", blocking=True,
                                    message=f"no case {case_id!r}")]
    catalogue = Catalogue.load(root)
    parsed = parse_workbook(data) if ext == ".xlsx" else parse_json(data)
    problems = list(parsed.problems)
    if parsed.record is not None:
        problems += validate(parsed.record, case_id, catalogue, parsed.rows)
    if parsed.borrower and not same_entity(parsed.borrower, case["borrower"], _noise(root), _name_match(root)):
        problems.append(ImportProblem(sheet=CASE, row=None, column="Borrower", blocking=False,
                                      message=f"the record names {parsed.borrower!r}; the case is {case['borrower']!r}"))
    if parsed.template_version and parsed.template_version != catalogue.version:
        problems.append(ImportProblem(sheet=CASE, row=None, column="Template version", blocking=False,
                                      message=f"the template is from version {parsed.template_version}; "
                                              f"{catalogue.version} is published"))
    if parsed.record is None or any(p.blocking for p in problems):
        return None, problems

    record = parsed.record
    sha = hashlib.sha256(data).hexdigest()
    folder = cases_dir(root) / case_id / "reference"
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{sha}{ext}"
    existed = stored.exists()
    now = now_iso()
    try:
        _store(conn, case_id, path, sha, record, catalogue, author, now, problems)
        stored.write_bytes(data)
    except BaseException:
        if not existed and stored.exists():
            stored.unlink()
        raise
    return load(conn, case_id), problems


def _store(conn: sqlite3.Connection, case_id: str, path: Path, sha: str, record: ReferenceRecordImport,
           catalogue: Catalogue, author: str, now: str, problems: list[ImportProblem]) -> None:
    with db.transaction(conn):
        conn.execute("DELETE FROM reference_items WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM reference_records WHERE case_id = ?", (case_id,))
        conn.execute(
            """INSERT INTO reference_records (case_id, workbook_name, workbook_sha256, record_date, deviations_recorded,
               config_version, imported_by, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, path.name, sha, record.record_date, int(record.deviations_recorded), catalogue.version, author, now),
        )
        for ord_, d in enumerate(record.deviations):
            conn.execute(
                "INSERT INTO reference_items (case_id, area, item_key, data, source_ref, ord) VALUES (?, ?, ?, ?, ?, ?)",
                (case_id, "deviations", item_key(d), d.model_dump_json(), d.source_ref, ord_),
            )
        if record.approval:
            conn.execute(
                "INSERT INTO reference_items (case_id, area, item_key, data, source_ref, ord) VALUES (?, ?, ?, ?, ?, ?)",
                (case_id, "approving_authority", "approval", record.approval.model_dump_json(),
                 record.approval.source_ref, 0),
            )
        db.log_decision(conn, at=now, actor=author, case_id=case_id, action="reference.imported", detail=json.dumps({
            "author": author, "workbook": path.name, "sha256": sha,
            "counts": {"deviations": len(record.deviations), "approving_authority": int(record.approval is not None)},
            "warnings": [p.message for p in problems if not p.blocking],
        }))


def item_key(d: ReferenceDeviation) -> str:
    return d.norm_id or f"REC-{d.row}"


def _noise(root: Path) -> list[str]:
    return [w.lower() for w in reader.load_alignment(root).name_noise_words]


def _name_match(root: Path) -> float:
    tolerances = {t.key: t.value for t in reader.load_tolerances(root).tolerances}
    return tolerances.get("name_match", 0.85)


def _name(user_id: str | None) -> str | None:
    if user_id is None:
        return None
    user = find_user_by_id(user_id)
    return user["name"] if user else user_id


def load(conn: sqlite3.Connection, case_id: str) -> ReferenceRecord | None:
    row = conn.execute("SELECT * FROM reference_records WHERE case_id = ?", (case_id,)).fetchone()
    if row is None:
        return None
    items = conn.execute("SELECT area, data FROM reference_items WHERE case_id = ? ORDER BY area, ord",
                         (case_id,)).fetchall()
    return ReferenceRecord(
        case_id=case_id,
        workbook_name=row["workbook_name"],
        workbook_sha256=row["workbook_sha256"],
        record_date=row["record_date"],
        deviations_recorded=bool(row["deviations_recorded"]),
        imported_by=row["imported_by"],
        imported_at=row["imported_at"],
        confirmed_by=row["confirmed_by"],
        confirmed_by_name=_name(row["confirmed_by"]),
        confirmed_at=row["confirmed_at"],
        config_version=row["config_version"],
        deviations=[ReferenceDeviation.model_validate_json(i["data"]) for i in items if i["area"] == "deviations"],
        approval=next((ReferenceApproval.model_validate_json(i["data"]) for i in items
                       if i["area"] == "approving_authority"), None),
        areas_not_compared=AREAS_NOT_COMPARED,
    )


def confirm(conn: sqlite3.Connection, case_id: str, user: dict) -> ReferenceRecord:
    """The RBL reviewer confirms the record (four eyes: never the person who imported it)."""
    with db.transaction(conn):
        row = conn.execute("SELECT imported_by, confirmed_by FROM reference_records WHERE case_id = ?",
                           (case_id,)).fetchone()
        if row is None:
            raise NotFound("no reference record for this case")
        if row["confirmed_by"] is not None:
            raise Conflict("the reference record is already confirmed")
        if row["imported_by"] == user["id"]:
            raise Conflict("the person who imported the record cannot confirm it")
        now = now_iso()
        conn.execute("UPDATE reference_records SET confirmed_by = ?, confirmed_at = ? WHERE case_id = ?",
                     (user["id"], now, case_id))
        db.log_decision(conn, at=now, actor=user["id"], case_id=case_id, action="reference.confirmed",
                        detail=json.dumps({"sha256": conn.execute(
                            "SELECT workbook_sha256 FROM reference_records WHERE case_id = ?", (case_id,)
                        ).fetchone()[0]}))
    record = load(conn, case_id)
    assert record is not None
    return record


def _problem_line(p: ImportProblem) -> str:
    where = " ".join(x for x in (p.sheet, f"row {p.row}" if p.row else "", p.column or "") if x)
    return f"{'error' if p.blocking else 'warning'}: {where}: {p.message}"


def problem_lines(problems: list[ImportProblem]) -> list[str]:
    return [_problem_line(p) for p in problems]
