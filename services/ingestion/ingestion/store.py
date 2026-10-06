"""SQLite store (FRD AD-3). Stage outputs and extracted text are JSONB (SQLite >= 3.45):
written with jsonb(?) and read back with json(col). One writer at a time (WAL)."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  sha256 TEXT PRIMARY KEY, filename TEXT, mime TEXT, size INTEGER, kind TEXT);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, case_ref TEXT NOT NULL, document_sha256 TEXT NOT NULL, filename TEXT,
  config_version TEXT NOT NULL, config_hash TEXT NOT NULL, engine_version TEXT NOT NULL,
  status TEXT, stage TEXT, decision TEXT, result BLOB, created_at TEXT);
CREATE INDEX IF NOT EXISTS runs_case ON runs(case_ref);
CREATE TABLE IF NOT EXISTS pages (
  run_id TEXT NOT NULL, page_no INTEGER NOT NULL, source TEXT, grade TEXT, ocr_conf REAL,
  text TEXT, words BLOB, lines BLOB, summary BLOB, PRIMARY KEY (run_id, page_no));
CREATE TABLE IF NOT EXISTS stage_results (
  run_id TEXT NOT NULL, seq INTEGER NOT NULL, stage TEXT NOT NULL, payload BLOB,
  input_hash TEXT, output_hash TEXT, ms INTEGER, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS classifications (
  run_id TEXT PRIMARY KEY, type TEXT, tier TEXT, confidence REAL, signals BLOB, candidates BLOB);
CREATE TABLE IF NOT EXISTS extractions (
  run_id TEXT NOT NULL, instance_no INTEGER NOT NULL, instance_key TEXT, page_from INTEGER, page_to INTEGER,
  fields BLOB, tables BLOB, missing BLOB, PRIMARY KEY (run_id, instance_no));
CREATE TABLE IF NOT EXISTS validations (
  run_id TEXT NOT NULL, instance_no INTEGER NOT NULL, checks BLOB, PRIMARY KEY (run_id, instance_no));
CREATE TABLE IF NOT EXISTS llm_calls (
  key TEXT PRIMARY KEY, provider TEXT, model TEXT, task TEXT, origin TEXT, request BLOB, response BLOB);
CREATE TABLE IF NOT EXISTS ocr_cache (key TEXT PRIMARY KEY, result BLOB);
"""


