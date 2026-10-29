"""Typed tools bound to the host's endpoints by configuration.

A tool call is: validate the model's arguments against the configured parameters, add the slot-filled parameters
(hidden from the model), call the host with the user's own bearer token, and return a typed result. Identity comes
from the Principal the runtime holds; the model can neither see nor set it. Failures are returned, not raised, as one
of a few typed errors that each say what to do next, so the runner can count them and the model can adapt.
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from pydantic_ai import RunContext
from pydantic_ai.tools import Tool

from .config import PLACEHOLDER, CopilotConfig, ToolParam, ToolSpec
from .identity import Principal

ErrorCode = Literal["NOT_FOUND", "NEEDS_INPUT", "FORBIDDEN", "UNAVAILABLE"]
_NEXT = {
    "NOT_FOUND": "Nothing matches. Do not retry with the same arguments; tell the user what was not found.",
    "NEEDS_INPUT": "The request was missing or had an invalid value. Fix the arguments or ask the user for it.",
    "FORBIDDEN": "The user may not see this. Do not retry; say they do not have access.",
    "UNAVAILABLE": "The source could not be reached. Do not retry in this turn; say what is missing.",
}
_PY = {"string": str, "integer": int, "boolean": bool}


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ok: bool
    data: Any = None
    error: ErrorCode | None = None
    message: str = ""
    truncated: bool = False
    fetched_at: str = ""

    def for_model(self) -> dict:
        if self.ok:
            return {"data": self.data, **({"truncated": True} if self.truncated else {})}
        return {"error": self.error, "next": f"{_NEXT[self.error]} {self.message}".strip()}


@dataclass
class ToolDeps:
    """What the runtime holds for a turn; the model sees none of it."""

    principal: Principal
    slots: dict
    caller: ToolCaller
    calls: list[dict] = field(default_factory=list)  # name, args, outcome: read by the runner and the trace
    max_steps: int = 99
    block_repeat: bool = True
    steps: int = 0
    seen: set = field(default_factory=set)
    results: list = field(default_factory=list)  # data from successful calls: the evidence for grounding


class ToolBlocked(Exception):
    """A guard stopped the call. The turn ends; the model cannot argue with it."""

    def __init__(self, reason: Literal["step_limit", "repeat_call"]):
        super().__init__(reason)
        self.reason = reason


def _fail(spec: ToolSpec, code: ErrorCode, message: str = "") -> ToolResult:
    return ToolResult(spec.name, False, error=code, message=message)


def _json_schema(spec: ToolSpec) -> dict:
    visible = {n: p for n, p in spec.params.items() if not p.from_slot}
    return {
        "type": "object",
        "properties": {n: {"type": p.type, "description": p.description} for n, p in visible.items()},
        "required": [n for n, p in visible.items() if p.required],
        "additionalProperties": False,
    }


def _check(p: ToolParam, v: Any) -> bool:
    return isinstance(v, _PY[p.type]) and not (p.type == "integer" and isinstance(v, bool))


def _project(data: Any, fields: list[str]) -> Any:
    """Keep only the listed keys of each row, so the model sees what it needs and nothing that varies between runs."""
    if not fields:
        return data
    if isinstance(data, list):
        return [_project(row, fields) for row in data]
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in fields}
    return data


def _limit(data: Any, n: int) -> tuple[Any, bool]:
    if isinstance(data, list):
        return data[:n], len(data) > n
    if isinstance(data, dict):
        out, cut = {}, False
        for k, v in data.items():
            if isinstance(v, list) and len(v) > n:
                v, cut = v[:n], True
            out[k] = v
        return out, cut
    return data, False


def _detail(r: httpx.Response) -> str:
    """The host's own words for what to fix, when it gave a sentence (a validation list is not one)."""
    try:
        d = r.json().get("detail")
    except (ValueError, AttributeError):
        return ""
    return d[:200] if isinstance(d, str) else ""


class ToolCaller:
    def __init__(self, cfg: CopilotConfig, client: httpx.AsyncClient | None = None, now: Callable[[], str] = lambda: ""):
        self._cfg, self._now = cfg, now
        self._client = client or httpx.AsyncClient(base_url=cfg.host.base_url)

    async def call(self, spec: ToolSpec, principal: Principal, slots: dict, args: dict) -> ToolResult:
        visible = {n for n, p in spec.params.items() if not p.from_slot}
        if set(args) - visible:
            return _fail(spec, "NEEDS_INPUT", f"Unknown arguments: {sorted(set(args) - visible)}.")
        values: dict[str, Any] = {}
        for n, p in spec.params.items():
            v = slots.get(p.from_slot) if p.from_slot else args.get(n)
            if v is None:
                if p.required:
                    return _fail(spec, "NEEDS_INPUT", f"{n} is required.")
                continue
            if not _check(p, v):
                return _fail(spec, "NEEDS_INPUT", f"{n} must be a {p.type}.")
            values[n] = v
        path = spec.path
        for n in set(PLACEHOLDER.findall(spec.path)):
            path = path.replace("{" + n + "}", urllib.parse.quote(str(values.pop(n)), safe=""))
        headers = {"Authorization": f"Bearer {principal.token}"}
        try:
            r = await self._client.request(
                spec.method, path, headers=headers, timeout=spec.timeout_s,
                **({"params": values} if spec.method == "GET" else {"json": values}),
            )
        except httpx.HTTPError as e:
            return _fail(spec, "UNAVAILABLE", type(e).__name__)
        if r.status_code in (401, 403):
            return _fail(spec, "FORBIDDEN")
        if r.status_code == 404:
            return _fail(spec, "NOT_FOUND")
        if r.status_code in (400, 409, 422):
            return _fail(spec, "NEEDS_INPUT", _detail(r) or f"The source answered {r.status_code}.")
        if r.status_code not in (200, 201):
            return _fail(spec, "UNAVAILABLE", f"The source answered {r.status_code}.")
        try:
            data, cut = _limit(_project(r.json(), spec.result_fields), spec.row_limit)
        except ValueError:
            return _fail(spec, "UNAVAILABLE", "Unreadable answer.")
        return ToolResult(spec.name, True, data, truncated=cut, fetched_at=self._now())


def build_tools(cfg: CopilotConfig, names: list[str]) -> list[Tool]:
    """Pydantic AI tools for the named specs. The model sees name, description and visible parameters only."""
    tools = []
    for name in names:
        spec = cfg.tool(name)

        async def run(ctx: RunContext[ToolDeps], _spec: ToolSpec = spec, **args: Any) -> dict:
            d = ctx.deps
            key = (_spec.name, json.dumps(args, sort_keys=True, default=str))
            blocked = "repeat_call" if d.block_repeat and key in d.seen else "step_limit" if d.steps >= d.max_steps else None
            if blocked:
                d.calls.append({"tool": _spec.name, "args": args, "ok": False, "error": "BLOCKED", "reason": blocked, "at": ""})
                raise ToolBlocked(blocked)
            d.steps += 1
            d.seen.add(key)
            res = await d.caller.call(_spec, d.principal, d.slots, args)
            if res.ok:
                d.results.append(res.data)
            d.calls.append({"tool": _spec.name, "args": args, "ok": res.ok, "error": res.error, "at": res.fetched_at})
            return res.for_model()

        tools.append(Tool.from_schema(run, name=spec.name, description=spec.description, json_schema=_json_schema(spec), takes_ctx=True))
    return tools
