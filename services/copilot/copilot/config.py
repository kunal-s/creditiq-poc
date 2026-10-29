"""Configuration models and loader. Everything the assistant does is set here; nothing is read from code.

A configuration directory holds host.yaml, llm.yaml, tools.yaml, registry.yaml, runtime.yaml and prompts/*.md.
It is loaded once, validated across sections, hashed, and frozen. Nothing in this service writes it (CLAUDE.md rule 4).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Kind = Literal["read", "draft", "act"]
PLACEHOLDER = re.compile(r"\{(\w+)\}")
RESERVED_SLOTS = {"pending_id"}  # filled by the runtime for an act tool: the id of the confirmed action, used as its idempotency key


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConfigError(ValueError):
    pass


class IdentityFields(_M):
    """Names of the fields in the host's identity response."""

    id: str = "id"
    role: str = "role"
    permissions: str = "permissions"


class HostConfig(_M):
    base_url: str
    identity_path: str  # GET with the user's bearer token; returns the user's id, role and permissions
    identity_fields: IdentityFields = IdentityFields()
    identity_timeout_s: float = Field(5, gt=0)
    cors_origins: list[str] = []
    context_keys: list[str] = []  # keys the client may send in `context` (e.g. case_id); others are dropped


class LlmConfig(_M):
    provider: Literal["openai"] = "openai"
    base_url: str
    api_key_env: str
    router_model: str
    runner_model: str
    temperature: float = 0
    seed: int = 1
    timeout_s: float = Field(60, gt=0)
    max_retries: int = Field(2, ge=0)


class ToolParam(_M):
    type: Literal["string", "integer", "boolean"] = "string"
    description: str
    required: bool = True
    from_slot: str | None = None  # filled by the runtime from the resolved slot; hidden from the model


class ToolSpec(_M):
    name: str
    kind: Kind
    description: str  # says when to use it and when not to
    method: Literal["GET", "POST"] = "GET"
    path: str  # relative to host.base_url; {param} placeholders
    params: dict[str, ToolParam] = {}
    timeout_s: float = Field(15, gt=0)
    row_limit: int = Field(200, gt=0)
    result_fields: list[str] = []  # keep only these keys of each result row (none listed: keep all); drops ids and noise

    @model_validator(mode="after")
    def _placeholders(self):
        missing = set(PLACEHOLDER.findall(self.path)) - set(self.params)
        if missing:
            raise ValueError(f"tool {self.name}: path placeholders without params: {sorted(missing)}")
        return self


class ToolsConfig(_M):
    tools: list[ToolSpec]


class OutputSpec(_M):
    format: Literal["text", "table", "draft"] = "text"  # a draft is text the panel shows as a message preview, with a copy button
    columns: list[str] = []

    @model_validator(mode="after")
    def _cols(self):
        if self.format == "table" and not self.columns:
            raise ValueError("a table output needs columns")
        return self


class ActSpec(_M):
    """How an act use case turns the user's draft into one confirmed call. The model takes no part in it."""

    tool: str  # the act tool; it runs only after the user confirms, with the values on the confirmation card
    from_draft: str  # the draft use case whose most recent draft the card is filled from
    draft_marker: str = "Draft - not sent"  # first line of a draft; not part of the message
    subject_marker: str = "Subject:"  # the line that starts the message; everything after it is the body
    blocked_pattern: str | None = None  # a regular expression; text that still matches it cannot be sent (unfilled placeholders)
    confirm_text: str  # the reply that shows the confirmation card
    needs_draft: str  # the reply when there is no live draft to act on
    done: str  # {to} is filled
    blocked: str  # shown on the card when `blocked_pattern` matches

    @model_validator(mode="after")
    def _pattern(self):
        if self.blocked_pattern:
            try:
                re.compile(self.blocked_pattern)
            except re.error as e:
                raise ValueError(f"blocked_pattern: {e}") from None
        return self


class UseCase(_M):
    id: str
    title: str
    kind: Kind
    examples: list[str] = Field(min_length=1)
    required_slots: list[str] = []
    optional_slots: list[str] = []
    context_slots: dict[str, str] = {}  # slot -> context key supplying it (the open case)
    tools: list[str] = Field(min_length=1)
    max_steps: int = Field(gt=0)
    permissions: list[str] = Field(min_length=1)  # host permission names; the user needs all
    prompt: str = ""  # file in prompts/; an act use case has none (no model runs for it)
    act: ActSpec | None = None  # required for kind "act", not allowed otherwise
    output: OutputSpec = OutputSpec()
    confirmation: Literal["none", "user"] = "none"
    follow_ups: list[str] = []  # next steps offered under a real answer, each worded as the user would type it
    empty_message: str | None = None  # the reply when every lookup succeeds but returns nothing; the model's text is not used
    slot_questions: dict[str, str] = {}  # slot -> question to ask when it is missing


class RegistryConfig(_M):
    use_cases: list[UseCase]


class RouterConfig(_M):
    prompt: str
    confidence_threshold: float = Field(ge=0, le=1)


class SessionConfig(_M):
    history_token_limit: int = Field(gt=0)
    summary_threshold: int = Field(gt=0)
    pending_action_ttl_s: int = Field(gt=0)
    max_message_chars: int = Field(2000, gt=0)


class GuardsConfig(_M):
    block_repeat_calls: bool = True
    ground_table_cells: bool = True  # every table cell must appear in the tool results
    default_max_steps: int = Field(4, gt=0)


class ReasonsConfig(_M):
    """Fills {missing} in messages.cannot_do."""

    step_limit: str
    repeat_call: str
    no_data: str
    ungrounded: str


