"""SQLite store under the data root (docs/functional-requirements.md AD-3).

One file, `<data root>/creditiq.sqlite3`. Schema changes are appended to
MIGRATIONS and never edited once committed; `PRAGMA user_version` records
how many have run. Nested structures (pages, classification, sides) are
JSON text columns, validated by the engine/contracts models on read.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .store import data_root

MIGRATIONS: list[str] = [
    # 1: the Wave 0 schema.
    """
    CREATE TABLE cases (
        id TEXT PRIMARY KEY,
        borrower TEXT NOT NULL,
        constitution TEXT NOT NULL,
        facilities TEXT NOT NULL,          -- JSON list of facility ids
        amount_inr INTEGER NOT NULL,
        pan TEXT, gstin TEXT, cin TEXT, udyam TEXT,
        collateral_present INTEGER NOT NULL DEFAULT 0,
        channel TEXT NOT NULL,
        stage TEXT NOT NULL,
        as_of TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        config_version TEXT,
        header TEXT NOT NULL DEFAULT '{}'  -- JSON {field: HeaderField}
    );
    CREATE TABLE case_seq (year INTEGER PRIMARY KEY, last INTEGER NOT NULL);

    CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_seen TEXT NOT NULL
    );

    CREATE TABLE files (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        sha256 TEXT NOT NULL,
        original_name TEXT NOT NULL,
        archive_path TEXT,
        content_type TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        channel TEXT NOT NULL,
        uploaded_by TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        status TEXT NOT NULL,
        reason TEXT,
        duplicate_of TEXT,
        label_hint TEXT
    );
    CREATE INDEX files_case ON files(case_id);
    CREATE INDEX files_sha ON files(case_id, sha256);

    CREATE TABLE documents (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        file_id TEXT NOT NULL REFERENCES files(id),
        page_from INTEGER NOT NULL,
        page_to INTEGER NOT NULL,
        pages TEXT NOT NULL,               -- JSON list of PageInfo
        grade TEXT NOT NULL,
        classification TEXT,               -- JSON Classification
        status TEXT NOT NULL,
        instance_key TEXT,
        party_id TEXT,
        version_of TEXT,
        duplicate_of TEXT,
        label_mismatch INTEGER NOT NULL DEFAULT 0,
        config_version TEXT
    );
    CREATE INDEX documents_case ON documents(case_id);

    CREATE TABLE field_values (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        document_id TEXT NOT NULL REFERENCES documents(id),
        field TEXT NOT NULL,
        value TEXT,                        -- JSON scalar
        raw TEXT,
        evidence TEXT,                     -- JSON Evidence
        method TEXT NOT NULL,
        confidence REAL,
        confidence_components TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL,
        missing_reason TEXT,
        corrected_value TEXT               -- JSON scalar
    );
    CREATE INDEX field_values_doc ON field_values(document_id);
    CREATE INDEX field_values_case ON field_values(case_id);

    CREATE TABLE findings (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        rule_id TEXT NOT NULL,
        title TEXT NOT NULL,
        outcome TEXT NOT NULL,
        severity TEXT NOT NULL,
        blocking INTEGER NOT NULL,
        explanation TEXT NOT NULL,
        sides TEXT NOT NULL,               -- JSON list of FindingSide
        tolerance TEXT,
        config_version TEXT,
        run_id TEXT
    );
    CREATE INDEX findings_case ON findings(case_id);

    CREATE TABLE query_items (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        grp TEXT NOT NULL,
        text TEXT NOT NULL,
        source_kind TEXT NOT NULL,
        source_ref TEXT NOT NULL,
        evidence TEXT NOT NULL DEFAULT '[]',
        resolved INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX query_items_case ON query_items(case_id);

    CREATE TABLE review_items (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        kind TEXT NOT NULL,
        ref TEXT NOT NULL,
        summary TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        decision TEXT,
        reason TEXT,
        decided_by TEXT,
        decided_at TEXT,
        maker TEXT,
        CHECK (maker IS NULL OR decided_by IS NULL OR maker <> decided_by)
    );
    CREATE INDEX review_items_open ON review_items(status, case_id);

    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL,              -- queued | running | done | failed
        attempts INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT
    );
    CREATE INDEX jobs_status ON jobs(status, created_at);

    CREATE TABLE stage_timings (
        case_id TEXT NOT NULL REFERENCES cases(id),
        subject TEXT NOT NULL,             -- file or document id
        stage TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ms INTEGER NOT NULL
    );
    CREATE INDEX stage_timings_case ON stage_timings(case_id);

    -- Append-only decision log (F-02.5). No UPDATE or DELETE is ever issued.
    CREATE TABLE decision_log (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT NOT NULL,
        actor TEXT NOT NULL,
        case_id TEXT,
        action TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TRIGGER decision_log_no_update BEFORE UPDATE ON decision_log
        BEGIN SELECT RAISE(ABORT, 'decision_log is append-only'); END;
    CREATE TRIGGER decision_log_no_delete BEFORE DELETE ON decision_log
        BEGIN SELECT RAISE(ABORT, 'decision_log is append-only'); END;
    """,
    # 2: Wave 1 intake and completeness (F-02, F-04, F-05, F-10, F-13, F-17).
    """
    ALTER TABLE files ADD COLUMN stored_name TEXT;      -- generated name under cases/<id>/files/
    ALTER TABLE files ADD COLUMN processed_at TEXT;     -- set once the sidecar result is stored
    ALTER TABLE files ADD COLUMN reason_code TEXT;      -- quality reason code for exceptions

    ALTER TABLE documents ADD COLUMN doc_key TEXT;      -- the sidecar's content-derived key
    ALTER TABLE documents ADD COLUMN identity TEXT NOT NULL DEFAULT '{}';
    ALTER TABLE documents ADD COLUMN defects TEXT NOT NULL DEFAULT '[]';
    ALTER TABLE documents ADD COLUMN split_uncertain INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE documents ADD COLUMN assigned_types TEXT;   -- JSON list: a person's type assignment (overlay)
    ALTER TABLE documents ADD COLUMN party_flag TEXT;       -- refiled | no_party
    ALTER TABLE documents ADD COLUMN party_override TEXT;   -- a person's attribution (party id, or 'none')
    ALTER TABLE documents ADD COLUMN created_at TEXT;
    CREATE UNIQUE INDEX documents_key ON documents(case_id, file_id, doc_key);

    ALTER TABLE jobs ADD COLUMN lease_until TEXT;

    ALTER TABLE review_items ADD COLUMN detail TEXT NOT NULL DEFAULT '{}';
    CREATE UNIQUE INDEX review_items_ref ON review_items(case_id, kind, ref);

    CREATE TABLE parties (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        pan TEXT,
        din TEXT,
        source TEXT NOT NULL,
        ord INTEGER NOT NULL
    );
    CREATE INDEX parties_case ON parties(case_id);

    -- F-04.8: figures the RM declared, kept for triangulation (F-19).
    CREATE TABLE declared_figures (
        case_id TEXT NOT NULL REFERENCES cases(id),
        field TEXT NOT NULL,
        value TEXT,
        proposed TEXT,
        source TEXT,
        basis TEXT NOT NULL,
        PRIMARY KEY (case_id, field)
    );

    -- F-13.1 / F-17.5: waived checklist items (non-mandatory only), with a reason.
    CREATE TABLE checklist_waivers (
        case_id TEXT NOT NULL REFERENCES cases(id),
        item_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        decided_by TEXT NOT NULL,
        decided_at TEXT NOT NULL,
        review_item_id TEXT,
        PRIMARY KEY (case_id, item_id)
    );
    """,
]


def db_path(root: Path | None = None) -> Path:
    return Path(root or data_root()) / "creditiq.sqlite3"


def migrate(conn: sqlite3.Connection) -> None:
    """Run the migrations not yet applied. Safe when several connections
    (the API and its job worker) open a new store at once: each migration
    takes the write lock, and one that another connection has just applied
    is skipped."""
    while True:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current >= len(MIGRATIONS):
            return
        index = current + 1
        try:
            conn.executescript(f"BEGIN IMMEDIATE; {MIGRATIONS[current]}; PRAGMA user_version = {index}; COMMIT;")
        except sqlite3.OperationalError:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            if conn.execute("PRAGMA user_version").fetchone()[0] >= index:
                continue
            raise


def connect(root: Path | None = None) -> sqlite3.Connection:
    path = db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    migrate(conn)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT, rolled back on any exception."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def log_decision(
    conn: sqlite3.Connection, *, at: str, actor: str, action: str, case_id: str | None, detail: str = "{}"
) -> None:
    conn.execute(
        "INSERT INTO decision_log (at, actor, case_id, action, detail) VALUES (?, ?, ?, ?, ?)",
        (at, actor, case_id, action, detail),
    )
