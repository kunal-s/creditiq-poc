"""The engine's model call log (engine/model_log.py): the CAM copilot writes one row per HTTP attempt,
with its tokens and latency, and one replay_hit row when a recorded answer is used. The recording
itself (cam_model_calls) is unchanged, and the log never holds the prompt, the answer or the key."""

import io
import json
import sqlite3
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cam_copilot, db, model_log
from tests.test_cam_review import _case

ANSWER = {"choices": [{"message": {"content": json.dumps({"paragraphs": ["Redrafted."]})}}],
          "usage": {"prompt_tokens": 300, "completion_tokens": 40, "total_tokens": 340,
                    "prompt_tokens_details": {"cached_tokens": 128}}}


class _Resp(io.BytesIO):
    status = 200
    headers = {"x-ratelimit-remaining-tokens": "150000", "x-ratelimit-remaining-requests": "99"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def analyst(client: TestClient) -> dict:
    from tests.conftest import ANALYST, sign_in

    return sign_in(client, ANALYST)


def _rows(root: Path) -> list[dict]:
    conn = db.connect(root)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM model_log ORDER BY at, rowid")]
    finally:
        conn.close()


def _regenerate(client, headers, case_id, instruction="Shorter."):
    return client.post(f"/api/cases/{case_id}/cam/sections/analysis/regenerate", json={"instruction": instruction},
                       headers=headers)


def test_a_live_answer_gives_one_row_with_tokens_and_a_recorded_one_a_replay_hit(
        client: TestClient, analyst, published_data_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-0123456789abcdef")
    sent: list = []

    def urlopen(req, timeout=None):
        sent.append(req)
        return _Resp(json.dumps(ANSWER).encode())

    monkeypatch.setattr(cam_copilot.urllib.request, "urlopen", urlopen)
    case_id = _case(client, analyst, published_data_root)
    first = _regenerate(client, analyst, case_id)
    assert first.status_code == 200, first.text and first.json()["recorded"] is False
    [row] = _rows(published_data_root)
    assert (row["service"], row["task"], row["source"], row["status"], row["attempt"]) == ("cam", "cam_section", "live", "ok", 1)
    assert (row["input_tokens"], row["output_tokens"], row["total_tokens"], row["cached_tokens"]) == (300, 40, 340, 128)
    assert row["http_status"] == 200 and row["latency_ms"] >= 0 and row["case_ref"] == case_id
    assert row["ratelimit_remaining_tokens"] == 150000 and row["ratelimit_remaining_requests"] == 99
    # The request is named by its recording hash, the one cam_model_calls keeps.
    conn = db.connect(published_data_root)
    try:
        [recorded] = conn.execute("SELECT request_hash, response FROM cam_model_calls WHERE case_id = ?", (case_id,)).fetchall()
    finally:
        conn.close()
    assert row["request_key"] == recorded["request_hash"] and json.loads(recorded["response"]) == ["Redrafted."]
    text = json.dumps(row)
    assert "Redrafted" not in text and "sk-test" not in text and "Shorter" not in text

    again = _regenerate(client, analyst, case_id)
    assert again.json()["recorded"] is True and len(sent) == 1
    hit = _rows(published_data_root)[-1]
    assert (hit["source"], hit["status"], hit["input_tokens"]) == ("replay_hit", "ok", None)


def test_an_http_error_is_logged_with_its_status(client: TestClient, analyst, published_data_root: Path,
                                                monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-0123456789abcdef")

    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {"retry-after": "7"},
                                     io.BytesIO(b'{"error": {"message": "Bad input, key sk-live-abcdef0123456789"}}'))

    monkeypatch.setattr(cam_copilot.urllib.request, "urlopen", urlopen)
    case_id = _case(client, analyst, published_data_root)
    assert _regenerate(client, analyst, case_id).status_code == 502
    [row] = _rows(published_data_root)
    assert (row["status"], row["error_code"], row["http_status"], row["retry_after_s"]) == ("error", "http", 400, 7.0)
    assert row["kind"] == "bad_request"
    assert "Bad input" in row["message"] and "sk-live" not in row["message"]


def test_the_log_is_append_only(published_data_root: Path):
    conn = db.connect(published_data_root)
    try:
        conn.execute("INSERT INTO model_log (id, at, service, source, status) VALUES ('x', '2026-11-13', 'cam', 'live', 'ok')")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM model_log")
    finally:
        conn.close()


def test_a_store_whose_version_21_was_another_change_gets_the_model_log(tmp_path):
    """A working copy that numbered its own migration 21 before the model call log took the number
    (a column on documents, say) is at version 21 with no model_log: migration 22 creates it, as
    21 would have, and the log is append-only there too."""
    path = db.db_path(tmp_path)
    conn = sqlite3.connect(path, isolation_level=None)
    for index, script in enumerate(db.MIGRATIONS[:20], start=1):
        conn.executescript(f"BEGIN; {script}; PRAGMA user_version = {index}; COMMIT;")
    conn.executescript("BEGIN; ALTER TABLE documents ADD COLUMN search_summary TEXT; PRAGMA user_version = 21; COMMIT;")
    conn.close()

    store = db.connect(tmp_path)
    try:
        assert store.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS) == 22
        columns = {r["name"] for r in store.execute("PRAGMA table_info(model_log)")}
        assert {"id", "at", "service", "source", "status", "kind"} <= columns
        model_log.write(store, {"at": "2026-11-13T10:00:00+00:00", "service": "cam", "task": "cam_section",
                                "source": "live", "status": "error", "kind": "timeout"})
        assert [tuple(r) for r in store.execute("SELECT service, kind FROM model_log")] == [("cam", "timeout")]
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            store.execute("DELETE FROM model_log")
    finally:
        store.close()
