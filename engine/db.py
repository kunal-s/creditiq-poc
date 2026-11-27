"""SQLite store under the data root (docs/functional-requirements.md AD-3).

One file, `<data root>/creditiq.sqlite3`. Schema changes are appended to
MIGRATIONS and never edited once committed; `PRAGMA user_version` records
how many have run. Nested structures (pages, classification, sides) are
JSON text columns, validated by the engine/contracts models on read.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .migrations import MIGRATIONS
from .migrations import ensure_guarded as _ensure_guarded
from .store import data_root

__all__ = ["MIGRATIONS", "connect", "db_path", "log_decision", "migrate", "transaction"]


def db_path(root: Path | None = None) -> Path:
    return Path(root or data_root()) / "creditiq.sqlite3"


def _apply_function(conn: sqlite3.Connection, step: Callable[[sqlite3.Connection], None], index: int) -> None:
    """A migration written as a function: under the write lock, skipped if another connection has just
    applied it, rolled back whole if it fails."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("PRAGMA user_version").fetchone()[0] < index:
            step(conn)
            conn.execute(f"PRAGMA user_version = {index}")
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def migrate(conn: sqlite3.Connection) -> None:
    """Run the migrations not yet applied. Safe when several connections
    (the API and its job worker) open a new store at once: each migration
    takes the write lock, and one that another connection has just applied
    is skipped."""
    while True:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current >= len(MIGRATIONS):
            _ensure_guarded(conn)
            return
        index = current + 1
        step = MIGRATIONS[current]
        try:
            if callable(step):
                _apply_function(conn, step, index)
            else:
                conn.executescript(f"BEGIN IMMEDIATE; {step}; PRAGMA user_version = {index}; COMMIT;")
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