def _j(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._lock = threading.RLock()
        if sqlite3.sqlite_version_info < (3, 45, 0):
            raise RuntimeError(f"SQLite {sqlite3.sqlite_version} is too old: JSONB needs 3.45 or newer")
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def _q(self, sql: str, args=()):
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    # --- documents and runs ---------------------------------------------------------------
    def add_document(self, sha256: str, filename: str, mime: str, size: int, kind: str | None) -> None:
        with self._lock:
            self._conn.execute("INSERT OR IGNORE INTO documents VALUES (?,?,?,?,?)", (sha256, filename, mime, size, kind))

    def begin_run(self, run_id: str, case_ref: str, sha256: str, filename: str, config_version: str, config_hash: str, engine_version: str) -> None:
        """Re-running the same inputs replaces the earlier run: same bytes, same config, same answer."""
        with self.tx() as c:
            for t in ("pages", "stage_results", "classifications", "extractions", "validations"):
                c.execute(f"DELETE FROM {t} WHERE run_id=?", (run_id,))
            c.execute("INSERT OR REPLACE INTO runs (id,case_ref,document_sha256,filename,config_version,config_hash,engine_version,status,stage,created_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (run_id, case_ref, sha256, filename, config_version, config_hash, engine_version, "running", "quality",
                       datetime.now(timezone.utc).isoformat()))

    def save_pages(self, run_id: str, pages) -> None:
        with self.tx() as c:
            for p in pages:
                j = p.to_json()
                words = [w for l in j["lines"] for w in l["words"]]
                c.execute("INSERT INTO pages VALUES (?,?,?,?,?,?,jsonb(?),jsonb(?),jsonb(?))",
                          (run_id, p.no, p.source, p.grade, p.ocr_conf, p.text(), _j(words), _j(j["lines"]), _j(p.summary())))

    def save_stage(self, run_id: str, seq: int, stage: str, payload, input_hash: str, output_hash: str, ms: int) -> None:
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO stage_results VALUES (?,?,?,jsonb(?),?,?,?)", (run_id, seq, stage, _j(payload), input_hash, output_hash, ms))
            c.execute("UPDATE runs SET stage=? WHERE id=?", (stage, run_id))

    def save_classification(self, run_id: str, cls: dict) -> None:
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO classifications VALUES (?,?,?,?,jsonb(?),jsonb(?))",
                      (run_id, cls.get("type"), cls.get("tier"), cls.get("confidence"), _j(cls.get("signals", {})), _j(cls.get("candidates", []))))

    def save_instance(self, run_id: str, n: int, key: str | None, p0: int, p1: int, fields: dict, tables: dict, checks: list) -> None:
        missing = sorted(k for k, v in fields.items() if v.get("status") == "missing")
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?,?,jsonb(?),jsonb(?),jsonb(?))", (run_id, n, key, p0, p1, _j(fields), _j(tables), _j(missing)))
            c.execute("INSERT OR REPLACE INTO validations VALUES (?,?,jsonb(?))", (run_id, n, _j(checks)))

    def finish_run(self, run_id: str, status: str, decision: str | None, result: dict) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET status=?, decision=?, stage='done', result=jsonb(?) WHERE id=?", (status, decision, _j(result), run_id))

    # --- reads ----------------------------------------------------------------------------
    def get_run(self, run_id: str) -> dict | None:
        r = self._q("SELECT id,case_ref,document_sha256,filename,config_version,config_hash,engine_version,status,stage,decision,json(result) FROM runs WHERE id=?", (run_id,))
        if not r:
            return None
        k = ["id", "case_ref", "sha256", "filename", "config_version", "config_hash", "engine_version", "status", "stage", "decision", "result"]
        d = dict(zip(k, r[0]))
        d["result"] = json.loads(d["result"]) if d["result"] else None
        return d

    def list_runs(self, case_ref: str) -> list[dict]:
        rows = self._q("SELECT id,filename,status,decision,config_version FROM runs WHERE case_ref=? ORDER BY id", (case_ref,))
        return [dict(zip(["id", "filename", "status", "decision", "config_version"], r)) for r in rows]

    def get_stages(self, run_id: str) -> list[dict]:
        rows = self._q("SELECT seq,stage,json(payload),input_hash,output_hash,ms FROM stage_results WHERE run_id=? ORDER BY seq", (run_id,))
        return [{"seq": a, "stage": b, "payload": json.loads(c), "input_hash": d, "output_hash": e, "ms": f} for a, b, c, d, e, f in rows]

    def get_page(self, run_id: str, page_no: int) -> dict | None:
        r = self._q("SELECT json(summary),text,json(lines) FROM pages WHERE run_id=? AND page_no=?", (run_id, page_no))
        if not r:
            return None
        return {**json.loads(r[0][0]), "text": r[0][1], "lines": json.loads(r[0][2])}

    def query_words(self, run_id: str, needle: str) -> list[dict]:
        """Example of querying inside the JSONB: pages whose words contain the needle."""
        rows = self._q("SELECT page_no, count(*) FROM pages, json_each(pages.words) WHERE run_id=? AND json_extract(value,'$[0]')=? GROUP BY page_no", (run_id, needle))
        return [{"page": p, "count": n} for p, n in rows]

    # --- recordings and OCR cache ---------------------------------------------------------
    def get_llm_call(self, key: str) -> dict | None:
        r = self._q("SELECT provider,model,task,origin,json(request),json(response) FROM llm_calls WHERE key=?", (key,))
        if not r:
            return None
        p, m, t, o, req, resp = r[0]
        return {"provider": p, "model": m, "task": t, "origin": o, "request": json.loads(req), "response": json.loads(resp)}

    def put_llm_call(self, key: str, row: dict) -> None:
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO llm_calls VALUES (?,?,?,?,?,jsonb(?),jsonb(?))",
                      (key, row["provider"], row["model"], row["task"], row.get("origin", "live"), _j(row["request"]), _j(row["response"])))

    def get(self, key: str) -> dict | None:  # OcrCache protocol
        r = self._q("SELECT json(result) FROM ocr_cache WHERE key=?", (key,))
        return json.loads(r[0][0]) if r else None

    def put(self, key: str, value: dict) -> None:
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO ocr_cache VALUES (?,jsonb(?))", (key, _j(value)))
