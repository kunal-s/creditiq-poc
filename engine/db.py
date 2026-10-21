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
    ALTER TABLE documents ADD COLUMN party_flag TEXT;       -- refiled | conflict | no_party
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
    # 3: case stages follow the processing stages (FRD 3.1 §7). The next
    # refresh of each case recomputes its stage exactly.
    """
    UPDATE cases SET stage = 'Documents' WHERE stage = 'Readiness';
    UPDATE cases SET stage = 'CrossVerification' WHERE stage = 'Appraisal';
    """,
    # 4: a failed cross-check's question for the customer (F-19.5).
    """
    ALTER TABLE findings ADD COLUMN query TEXT;
    """,
    # 5: a finding's area and scope, its line-by-line detail, and the
    # documents it waits for (F-19.3).
    """
    ALTER TABLE findings ADD COLUMN area TEXT NOT NULL DEFAULT 'identity';
    ALTER TABLE findings ADD COLUMN scope TEXT;
    ALTER TABLE findings ADD COLUMN detail TEXT;            -- JSON FindingDetail
    ALTER TABLE findings ADD COLUMN missing TEXT NOT NULL DEFAULT '[]';  -- JSON list
    """,
    # 6: RBL's reference record for a case, deviations and approving-authority areas (F-25.1,
    # F-25.2), and the reviewer's adjudications of the comparison (F-25.4, F-25.5). Each table
    # references only cases(id), so delete_case removes them in any order. No processing
    # module reads them (.importlinter contract 2).
    """
    CREATE TABLE reference_records (
        case_id TEXT PRIMARY KEY REFERENCES cases(id),
        workbook_name TEXT NOT NULL,
        workbook_sha256 TEXT NOT NULL,
        record_date TEXT,
        deviations_recorded INTEGER NOT NULL,
        config_version TEXT,
        imported_by TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        confirmed_by TEXT,
        confirmed_at TEXT,
        CHECK (confirmed_by IS NULL OR confirmed_by <> imported_by)
    );
    CREATE TABLE reference_items (
        case_id TEXT NOT NULL REFERENCES cases(id),
        area TEXT NOT NULL,          -- deviations | approving_authority
        item_key TEXT NOT NULL,      -- a norm id, REC-<row> for a row with no norm, or 'approval'
        data TEXT NOT NULL,          -- JSON ReferenceDeviation | ReferenceApproval
        source_ref TEXT NOT NULL,
        ord INTEGER NOT NULL,
        PRIMARY KEY (case_id, area, item_key)
    );
    CREATE TABLE comparison_adjudications (
        case_id TEXT NOT NULL REFERENCES cases(id),
        area TEXT NOT NULL,
        item_key TEXT NOT NULL,
        verdict TEXT NOT NULL CHECK (verdict IN ('valid', 'not_valid')),
        reason TEXT NOT NULL,
        snapshot TEXT NOT NULL,      -- JSON: status, both sides, config_version when decided
        decided_by TEXT NOT NULL,
        decided_at TEXT NOT NULL,
        PRIMARY KEY (case_id, area, item_key)
    );
    """,
    # 7: the cross-verification board (F-19). Each finding's card (its sources as columns, the
    # gap per leg, what would complete it) is kept with the finding; references stay stable
    # across runs; the latest run of each case is recorded; and a request a person adds to the
    # query list from a check that could not run is kept until the check completes. Every
    # table references only cases(id), so delete_case removes them in any order.
    """
    ALTER TABLE findings ADD COLUMN card TEXT;          -- JSON: the card fields of Finding
    CREATE TABLE finding_refs (
        case_id TEXT NOT NULL REFERENCES cases(id),
        rule_id TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT '',
        seq INTEGER NOT NULL,
        assigned_at TEXT NOT NULL,
        PRIMARY KEY (case_id, rule_id, scope)
    );
    CREATE TABLE crosscheck_runs (
        case_id TEXT PRIMARY KEY REFERENCES cases(id),
        run_no INTEGER NOT NULL,
        run_at TEXT NOT NULL,
        rules INTEGER NOT NULL,
        sources INTEGER NOT NULL
    );
    CREATE TABLE query_additions (
        case_id TEXT NOT NULL REFERENCES cases(id),
        rule_id TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL,
        added_by TEXT NOT NULL,
        added_at TEXT NOT NULL,
        PRIMARY KEY (case_id, rule_id, scope)
    );
    """,
    # 8: an escalation to the Credit Manager is kept with the discrepancy's identity (case, rule,
    # scope: the key of its XV reference), where a run of the checks cannot withdraw it. A run
    # withdraws the open review item of a discrepancy that does not fail; when the discrepancy
    # fails again, the item raised for it carries the escalation still unresolved. Accepting or
    # dismissing the discrepancy resolves it. Escalations recorded before this migration are copied
    # from the open review items that carry them. References only cases(id), so delete_case
    # removes it in any order.
    """
    CREATE TABLE finding_escalations (
        case_id TEXT NOT NULL REFERENCES cases(id),
        rule_id TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT '',
        escalated_by TEXT NOT NULL,
        escalated_at TEXT NOT NULL,
        comment TEXT NOT NULL,
        resolved_by TEXT,                  -- who accepted or dismissed the discrepancy
        resolved_at TEXT,
        PRIMARY KEY (case_id, rule_id, scope)
    );
    INSERT INTO finding_escalations (case_id, rule_id, scope, escalated_by, escalated_at, comment)
    SELECT r.case_id, f.rule_id, COALESCE(f.scope, ''),
           COALESCE(json_extract(r.detail, '$.escalation.by'), ''),
           COALESCE(json_extract(r.detail, '$.escalation.at'), ''),
           COALESCE(json_extract(r.detail, '$.escalation.comment'), '')
    FROM review_items r JOIN findings f ON f.case_id = r.case_id AND r.ref = 'finding:' || f.id
    WHERE r.kind = 'finding' AND r.status = 'open'
      AND CASE WHEN json_valid(r.detail) THEN json_type(r.detail, '$.escalation') END = 'object';
    """,
    # 12: the assessment gate (F-13, F-19 to F-24). Cross-verification, policy checks and the
    # outputs open only once completeness is satisfied and a person creates the case. Written
    # once and never cleared: a late document can move the stage back, but the case stays created.
    """
    ALTER TABLE cases ADD COLUMN assessment_opened_at TEXT;
    ALTER TABLE cases ADD COLUMN assessment_opened_by TEXT;
    """,
    # 13: the draft CAM's review (F-23): a section's words in a person's hand or redrafted by the
    # copilot and kept, the figures a person overrode with the reason, and the data asked for from
    # a section (it sits on the query list). Each copilot answer is recorded by its request, so the
    # same request is answered the same way. Every row is kept with who and when.
    """
    CREATE TABLE cam_reviews (
        case_id TEXT NOT NULL REFERENCES cases(id),
        section_id TEXT NOT NULL,
        state TEXT NOT NULL,               -- edited | regenerated
        paragraphs TEXT NOT NULL,          -- JSON list of strings
        model TEXT,
        by TEXT NOT NULL,
        at TEXT NOT NULL,
        PRIMARY KEY (case_id, section_id)
    );
    CREATE TABLE cam_overrides (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        section_id TEXT NOT NULL,
        figure TEXT NOT NULL,
        original TEXT NOT NULL,
        value TEXT NOT NULL,
        reason TEXT NOT NULL,
        by TEXT NOT NULL,
        at TEXT NOT NULL
    );
    CREATE TABLE cam_requests (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        section_id TEXT NOT NULL,
        text TEXT NOT NULL,
        by TEXT NOT NULL,
        at TEXT NOT NULL
    );
    CREATE TABLE cam_model_calls (
        case_id TEXT NOT NULL REFERENCES cases(id),
        request_hash TEXT NOT NULL,
        model TEXT NOT NULL,
        response TEXT NOT NULL,            -- JSON list of paragraphs
        at TEXT NOT NULL,
        PRIMARY KEY (case_id, request_hash)
    );
    """,
    # 14: CAM templates (F-23; FRD decision C.4-12). Further layouts analysts make, bank-wide, beside
    # the configured default; never edited in place. And the template each appraisal's memo follows,
    # where one other than the default was chosen.
    """
    CREATE TABLE cam_templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        sections TEXT NOT NULL,            -- JSON: [{id, title, purpose, parts: [kind]}]
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE case_cam_templates (
        case_id TEXT PRIMARY KEY REFERENCES cases(id),
        template_id TEXT NOT NULL,
        chosen_by TEXT NOT NULL,
        chosen_at TEXT NOT NULL
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
    # FastAPI may open a request's connection in one threadpool thread and use
    # it in another. Each connection still belongs to exactly one request (or
    # one worker loop), never shared concurrently, so the same-thread check
    # only produces false errors.
    conn = sqlite3.connect(path, isolation_level=None, timeout=10, check_same_thread=False)
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
