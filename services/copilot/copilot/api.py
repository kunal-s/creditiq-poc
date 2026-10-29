"""HTTP gateway: identity, session, one turn, streamed back as server-sent events.

POST /chat          {message, session_id?, context?}  ->  text/event-stream: `session`, then `result` (or `error`)
POST /actions/{id}/confirm  {session_id, context, values}  ->  the result of the confirmed act (422 keeps the card open)
POST /actions/{id}/cancel   {session_id}                   ->  the result of the cancellation
GET  /sessions/{id} the caller's own transcript
GET  /health
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .actions import ActionRefused, cancel, confirm
from .config import CopilotConfig, load_dir
from .identity import HostIdentity, IdentityUnavailable, Principal, Unauthenticated, bearer_token
from .models import build_model
from .recording import ReplayMiss
from .runner import handle_turn
from .settings import Settings, utc_now
from .store import Session, Store, pending_action_live
from .tools import ToolCaller

log = logging.getLogger("copilot")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    context: dict = Field(default_factory=dict)


class ConfirmRequest(BaseModel):
    session_id: str
    context: dict = Field(default_factory=dict)
    values: dict[str, str]


class CancelRequest(BaseModel):
    session_id: str


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(
    settings: Settings, *, cfg: CopilotConfig | None = None, identity: HostIdentity | None = None, caller: ToolCaller | None = None,
    router_model=None, runner_model=None, now: Callable[[], str] = utc_now,
) -> FastAPI:
    cfg = cfg or load_dir(settings.config_dir)
    if settings.host_url:
        cfg = cfg.model_copy(update={"host": cfg.host.model_copy(update={"base_url": settings.host_url})})
    if settings.cors_origins is not None:
        cfg = cfg.model_copy(update={"host": cfg.host.model_copy(update={"cors_origins": list(settings.cors_origins)})})
    store = Store(settings.data_dir / "copilot.sqlite3")
    identity = identity or HostIdentity(cfg.host)
    caller = caller or ToolCaller(cfg, now=now)
    models = {}

    def model(role: str, given):
        if given is not None:
            return given
        if role not in models:  # built on first use so a replay-only start needs no key
            models[role] = build_model(cfg.llm, role, store=store, mode=settings.mode, now=now)
        return models[role]

    locks: dict[str, asyncio.Lock] = {}
    app = FastAPI(title="Case assistant", docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.host.cors_origins, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

    async def principal(authorization: str | None = Header(None)) -> Principal:
        try:
            return await identity.resolve(bearer_token(authorization))
        except Unauthenticated:
            raise HTTPException(401, "not signed in") from None
        except IdentityUnavailable as e:
            log.warning("identity unavailable: %s", e)
            raise HTTPException(503, "identity service unavailable") from None

    @app.get("/health")
    def health():
        return {"ok": True, "config": cfg.hash[:12], "mode": settings.mode}

    @app.get("/sessions/{session_id}")
    def transcript(session_id: str, user: Principal = Depends(principal)):
        s = store.load(session_id, user.user_id)
        if s is None:
            raise HTTPException(404, "no such session")
        live = pending_action_live(s, now())
        return {"session_id": s.session_id, "context": s.context,
                "action": {k: s.pending_action[k] for k in ("id", "use_case", "fields", "expires_at")} if live and s.pending_action.get("proposed") else None,
                "messages": [{"role": m.role, "text": m.content, "terminal": m.terminal, "at": m.at, **(m.payload or {})} for m in store.messages(session_id, user.user_id)]}

    @app.post("/chat")
    async def chat(body: ChatRequest, user: Principal = Depends(principal)):
        if len(body.message) > cfg.runtime.session.max_message_chars:
            raise HTTPException(422, "message too long")
        context = {k: str(v) for k, v in body.context.items() if k in cfg.host.context_keys and v not in (None, "")}
        if body.session_id:
            session: Session | None = store.load(body.session_id, user.user_id)
            if session is None:
                raise HTTPException(404, "no such session")
            session.context = context  # what is open now, not what was open before
        else:
            session = store.create_session(user.user_id, now(), context)

        async def events():
            yield _sse("session", {"session_id": session.session_id})
            lock = locks.setdefault(session.session_id, asyncio.Lock())
            async with lock:  # one turn at a time per session
                if len(locks) > 1000:  # drop idle locks so the table cannot grow without bound
                    for k in [k for k, v in locks.items() if not v.locked() and k != session.session_id]:
                        del locks[k]
                try:
                    res = await handle_turn(cfg, router_model=model("router", router_model), runner_model=model("runner", runner_model),
                                            caller=caller, store=store, principal=user, session=session, message=body.message, now=now)
                except ReplayMiss as e:
                    log.warning("%s", e)
                    yield _sse("error", {"code": "model_unavailable"})
                    return
                except Exception:  # headers are already sent: end the stream with an event, not a broken connection
                    log.exception("turn failed")
                    yield _sse("error", {"code": "internal"})
                    return
            yield _sse("result", {"session_id": res.session_id, "turn_id": res.turn_id, "terminal": res.terminal, "text": res.text,
                                  "use_case": res.use_case, "columns": res.columns, "rows": res.rows, "sources": res.sources,
                                  "action": res.action, "format": res.format, "follow_ups": res.follow_ups})

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    def _context(raw: dict) -> dict:
        return {k: str(v) for k, v in raw.items() if k in cfg.host.context_keys and v not in (None, "")}

    def _own_session(session_id: str, user: Principal) -> Session:
        session = store.load(session_id, user.user_id)
        if session is None:
            raise HTTPException(404, "no such session")
        return session

    def _result(r) -> dict:
        return {"session_id": r.session_id, "terminal": r.terminal, "text": r.text, "use_case": None, "columns": [], "rows": [],
                "sources": r.sources, "done": r.done}

    @app.post("/actions/{pending_id}/confirm")
    async def confirm_action(pending_id: str, body: ConfirmRequest, user: Principal = Depends(principal)):
        session = _own_session(body.session_id, user)
        async with locks.setdefault(session.session_id, asyncio.Lock()):
            session = _own_session(body.session_id, user)  # re-read: a turn may have finished while this waited
            try:
                r = await confirm(cfg, caller=caller, store=store, principal=user, session=session, pending_id=pending_id,
                                  values=body.values, context=_context(body.context), now=now)
            except ActionRefused as e:
                raise HTTPException(e.status, e.message) from None
            except Exception:
                log.exception("action failed")
                raise HTTPException(500, "action failed") from None
        return _result(r)

    @app.post("/actions/{pending_id}/cancel")
    async def cancel_action(pending_id: str, body: CancelRequest, user: Principal = Depends(principal)):
        session = _own_session(body.session_id, user)
        async with locks.setdefault(session.session_id, asyncio.Lock()):
            session = _own_session(body.session_id, user)
            return _result(cancel(cfg, store=store, principal=user, session=session, pending_id=pending_id, now=now))

    return app
