"""Creating a case (docs/functional-requirements.md F-01, F-04.6 to F-04.8).

A case exists only after a person confirms it (F-04.7). Before anything is written the case is checked
against its product (config/app.yaml) and its form (config/intake.yaml, engine/intake_rules.py), the
product's minimum, the sources its values claim, and the duplicate check (F-04.5); the duplicate check
runs again inside the write transaction, so two creates at once cannot both pass it. POST /api/cases
creates a case alone; POST /api/cases/intake creates it with its files, together or not at all.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from . import intake, intake_rules, uploads
from .cases import CaseError, DuplicateCase, find_duplicates, get_case, owners_of
from .config import ProductConfig, branch_for_label, find_user_by_id, load_app_config, option_default, option_ids
from .config import product as product_config
from .contracts import CaseCreate, CaseDetail, CaseSummary, HeaderField, UploadResult
from .db import log_decision, transaction
from .names import similarity
from .store import MESSAGE_FILE_NAME, case_files_dir, cases_dir, data_root
from .util import stable_id

_log = logging.getLogger("creditiq.cases")

#: The case a Registrar stages files for before the case exists (`bind_case` names the real one).
PENDING_CASE = "PENDING"

# Header fields that are the RM's declaration, kept for triangulation (F-04.8, F-19).
DECLARED_FIELDS = ("declared_turnover_inr", "amount_inr", "existing_banking")


class MinimumMissing(CaseError):
    """The product's minimum fields are not all given (F-04.6)."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"missing required fields: {', '.join(missing)}")


class TooFewFiles(CaseError):
    """The one-request create needs at least `min_files` registered files."""

    def __init__(self, min_files: int, registered: int) -> None:
        self.min_files = min_files
        self.registered = registered
        super().__init__(
            f"at least {min_files} document{'s' if min_files != 1 else ''} needed to create the case; "
            f"{registered} received as new documents (system files, refused files and repeats do not count)"
        )


