"""draft -> send: the draft leaves a pending action, the act use case shows it for confirmation, and the host is called
only when the user confirms, with the values on the card, once."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from copilot.actions import ActionRefused, cancel, confirm
from copilot.api import create_app
from copilot.config import load_dir
from copilot.identity import HostIdentity, Principal
from copilot.runner import handle_turn, parse_draft
from copilot.settings import Settings
from copilot.store import Store
from copilot.tools import ToolCaller

CFG = load_dir(Path(__file__).resolve().parent.parent / "config")
ACT = CFG.use_case("send_followup_email")
USER = Principal("u1", "rm", frozenset({"case.read", "message.send"}), "tok-u1")
ROWS = [{"document": "bank_statement_apr.pdf", "status": "exception", "reason": "The file is password-protected.", "rule": "encrypted"}]
DRAFT = "Draft - not sent\nSubject: Please resend corrected documents\n\nHello [Name],\n\nPlease resend bank_statement_apr.pdf.\n\nThank you,\n[Name]"
CLOCK = {"t": "2026-10-28T10:00:00"}
NOW = lambda: CLOCK["t"]  # noqa: E731
VALUES = {"to": "customer@example.com", "subject": "Please resend corrected documents", "body": "Hello Asha,\n\nPlease resend bank_statement_apr.pdf."}


def router_for(use_case):
    return FunctionModel(lambda m, i: ModelResponse(parts=[ToolCallPart("final_result", {"use_case": use_case, "confidence": 0.9})]))


def writer(text=DRAFT):
    def fn(messages, info):
        n = sum(isinstance(p, ToolReturnPart) for m in messages for p in m.parts)
        return ModelResponse(parts=[ToolCallPart("get_rejection_reasons", {})] if n == 0 else [ToolCallPart("final_result", {"text": text})])
    return FunctionModel(fn)


class Host:
    """Stands in for the host: serves the rejections, records message posts, and can be told to fail them."""

    def __init__(self):
        self.posts, self.fail = [], None

    def __call__(self, req):
        if req.method == "POST":
            self.posts.append((req.url.path, req.headers["authorization"], json.loads(req.content)))
            if self.fail:
                return self.fail
            return httpx.Response(200, json={"id": 7, "case_id": "1042", "to": VALUES["to"], "subject": VALUES["subject"], "status": "recorded"})
        return httpx.Response(200, json=ROWS)

    def caller(self):
        return ToolCaller(CFG, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(self)), now=NOW)


@pytest.fixture(autouse=True)
def clock():
    CLOCK["t"] = "2026-10-28T10:00:00"


async def say(store, session, host, use_case, text=DRAFT, msg="x"):
    return await handle_turn(CFG, router_model=router_for(use_case), runner_model=writer(text), caller=host.caller(), store=store,
                             principal=USER, session=session, message=msg, now=NOW)


async def drafted(ctx=None):
    host, store = Host(), Store(":memory:")
    session = store.create_session("u1", NOW(), ctx or {"case_id": "1042"})
    await say(store, session, host, "draft_followup_email")
    return host, store, store.load(session.session_id, "u1")


async def proposed():
    host, store, session = await drafted()
    res = await say(store, session, host, "send_followup_email", msg="send it")
    return host, store, store.load(session.session_id, "u1"), res


async def press(host, store, session, values=None, context=None, principal=USER):
    p = session.pending_action["id"]
    return await confirm(CFG, caller=host.caller(), store=store, principal=principal, session=session, pending_id=p,
                         values=VALUES if values is None else values, context=context or {"case_id": "1042"}, now=NOW)


def test_a_draft_is_split_into_subject_and_body():
    assert parse_draft(DRAFT, ACT.act) == {"subject": "Please resend corrected documents", "body": DRAFT.split("\n\n", 1)[1]}
    assert parse_draft("Draft - not sent\nNo subject here", ACT.act) is None
    assert parse_draft("Subject: only a subject", ACT.act) is None


async def test_a_draft_leaves_a_pending_action_bound_to_the_case_but_shows_no_card():
    host, store, s = await drafted()
    p = s.pending_action
    assert p["use_case"] == "send_followup_email" and p["context"] == {"case_id": "1042"}
    assert p["fields"]["to"] == "" and p["fields"]["subject"] == "Please resend corrected documents" and "[Name]" in p["fields"]["body"]
    assert host.posts == []
    assert "offer" in [t["event"] for t in store.read_trace(s.session_id)]


async def test_send_it_shows_the_card_and_calls_nothing():
    host, store, s, res = await proposed()
    assert res.terminal == "confirm" and res.text == ACT.act.confirm_text
    assert res.action["id"] == s.pending_action["id"] and set(res.action["fields"]) == {"to", "subject", "body"}
    assert host.posts == []
    assert [t["event"] for t in store.read_trace(s.session_id)][-3:] == ["route", "propose", "terminal"]


@pytest.mark.parametrize("how", ["no_draft", "lapsed", "other_case"])
async def test_nothing_to_send_says_so(how):
    host, store = Host(), Store(":memory:")
    session = store.create_session("u1", NOW(), {"case_id": "1042"})
    if how != "no_draft":
        await say(store, session, host, "draft_followup_email")
        session = store.load(session.session_id, "u1")
    if how == "lapsed":
        CLOCK["t"] = "2026-10-28T11:00:00"
    if how == "other_case":
        session.context = {"case_id": "2000"}
    res = await say(store, session, host, "send_followup_email", msg="send it")
    assert res.terminal == "cannot_do" and res.text == ACT.act.needs_draft and res.action is None


async def test_confirming_calls_the_host_once_with_the_users_token_and_the_card_values():
    host, store, s, _ = await proposed()
    pid = s.pending_action["id"]
    r = await press(host, store, s)
    assert r.terminal == "answer" and r.text == "The email to customer@example.com has been recorded for sending."
    assert host.posts == [("/api/cases/1042/messages", "Bearer tok-u1", {**VALUES, "idempotency_key": pid})]
    assert s.pending_action is None
    again = await confirm(CFG, caller=host.caller(), store=store, principal=USER, session=s, pending_id=pid, values=VALUES,
                          context={"case_id": "1042"}, now=NOW)
    assert again.terminal == "cannot_do" and len(host.posts) == 1  # a second press calls nothing
    act = [t for t in store.read_trace(s.session_id) if t["event"] == "act"]
    assert act[0]["detail"] == {"pending_id": pid, "tool": "send_customer_email", "ok": True, "error": None}
    assert "customer@example.com" not in json.dumps(act[0]["detail"])  # the trace holds no message content


async def test_text_still_in_brackets_is_refused_and_the_card_stays_open():
    host, store, s, _ = await proposed()
    with pytest.raises(ActionRefused) as e:
        await press(host, store, s, {**VALUES, "body": "Hello [Name],\n\nPlease resend."})
    assert e.value.status == 422 and e.value.message == ACT.act.blocked
    assert host.posts == [] and s.pending_action is not None


async def test_the_hosts_reason_is_shown_and_the_card_stays_open():
    host, store, s, _ = await proposed()
    host.fail = httpx.Response(422, json={"detail": "The recipient address is not valid."})
    with pytest.raises(ActionRefused) as e:
        await press(host, store, s, {**VALUES, "to": "nope"})
    assert e.value.status == 422 and e.value.message == "The recipient address is not valid." and s.pending_action is not None


async def test_an_unreachable_host_keeps_the_action_and_a_retry_reuses_the_key():
    host, store, s, _ = await proposed()
    host.fail = httpx.Response(503)
    with pytest.raises(ActionRefused) as e:
        await press(host, store, s)
    assert e.value.status == 503 and s.pending_action is not None
    host.fail = None
    await press(host, store, s)
    assert host.posts[0][2]["idempotency_key"] == host.posts[1][2]["idempotency_key"]


@pytest.mark.parametrize("values", [{"to": "a@b.co"}, {**VALUES, "extra": "x"}, {**VALUES, "body": "x" * 7000}])
async def test_only_the_card_fields_are_accepted(values):
    host, store, s, _ = await proposed()
    with pytest.raises(ActionRefused):
        await press(host, store, s, values)
    assert host.posts == []


async def test_a_lapsed_or_foreign_confirmation_is_not_run():
    host, store, s, _ = await proposed()
    r = await press(host, store, s, context={"case_id": "2000"})  # the user has moved to another case
    assert r.text == CFG.runtime.messages.action_expired and host.posts == []
    host, store, s, _ = await proposed()
    CLOCK["t"] = "2026-10-28T11:00:00"
    assert (await press(host, store, s)).text == CFG.runtime.messages.action_expired and host.posts == []


async def test_permissions_are_checked_again_at_confirmation():
    host, store, s, _ = await proposed()
    r = await press(host, store, s, principal=Principal("u1", "rm", frozenset({"case.read"}), "t"))
    assert r.text == CFG.runtime.messages.forbidden and host.posts == []


async def test_cancelling_clears_the_action():
    host, store, s, _ = await proposed()
    r = cancel(CFG, store=store, principal=USER, session=s, pending_id=s.pending_action["id"], now=NOW)
    assert r.text == CFG.runtime.messages.action_cancelled and s.pending_action is None


async def test_a_new_draft_replaces_the_pending_one():
    host, store, s = await drafted()
    first = s.pending_action["id"]
    await say(store, s, host, "draft_followup_email")
    assert store.load(s.session_id, "u1").pending_action["id"] != first


def test_the_gateway_confirms_and_cancels_only_the_callers_own_session(tmp_path):
    host = Host()
    ident = lambda req: httpx.Response(200, json={"id": "u1", "role": "rm", "permissions": ["case.read", "message.send"]}) if req.url.path == CFG.host.identity_path else host(req)  # noqa: E731
    mk = lambda: httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(ident))  # noqa: E731
    store = Store(tmp_path / "copilot.sqlite3")
    app = create_app(Settings(Path("."), tmp_path), cfg=CFG, identity=HostIdentity(CFG.host, mk()), caller=ToolCaller(CFG, mk(), now=NOW),
                     router_model=router_for("explain_rejections"), runner_model=writer(), now=NOW)
    client = TestClient(app)
    h = {"Authorization": "Bearer tok-u1"}
    sid = client.post("/chat", json={"message": "hi", "context": {"case_id": "1042"}}, headers=h).text.split('"session_id": "')[1].split('"')[0]
    s = Store(tmp_path / "copilot.sqlite3")
    session = s.load(sid, "u1")
    session.pending_action = {"id": "p_1", "use_case": "send_followup_email", "fields": {"to": "", "subject": "S", "body": "B"}, "slots": {"case_id": "1042"},
                              "context": {"case_id": "1042"}, "expires_at": "2099-01-01T00:00:00", "proposed": True}
    s.save(session, NOW())
    body = {"session_id": sid, "context": {"case_id": "1042"}, "values": VALUES}
    assert client.get(f"/sessions/{sid}", headers=h).json()["action"]["id"] == "p_1"
    assert client.post("/actions/p_1/confirm", json={**body, "session_id": "s_nope"}, headers=h).status_code == 404
    assert client.post("/actions/p_1/confirm", json={**body, "values": {**VALUES, "body": "Hi [Name]"}}, headers=h).status_code == 422
    r = client.post("/actions/p_1/confirm", json=body, headers=h)
    assert r.status_code == 200 and r.json()["terminal"] == "answer" and len(host.posts) == 1
    assert client.get(f"/sessions/{sid}", headers=h).json()["action"] is None
    assert client.post("/actions/p_1/cancel", json={"session_id": sid}, headers=h).json()["text"] == CFG.runtime.messages.action_cancelled


async def test_a_real_answer_offers_its_follow_ups_and_an_empty_one_does_not():
    host, store = Host(), Store(":memory:")
    session = store.create_session("u1", NOW(), {"case_id": "1042"})
    res = await say(store, session, host, "draft_followup_email")
    assert res.format == "draft" and res.follow_ups == ["Send it"]
    assert store.messages(session.session_id, "u1")[-1].payload["follow_ups"] == ["Send it"]

    class NoRows(Host):
        def __call__(self, req):
            return httpx.Response(200, json=[])
    res = await say(store, session, NoRows(), "draft_followup_email")
    assert res.text == CFG.use_case("draft_followup_email").empty_message and res.follow_ups == []


async def test_a_confirmed_action_is_marked_done():
    host, store, s, _ = await proposed()
    r = await press(host, store, s)
    assert r.done is True
    assert store.messages(s.session_id, "u1")[-1].payload["done"] is True