class MessagesConfig(_M):
    reasons: ReasonsConfig
    decline: str
    clarify: str
    cannot_do: str  # {found} / {missing} are filled by the runner
    forbidden: str
    context_case_differs: str  # {open} / {named}
    action_expired: str  # a confirmation that lapsed, or belongs to another case
    action_cancelled: str


class RuntimeConfig(_M):
    router: RouterConfig
    session: SessionConfig
    guards: GuardsConfig = GuardsConfig()
    context_wins: bool = True  # the open case beats a case named in the text
    messages: MessagesConfig


class CopilotConfig(_M):
    host: HostConfig
    llm: LlmConfig
    tools: ToolsConfig
    registry: RegistryConfig
    runtime: RuntimeConfig
    prompts: dict[str, str]
    hash: str

    def tool(self, name: str) -> ToolSpec:
        return next(t for t in self.tools.tools if t.name == name)

    def use_case(self, uid: str) -> UseCase:
        return next(u for u in self.registry.use_cases if u.id == uid)

    def act_for(self, draft_id: str) -> UseCase | None:
        """The act use case that sends what the given draft use case writes."""
        return next((u for u in self.registry.use_cases if u.act and u.act.from_draft == draft_id), None)


SECTIONS = {"host": HostConfig, "llm": LlmConfig, "tools": ToolsConfig, "registry": RegistryConfig, "runtime": RuntimeConfig}


def _cross_check(host: HostConfig, tools: ToolsConfig, reg: RegistryConfig, rt: RuntimeConfig, prompts: dict[str, str]) -> None:
    errs: list[str] = []
    names = [t.name for t in tools.tools]
    if len(set(names)) != len(names):
        errs.append("duplicate tool names")
    by_name = {t.name: t for t in tools.tools}
    ids = [u.id for u in reg.use_cases]
    if len(set(ids)) != len(ids):
        errs.append("duplicate use case ids")
    if rt.router.prompt not in prompts:
        errs.append(f"router prompt {rt.router.prompt!r} not found in prompts/")
    for u in reg.use_cases:
        slots = set(u.required_slots) | set(u.optional_slots)
        if u.kind != "act" and u.prompt not in prompts:
            errs.append(f"{u.id}: prompt {u.prompt!r} not found in prompts/")
        if (u.kind == "act") != (u.act is not None):
            errs.append(f"{u.id}: `act` is required for an act use case and only allowed there")
        if u.act:
            a = u.act
            t = by_name.get(a.tool)
            if a.tool not in u.tools or t is None or t.kind != "act":
                errs.append(f"{u.id}: act.tool {a.tool!r} must be an act tool the use case lists")
            elif not any(not p.from_slot for p in t.params.values()):
                errs.append(f"{u.id}: act tool {a.tool} has no fields for the user to confirm")
            d = next((x for x in reg.use_cases if x.id == a.from_draft), None)
            if d is None or d.kind != "draft":
                errs.append(f"{u.id}: act.from_draft {a.from_draft!r} must be a draft use case")
            elif d.context_slots != u.context_slots:
                errs.append(f"{u.id}: act and its draft must take the same context slots")
            if sum(1 for x in reg.use_cases if x.act and x.act.from_draft == a.from_draft) > 1:
                errs.append(f"{u.id}: more than one act use case sends the draft of {a.from_draft}")
        for tn in u.tools:
            t = by_name.get(tn)
            if t is None:
                errs.append(f"{u.id}: unknown tool {tn!r}")
                continue
            if u.kind == "read" and t.kind != "read":
                errs.append(f"{u.id}: a read use case cannot use the {t.kind} tool {tn}")
            if u.kind != "act" and t.kind == "act":
                errs.append(f"{u.id}: only an act use case can use the act tool {tn}")
            for pn, p in t.params.items():
                if p.from_slot and p.from_slot not in slots and p.from_slot not in RESERVED_SLOTS:
                    errs.append(f"{u.id}: tool {tn} param {pn} needs slot {p.from_slot!r} the use case does not declare")
        used = {p.from_slot for tn in u.tools if tn in by_name for p in by_name[tn].params.values() if p.from_slot}
        for slot in sorted(slots - used):
            errs.append(f"{u.id}: slot {slot!r} is not used by any of its tools")
        if u.kind == "act" and u.confirmation != "user":
            errs.append(f"{u.id}: an act use case must require user confirmation")
        for slot, key in u.context_slots.items():
            if slot not in slots:
                errs.append(f"{u.id}: context slot {slot!r} is not a declared slot")
            if key not in host.context_keys:
                errs.append(f"{u.id}: context key {key!r} is not listed in host.context_keys")
        for slot in u.required_slots:
            if slot not in u.slot_questions and slot not in u.context_slots:
                errs.append(f"{u.id}: required slot {slot!r} has no slot_questions entry")
    if errs:
        raise ConfigError("; ".join(errs))


def _read(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"missing configuration file {path.name} in {path.parent}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"{path.name}: {e}") from None


def load_dir(path: Path | str) -> CopilotConfig:
    path = Path(path)
    raw = {k: _read(path / f"{k}.yaml") for k in SECTIONS}
    prompts = {p.name: p.read_text(encoding="utf-8") for p in sorted((path / "prompts").glob("*.md"))}
    try:
        built = {k: SECTIONS[k].model_validate(v) for k, v in raw.items()}
    except Exception as e:  # pydantic ValidationError carries the field paths
        raise ConfigError(str(e)) from None
    _cross_check(built["host"], built["tools"], built["registry"], built["runtime"], prompts)
    digest = hashlib.sha256(json.dumps([raw, prompts], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return CopilotConfig(**built, prompts=prompts, hash=digest)