class IdentifierInvalid(CaseError):
    """An identifier is not valid for its box or field."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- The case number ---


def _next_case_id(conn: sqlite3.Connection, root: Path, year: int, prefix: str) -> str:
    """The next case number of the product's prefix: a sequence per prefix and year, so each product counts
    from 1 and the numbers BBG had already issued continue. A number is never reused: one a case holds, or
    whose folder is already in the data root (a leftover), is skipped. The default product's numbers are
    also kept in the one sequence older code reads (case_seq), so it never issues one twice."""
    fmt = load_app_config()["case_id"]["format"]
    row = conn.execute("SELECT last FROM case_seq_prefix WHERE prefix = ? AND year = ?", (prefix, year)).fetchone()
    seq = (row["last"] if row else 0) + 1
    while True:
        case_id = fmt.format(prefix=prefix, year=year, seq=seq)
        held = conn.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone() is not None
        leftover = (cases_dir(root) / case_id).exists()
        if not (held or leftover):
            break
        if leftover and not held:
            _log.warning("case number %s skipped: a folder of that name is already in the data root", case_id)
        seq += 1
    conn.execute("INSERT INTO case_seq_prefix (prefix, year, last) VALUES (?, ?, ?) "
                 "ON CONFLICT(prefix, year) DO UPDATE SET last = excluded.last", (prefix, year, seq))
    if prefix == product_config(None).prefix:
        conn.execute("INSERT INTO case_seq (year, last) VALUES (?, ?) "
                     "ON CONFLICT(year) DO UPDATE SET last = max(last, excluded.last)", (year, seq))
    return case_id


# --- What a case is checked against ---


def _product_of(data: CaseCreate) -> ProductConfig:
    try:
        return product_config(data.product)
    except KeyError:
        raise CaseError(f"unknown product {data.product!r}") from None


def _check_choices(data: CaseCreate, product: ProductConfig) -> None:
    """Every choice is one the product offers (config/app.yaml)."""
    if data.channel not in option_ids("channels"):
        raise CaseError(f"unknown channel {data.channel!r}")
    if data.constitution not in option_ids("constitutions"):
        raise CaseError(f"unknown constitution {data.constitution!r}")
    unknown = set(data.facilities) - option_ids("facilities")
    if unknown:
        raise CaseError(f"unknown facilities {sorted(unknown)}")
    if data.case_type != "unknown" and data.case_type not in product.case_types:
        raise CaseError(f"unknown case type {data.case_type!r} for {product.label}")
    for value, allowed, label in (
        (data.branch, option_ids("branches"), "branch"),
        (data.bank_stage, set(product.stages), "bank stage"),
        (data.customer_type, set(product.customer_types), "customer type"),
        (data.program, set(product.programs), "program"),
    ):
        if value is not None and value not in allowed:
            raise CaseError(f"unknown {label} {value!r} for {product.label}")


def _customer_type_and_constitution(data: CaseCreate, product: ProductConfig) -> CaseCreate:
    """A business's customer type is its constitution: either given fills the other, and the two may not
    disagree. A product whose customers are not constitutions keeps them apart."""
    if not product.constitution_based:
        return data
    known = data.constitution if data.constitution != "unknown" else None
    if data.customer_type is not None and known is not None and data.customer_type != known:
        raise CaseError(f"customer type {data.customer_type!r} and constitution {known!r} disagree")
    return data.model_copy(update={"constitution": known or data.customer_type or "unknown",
                                   "customer_type": data.customer_type or known})


def _context(data: CaseCreate) -> dict:
    """What `show_when` and the holder rules read of the case."""
    return {"customer_type": data.customer_type, "case_type": data.case_type, "constitution": data.constitution}


def _from_rows(data: CaseCreate, product: ProductConfig, name_threshold: float) -> CaseCreate:
    """What the rows already say, for a case that leaves it out: a borrower not named is its primary
    applicant (a loan against property), whose PAN is then the case's too, each recorded in the header with
    where it came from; a borrower named otherwise (a business) takes nothing from the applicant's row. A
    business's facilities and amount come from its facility lines. Never overrides a value given."""
    header = dict(data.header)
    update: dict = {}
    row = intake.primary_row(product, data.groups)
    name = intake.row_value(row, "name") if row is not None else None
    if name and (not data.borrower.strip() or similarity(name, data.borrower) >= name_threshold):
        for column, field in (("borrower", "name"), ("pan", "pan")):
            value = intake.row_value(row, field)
            if value and not (getattr(data, column) or "").strip():
                update[column] = value.upper() if column == "pan" else value
                source = getattr(row.get(field), "source", None)
                header.setdefault(column, HeaderField(value=update[column], proposed=None, source=source or "person"))
    facilities, amount = intake.from_facility_lines(data.groups, facilities=data.facilities, amount_inr=data.amount_inr)
    unknown = set(facilities) - option_ids("facilities")
    if unknown:
        raise CaseError(f"unknown facilities {sorted(unknown)}")
    return data.model_copy(update={**update, "header": header, "facilities": facilities, "amount_inr": amount})


def _case_columns(data: CaseCreate) -> dict[str, str | None]:
    """The case's own columns as the form's fields read them (None for a value not given)."""
    def given(value: object) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    return {
        "borrower": given(data.borrower), "pan": given(data.pan), "gstin": given(data.gstin), "cin": given(data.cin),
        "udyam": given(data.udyam), "application_id": given(data.application_id),
        "customer_id": given(data.customer_id), "amount_inr": given(data.amount_inr or None),
        "tenure_months": given(data.tenure_months), "customer_type": given(data.customer_type),
        "program": given(data.program), "branch": given(data.branch), "bank_stage": given(data.bank_stage),
        "constitution": None if data.constitution == "unknown" else data.constitution,
        "case_type": None if data.case_type == "unknown" else data.case_type,
    }


