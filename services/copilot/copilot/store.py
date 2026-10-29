"""Session store and trace log (SQLite, WAL).

Three kinds of state, kept apart: the transcript (messages), the working context (columns of `sessions`) and the
user context, which is never stored (the host supplies it on every request). The trace is append-only, enforced by
triggers. Time is always passed in by the caller, so nothing here reads the wall clock.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

MIGRATIONS = [
    """
    CREATE TABLE sessions (
      session_id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      context TEXT NOT NULL DEFAULT '{}',
      active_use_case TEXT,
      resolved_slots TEXT NOT NULL DEFAULT '{}',
      pending_slot TEXT,
      pending_action TEXT,
      last_results TEXT NOT NULL DEFAULT '[]',
      summary TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE messages (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL REFERENCES sessions(session_id),
      at TEXT NOT NULL,
      role TEXT NOT NULL CHECK (role IN ('user','assistant')),
      content TEXT NOT NULL,
      terminal TEXT
    );
    CREATE INDEX messages_session ON messages(session_id, seq);
    CREATE TABLE trace (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      at TEXT NOT NULL,
      session_id TEXT NOT NULL,
      turn_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      event TEXT NOT NULL,
      detail TEXT NOT NULL
    );
    CREATE INDEX trace_session ON trace(session_id, seq);
    CREATE TRIGGER trace_no_update BEFORE UPDATE ON trace BEGIN SELECT RAISE(ABORT, 'trace is append-only'); END;
    CREATE TRIGGER trace_no_delete BEFORE DELETE ON trace BEGIN SELECT RAISE(ABORT, 'trace is append-only'); END;
    """,
    # recorded model responses: the unit of determinism (CLAUDE.md rule 6)
    """
    CREATE TABLE llm_calls (
      request_key TEXT PRIMARY KEY,
      model TEXT NOT NULL,
      recorded_at TEXT NOT NULL,
      request TEXT NOT NULL,
      response TEXT NOT NULL
    );
    """,
    "ALTER TABLE messages ADD COLUMN payload TEXT;",
]


@dataclass
class Session:
    session_id: str
    user_id: str
    context: dict = field(default_factory=dict)  # what the client says is open, e.g. {"case_id": "1042"}
    active_use_case: str | None = None
    resolved_slots: dict = field(default_factory=dict)
    pending_slot: str | None = None
    pending_action: dict | None = None  # {type, draft_id, expires_at}
    last_results: list[dict] = field(default_factory=list)  # references with fetch time, not copies
    summary: str = ""


@dataclass(frozen=True)
class Message:
    seq: int
    at: str
    role: str
    content: str
    terminal: str | None
    payload: dict | None = None


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            folder = Path(self.path).parent
            folder.mkdir(parents=True, exist_ok=True)
            folder.chmod(0o700)  # transcripts and recorded requests hold case content, like the engine's case files
        self._mem = sqlite3.connect(":memory:") if self.path == ":memory:" else None
        with self._conn() as c:
            if self._mem is None:
                c.execute("PRAGMA journal_mode=WAL")
            v = c.execute("PRAGMA user_version").fetchone()[0]
            for n, script in enumerate(MIGRATIONS[v:], start=v + 1):
                c.executescript(script)
                c.execute(f"PRAGMA user_version = {n}")

    @contextmanager
    def _conn(self):
        c = self._mem or sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            if self._mem is None:
                c.close()

    # sessions
    def create_session(self, user_id: str, now: str, context: dict | None = None) -> Session:
        s = Session(f"s_{uuid.uuid4().hex[:12]}", user_id, dict(context or {}))
        with self._conn() as c:
            c.execute(
                "INSERT INTO sessions(session_id,user_id,created_at,updated_at,context) VALUES (?,?,?,?,?)",
                (s.session_id, user_id, now, now, json.dumps(s.context)),
            )
        return s

    def load(self, session_id: str, user_id: str) -> Session | None:
        """A session belongs to the user who opened it; anyone else gets None, as if it did not exist."""
        with self._conn() as c:
            r = c.execute("SELECT * FROM sessions WHERE session_id=? AND user_id=?", (session_id, user_id)).fetchone()
        if r is None:
            return None
        return Session(
            r["session_id"], r["user_id"], json.loads(r["context"]), r["active_use_case"], json.loads(r["resolved_slots"]),
            r["pending_slot"], json.loads(r["pending_action"]) if r["pending_action"] else None,
            json.loads(r["last_results"]), r["summary"],
        )

    def save(self, s: Session, now: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE sessions SET updated_at=?, context=?, active_use_case=?, resolved_slots=?, pending_slot=?,"
                " pending_action=?, last_results=?, summary=? WHERE session_id=? AND user_id=?",
                (now, json.dumps(s.context), s.active_use_case, json.dumps(s.resolved_slots), s.pending_slot,
                 json.dumps(s.pending_action) if s.pending_action else None, json.dumps(s.last_results), s.summary,
                 s.session_id, s.user_id),
            )

    # transcript
    def add_message(self, session_id: str, at: str, role: str, content: str, terminal: str | None = None, payload: dict | None = None) -> int:
        with self._conn() as c:
            return c.execute(
                "INSERT INTO messages(session_id,at,role,content,terminal,payload) VALUES (?,?,?,?,?,?)",
                (session_id, at, role, content, terminal, json.dumps(payload) if payload else None),
            ).lastrowid

    def messages(self, session_id: str, user_id: str) -> list[Message]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT m.seq,m.at,m.role,m.content,m.terminal,m.payload FROM messages m JOIN sessions s USING(session_id)"
                " WHERE m.session_id=? AND s.user_id=? ORDER BY m.seq",
                (session_id, user_id),
            ).fetchall()
        return [Message(*tuple(r)[:5], json.loads(r[5]) if r[5] else None) for r in rows]

    # recorded model responses
    def get_llm_call(self, key: str) -> str | None:
        with self._conn() as c:
            r = c.execute("SELECT response FROM llm_calls WHERE request_key=?", (key,)).fetchone()
        return r["response"] if r else None

    def put_llm_call(self, key: str, model: str, at: str, request: str, response: str, *, replace: bool = False) -> None:
        """A live recording keeps the first answer for a request; an explicit import replaces it, so the store matches the file."""
        with self._conn() as c:
            c.execute(
                f"INSERT OR {'REPLACE' if replace else 'IGNORE'} INTO llm_calls(request_key,model,recorded_at,request,response) VALUES (?,?,?,?,?)",
                (key, model, at, request, response),
            )

    # trace
    def trace(self, *, at: str, session_id: str, turn_id: str, user_id: str, event: str, detail: dict) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO trace(at,session_id,turn_id,user_id,event,detail) VALUES (?,?,?,?,?,?)",
                (at, session_id, turn_id, user_id, event, json.dumps(detail, sort_keys=True, default=str)),
            )

    def read_trace(self, session_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM trace WHERE session_id=? ORDER BY seq", (session_id,)).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]


def pending_action_live(s: Session, now: str) -> bool:
    """A pending action is bound to the draft the user saw and lapses at `expires_at` (ISO strings compare in order)."""
    return bool(s.pending_action) and s.pending_action.get("expires_at", "") > now