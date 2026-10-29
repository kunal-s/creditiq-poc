import sqlite3

import pytest

from copilot.store import Store, pending_action_live

T0, T1 = "2026-10-28T10:00:00", "2026-10-28T10:05:00"


def test_session_roundtrip_and_owner_only(tmp_path):
    st = Store(tmp_path / "d" / "copilot.sqlite3")
    s = st.create_session("u1", T0, {"case_id": "1042"})
    s.active_use_case, s.resolved_slots = "explain_rejections", {"case_id": "1042"}
    s.last_results = [{"tool": "get_rejection_reasons", "ref": "r_31", "fetched_at": T0}]
    s.pending_action = {"type": "send_email", "draft_id": "d_7", "expires_at": "2026-10-28T10:10:00"}
    st.save(s, T1)
    got = st.load(s.session_id, "u1")
    assert got == s
    assert st.load(s.session_id, "u2") is None
    assert st.load("s_missing", "u1") is None


def test_pending_action_lapses(tmp_path):
    s = Store(":memory:").create_session("u1", T0)
    assert not pending_action_live(s, T0)
    s.pending_action = {"expires_at": "2026-10-28T10:10:00"}
    assert pending_action_live(s, T1) and not pending_action_live(s, "2026-10-28T10:10:01")


def test_transcript_order_and_privacy():
    st = Store(":memory:")
    s = st.create_session("u1", T0)
    st.add_message(s.session_id, T0, "user", "why?")
    st.add_message(s.session_id, T1, "assistant", "because", terminal="answer")
    assert [(m.role, m.terminal) for m in st.messages(s.session_id, "u1")] == [("user", None), ("assistant", "answer")]
    assert st.messages(s.session_id, "u2") == []


def test_trace_is_append_only(tmp_path):
    p = tmp_path / "c.sqlite3"
    st = Store(p)
    s = st.create_session("u1", T0)
    st.trace(at=T0, session_id=s.session_id, turn_id="t1", user_id="u1", event="route", detail={"use_case": "x", "confidence": 0.9})
    assert st.read_trace(s.session_id)[0]["detail"]["confidence"] == 0.9
    con = sqlite3.connect(p)
    for sql in ("UPDATE trace SET event='x'", "DELETE FROM trace"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            con.execute(sql)


def test_reopen_keeps_data_and_does_not_remigrate(tmp_path):
    p = tmp_path / "c.sqlite3"
    sid = Store(p).create_session("u1", T0).session_id
    assert Store(p).load(sid, "u1") is not None


def test_data_folder_is_private(tmp_path):
    Store(tmp_path / "copilot" / "c.sqlite3")
    assert (tmp_path / "copilot").stat().st_mode & 0o777 == 0o700


def test_import_recordings_cli(tmp_path, monkeypatch, capsys):
    import json

    from copilot.cli import main

    f = tmp_path / "r.json"
    f.write_text(json.dumps([{"request_key": "k1", "model": "m", "request": "{}", "response": "[]"}]))
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "d"))
    assert main(["import-recordings", str(f)]) == 0 and main(["import-recordings", str(f)]) == 0  # twice: idempotent
    assert "imported 1" in capsys.readouterr().out
    assert Store(tmp_path / "d" / "copilot.sqlite3").get_llm_call("k1") == "[]"


def test_import_replaces_what_is_already_stored_but_a_live_recording_keeps_the_first(tmp_path, monkeypatch):
    import json

    from copilot.cli import main

    st = Store(tmp_path / "d" / "copilot.sqlite3")
    st.put_llm_call("k", "m", "t", "{}", "first")
    st.put_llm_call("k", "m", "t", "{}", "second")  # a live recording does not overwrite
    assert st.get_llm_call("k") == "first"
    f = tmp_path / "r.json"
    f.write_text(json.dumps([{"request_key": "k", "model": "m", "request": "{}", "response": "imported"}]))
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path / "d"))
    assert main(["import-recordings", str(f)]) == 0
    assert st.get_llm_call("k") == "imported"