def _rules(check: Callable, *args):
    """A rule of engine/intake_rules.py, its refusal as the create's own."""
    try:
        return check(*args)
    except intake_rules.IdentifierProblem as e:
        raise IdentifierInvalid(str(e)) from e
    except intake_rules.IntakeError as e:
        raise CaseError(str(e)) from e


def _check_minimum(data: CaseCreate, product: ProductConfig) -> None:
    missing = intake.missing_minimum(
        product, borrower=data.borrower, facilities=data.facilities, amount_inr=data.amount_inr,
        customer_type=data.customer_type, tenure_months=data.tenure_months, groups=data.groups)
    if missing:
        raise MinimumMissing(missing)


def _check_identifiers(data: CaseCreate, product: ProductConfig) -> None:
    """Identifiers held on the case, under the product's rules for each box; a box `show_when` hides for the
    case takes none (the proposal flags them, F-04.4; a create refuses them)."""
    for ident_id, value in (("pan", data.pan), ("gstin", data.gstin), ("cin", data.cin), ("udyam", data.udyam),
                            ("application_id", data.application_id), ("customer_id", data.customer_id)):
        if not (value or "").strip():
            continue
        problem = intake_rules.check_identifier(product, ident_id, value, constitution=data.constitution,
                                                customer_type=data.customer_type, case_type=data.case_type)
        if problem:
            raise IdentifierInvalid(f"{ident_id}: {problem}")


def _check_plain(data: CaseCreate) -> None:
    """The case's own text columns hold no control characters, and its tenure is within the form's limit
    (config/intake.yaml limits.months_max), whatever product asks them."""
    for name in ("borrower", "pan", "gstin", "cin", "udyam", "application_id", "customer_id"):
        value = getattr(data, name)
        if value and intake_rules.has_controls(value):
            raise CaseError(f"{name}: has control characters")
    most = intake.limits()["months_max"]
    if data.tenure_months is not None and data.tenure_months > most:
        raise CaseError(f"tenure_months: months from 1 to {most}")


def _check_sources(data: CaseCreate) -> None:
    """Every value's source is one a create may record (engine/intake.py CREATE_SOURCES): a span of the
    message must point into it; a document's page is the engine's to cite, never a client's to claim."""
    cells = [(name, h) for name, h in data.header.items()] + [
        (f"{section} row {n} {name}", h)
        for section, rows in data.groups.items() for n, row in enumerate(rows, start=1) for name, h in row.items()
    ]
    for name, h in cells:
        problem = intake.create_source_problem(h.source, data.message_text)
        if problem:
            raise CaseError(f"field {name!r}: {problem}")


def _validate(data: CaseCreate, name_threshold: float = 0.85) -> tuple[CaseCreate, ProductConfig]:
    """The case checked against its product and form, in the order the screens report it: the choices, the
    rows and single values of the form, then the product's minimum (MinimumMissing), then the form's own
    rules, the identifiers (IdentifierInvalid) and the sources. Returns the case with its rows cleaned
    (empty rows dropped) and what the rows already say filled in."""
    product = _product_of(data)
    _check_choices(data, product)
    _check_plain(data)
    data = _customer_type_and_constitution(data, product)
    context = _context(data)
    groups = _rules(intake_rules.validate_groups, product, data.groups, context)
    _rules(intake_rules.validate_header, product, data.header, context)
    data = _from_rows(data.model_copy(update={"groups": groups}), product, name_threshold)
    _check_minimum(data, product)
    columns = _case_columns(data)
    _rules(intake_rules.check_case_columns, product, columns, context)
    _rules(intake_rules.check_form_rules, product, columns, data.header, groups, context)
    _check_identifiers(data, product)
    _check_sources(data)
    return data, product


def _clean_id(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _with_defaults(data: CaseCreate, created_by: str) -> CaseCreate:
    """T2.1: fill product and bank stage from their configured defaults and the
    branch from the RM's own, recording each in the header with where it came
    from, so a default is never mistaken for a confirmed value (F-01.2)."""
    header = dict(data.header)
    filled: dict[str, str | None] = {}
    rm_branch = branch_for_label((find_user_by_id(created_by) or {}).get("branch"))
    for name, current, default, source in (
        ("product", data.product, option_default("products"), "default:config"),
        ("bank_stage", data.bank_stage, option_default("bank_stages"), "default:config"),
        ("branch", data.branch, rm_branch, "default:rm"),
    ):
        if current is not None or default is None:
            continue
        filled[name] = default
        if name not in header:
            header[name] = HeaderField(value=default, proposed=default, source=source)
    return data.model_copy(update={
        **filled,
        "application_id": _clean_id(data.application_id),
        "customer_id": _clean_id(data.customer_id),
        "header": header,
    })


# --- The duplicate check (F-04.5) ---


def _duplicates(conn: sqlite3.Connection, data: CaseCreate, name_threshold: float) -> list[CaseSummary]:
    """Existing cases matching the case: its PAN and every PAN its people give, its GSTIN, its application
    ID, its name."""
    return find_duplicates(conn, pan=data.pan, gstin=data.gstin, borrower=data.borrower, name_threshold=name_threshold,
                           application_id=data.application_id,
                           pans=intake.people_pans(_product_of(data), data.groups))


def _raise_duplicates(conn: sqlite3.Connection, found: list[CaseSummary]) -> None:
    raise DuplicateCase(found, owners_of(conn, found))


def prepare_case(
    conn: sqlite3.Connection, data: CaseCreate, *, created_by: str, name_threshold: float = 0.85,
) -> tuple[CaseCreate, list[CaseSummary]]:
    """Everything a create checks before it writes (CaseError, MinimumMissing, IdentifierInvalid,
    DuplicateCase): the case as it will be stored, and the duplicates its override reason covers."""
    data, _ = _validate(data, name_threshold)
    data = _with_defaults(data, created_by)
    duplicates = _duplicates(conn, data, name_threshold)
    if duplicates and not (data.duplicate_override_reason or "").strip():
        _raise_duplicates(conn, duplicates)
    return data, duplicates


def _recheck_duplicates(conn: sqlite3.Connection, data: CaseCreate, covered: list[CaseSummary],
                        name_threshold: float) -> list[CaseSummary]:
    """The duplicate check again, inside the write transaction: a case another create wrote since the first
    check, which no override reason covers, stops this one."""
    found = _duplicates(conn, data, name_threshold)
    seen = {d.id for d in covered} if (data.duplicate_override_reason or "").strip() else set()
    uncovered = [d for d in found if d.id not in seen]
    if uncovered:
        _raise_duplicates(conn, uncovered)
    return found


# --- Writing the case ---


def _creation_detail(data: CaseCreate, config_version: str | None, duplicates: list[CaseSummary]) -> dict:
    """What the decision log keeps of a creation: the case's choices, the duplicates overridden, the
    message's hash, and how many filled fields came from each kind of source (counts only, no values)."""
    return {
        "channel": data.channel, "product": data.product, "case_type": data.case_type,
        "customer_type": data.customer_type, "program": data.program, "application_id": data.application_id,
        "customer_id": data.customer_id, "branch": data.branch, "bank_stage": data.bank_stage,
        "config_version": config_version, "duplicate_override_reason": data.duplicate_override_reason,
        "duplicates": [d.id for d in duplicates],
        "message_sha256": hashlib.sha256(data.message_text.encode("utf-8")).hexdigest()
        if data.message_text is not None else None,
        "fields_by_source": intake.counts_by_source(data.header, data.groups),
        "rows": {s: len(rows) for s, rows in data.groups.items()},
    }


def _case_row(case_id: str, data: CaseCreate, *, created_by: str, now: datetime, config_version: str | None) -> tuple:
    return (
        case_id, data.borrower.strip(), data.constitution, json.dumps(data.facilities), data.amount_inr, data.pan,
        data.gstin, data.cin, data.udyam, int(data.collateral_present), data.channel, now.date().isoformat(),
        created_by, now.isoformat(timespec="seconds"), config_version,
        json.dumps({k: v.model_dump() for k, v in data.header.items()}), data.product, data.case_type,
        data.application_id, data.customer_id, data.branch, data.bank_stage, data.customer_type, data.program,
        data.tenure_months,
        json.dumps({s: [{k: c.model_dump() for k, c in row.items()} for row in rows] for s, rows in data.groups.items()}),
    )


def _store_message(conn: sqlite3.Connection, root: Path, case_id: str, data: CaseCreate, created_by: str, at: str,
                   config_version: str | None) -> None:
    """F-04.8: the pasted message, unchanged, as the case's first document."""
    raw = data.message_text.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    files_dir = case_files_dir(case_id, root)
    for d in (files_dir.parent.parent, files_dir.parent, files_dir):
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(d, 0o700)
    target = files_dir / sha
    if not target.exists():
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
    file_id = stable_id("F", case_id, "message")
    conn.execute(
        """INSERT INTO files (id, case_id, sha256, original_name, archive_path, content_type, size_bytes, channel,
               uploaded_by, uploaded_at, status, stored_name, processed_at)
           VALUES (?, ?, ?, ?, NULL, 'text/plain', ?, ?, ?, ?, 'registered', ?, ?)""",
        (file_id, case_id, sha, MESSAGE_FILE_NAME, len(raw), data.channel, created_by, at, sha, at),
    )
    classification = {"types": ["application_message"], "confidence": 1.0, "exit_tier": "person", "signals": [],
                      "candidates": []}
    conn.execute(
        """INSERT INTO documents (id, case_id, file_id, page_from, page_to, pages, grade, classification, status,
               config_version, doc_key, created_at)
           VALUES (?, ?, ?, 1, 1, ?, 'A', ?, 'accepted', ?, 'message', ?)""",
        (
            stable_id("DOC", case_id, file_id, "message"), case_id, file_id,
            json.dumps([{"n": 1, "route": "text", "grade": "A", "reasons": [], "ocr_confidence": None}]),
            json.dumps(classification), config_version, at,
        ),
    )


def _store_declared(conn: sqlite3.Connection, case_id: str, data: CaseCreate) -> None:
    for name in DECLARED_FIELDS:
        h = data.header.get(name)
        value = h.value if h else None
        if name == "amount_inr" and value is None:
            value = str(data.amount_inr)
        if value is None:
            continue
        conn.execute(
            """INSERT INTO declared_figures (case_id, field, value, proposed, source, basis)
               VALUES (?, ?, ?, ?, ?, 'RM declaration, unverified')""",
            (case_id, name, value, h.proposed if h else None, (h.source if h else None) or "person"),
        )


def _insert_case(
    conn: sqlite3.Connection, root: Path, data: CaseCreate, *, created_by: str, config_version: str | None,
    covered: list[CaseSummary], name_threshold: float, before_files: Callable[[str], None] | None = None,
) -> str:
    """Inside the transaction the caller holds: the duplicate check again, the case number, the case row, its
    creation entry in the decision log, the message as its first document and the declared figures.
    `before_files` runs once the number is known and before anything is written into the case's folder.
    Returns the case number."""
    duplicates = _recheck_duplicates(conn, data, covered, name_threshold)
    now = _now()
    case_id = _next_case_id(conn, root, now.year, _product_of(data).prefix)
    if before_files is not None:
        before_files(case_id)
    conn.execute(
        """INSERT INTO cases (id, borrower, constitution, facilities, amount_inr, pan, gstin, cin, udyam,
               collateral_present, channel, stage, as_of, created_by, created_at, config_version, header,
               product, case_type, application_id, customer_id, branch, bank_stage, customer_type, program,
               tenure_months, intake_groups)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Intake', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        _case_row(case_id, data, created_by=created_by, now=now, config_version=config_version),
    )
    at = now.isoformat(timespec="seconds")
    log_decision(conn, at=at, actor=created_by, case_id=case_id, action="case.created",
                 detail=json.dumps(_creation_detail(data, config_version, duplicates)))
    if data.message_text is not None:
        _store_message(conn, root, case_id, data, created_by, at, config_version)
    _store_declared(conn, case_id, data)
    return case_id


def create_case(
    conn: sqlite3.Connection, data: CaseCreate, *, created_by: str, config_version: str | None,
    root: Path | None = None, name_threshold: float = 0.85,
) -> CaseDetail:
    """POST /api/cases: the case alone (its files are uploaded after)."""
    data, covered = prepare_case(conn, data, created_by=created_by, name_threshold=name_threshold)
    root = Path(root or data_root())
    with transaction(conn):
        case_id = _insert_case(conn, root, data, created_by=created_by, config_version=config_version,
                               covered=covered, name_threshold=name_threshold)
    detail = get_case(conn, case_id)
    assert detail is not None
    return detail


# --- The case with its files ---


def min_files(product: ProductConfig) -> int:
    """The registered files a case of the product needs before it is created (config/intake.yaml)."""
    documents = intake.product_schema(product)["start"]["documents"]
    return documents["min_files"] if documents["required"] else 0


def _stage_files(conn: sqlite3.Connection, root: Path, data: CaseCreate, *, created_by: str, channel: str,
                 parts: list[uploads.SpooledPart], staged: Path) -> uploads.Registrar:
    """The request's files registered into the staging folder, before the case exists; fewer registered
    files than the product needs (system files, refused files and repeats do not count) is TooFewFiles."""
    registrar = uploads.Registrar(conn, root, PENDING_CASE, created_by, channel, files_dir=staged)
    try:
        for part in parts:
            registrar.add_spooled(part)
    finally:
        for part in parts:
            part.path.unlink(missing_ok=True)
    needed = min_files(_product_of(data))
    if registrar.registered < needed:
        raise TooFewFiles(needed, registrar.registered)
    return registrar


def _mover(registrar: uploads.Registrar, root: Path, staged: Path, created: list[Path]) -> Callable[[str], None]:
    """Moves the staged files into the new case's folder once its number is known, noting the folder it
    made so a failure can remove it."""
    def move(case_id: str) -> None:
        target = case_files_dir(case_id, root)
        uploads.secure_dir(target.parent.parent)
        if target.parent.exists():
            raise CaseError(f"the folder for case {case_id} already exists; not overwritten")
        uploads.secure_dir(target.parent)
        created.append(target.parent)
        os.replace(staged, target)
        registrar.bind_case(case_id, target)

    return move


def create_case_with_files(
    conn: sqlite3.Connection, root: Path, data: CaseCreate, *, created_by: str, config_version: str | None,
    name_threshold: float, channel: str, parts: list[uploads.SpooledPart], staging: Path,
) -> tuple[CaseDetail, UploadResult]:
    """POST /api/cases/intake: the case and its files are stored together or not at all (plan 2026-11-27
    section 6). The case is checked first, then its files registered into `staging` (a folder of the data
    root, mode 700, the caller's to remove). Then, in one transaction, the duplicate check runs again, the
    case is numbered, the staged files are moved into its folder, and the case, its files and its
    processing job are written. On any failure the transaction rolls back and the case's folder is
    removed, so no case and no folder remain."""
    data, covered = prepare_case(conn, data, created_by=created_by, name_threshold=name_threshold)
    staged = staging / "files"
    registrar = _stage_files(conn, root, data, created_by=created_by, channel=channel, parts=parts, staged=staged)
    created: list[Path] = []
    try:
        with transaction(conn):
            case_id = _insert_case(conn, root, data, created_by=created_by, config_version=config_version,
                                   covered=covered, name_threshold=name_threshold,
                                   before_files=_mover(registrar, root, staged, created))
            result = registrar.write()
    except BaseException:
        for d in created:
            shutil.rmtree(d, ignore_errors=True)
        raise
    detail = get_case(conn, case_id)
    assert detail is not None
    return detail, result
