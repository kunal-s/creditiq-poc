"""Intent router: pick one use case, fill its slots, or ask / decline.

The model sees the catalogue (ids, titles, examples, slot names) and the message, nothing else. Everything after its
answer is decided here, outside the model: unknown ids decline, low confidence asks one clarifying question, a user
without the use case's permissions is told so, the open case beats a case named in the text (config `context_wins`),
and a required slot that is still missing becomes one question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from .config import CopilotConfig, UseCase
from .identity import Principal
from .recording import sampling_settings
from .store import Session

Kind = Literal["use_case", "ask", "clarify", "decline", "forbidden", "context_differs"]


class RouterAnswer(BaseModel):
    use_case: str | None = Field(None, description="Id of the best-fitting use case, or null if none fits")
    confidence: float = Field(ge=0, le=1)
    slots: dict[str, str] = Field(default_factory=dict, description="Values stated in the message, by slot name")


@dataclass(frozen=True)
class Route:
    kind: Kind
    use_case: str | None = None
    slots: dict = field(default_factory=dict)
    pending_slot: str | None = None
    message: str = ""  # the question or notice to show for every kind except use_case
    confidence: float | None = None


def catalogue(cfg: CopilotConfig) -> str:
    lines = []
    for u in cfg.registry.use_cases:
        slots = ", ".join(u.required_slots + u.optional_slots) or "none"
        ex = "; ".join(u.examples)
        lines.append(f"- {u.id}: {u.title}. Slots: {slots}. Examples: {ex}")
    return "\n".join(lines)


def _instructions(cfg: CopilotConfig, active: str | None) -> str:
    text = cfg.prompts[cfg.runtime.router.prompt].strip() + "\n\nUse cases:\n" + catalogue(cfg)
    if active:
        text += f"\n\nThe conversation is currently about: {active}."
    return text


async def route(cfg: CopilotConfig, model: Model, principal: Principal, session: Session, message: str) -> Route:
    msgs = cfg.runtime.messages

    # An answer to a question we just asked continues the same use case, without a model call.
    if session.pending_slot and session.active_use_case:
        uc = cfg.use_case(session.active_use_case)
        slots = {**session.resolved_slots, session.pending_slot: message.strip()}
        return _finish(cfg, uc, principal, session, slots, 1.0)

    agent = Agent(model, output_type=RouterAnswer, instructions=_instructions(cfg, session.active_use_case),
                  model_settings=sampling_settings(cfg.llm))
    ans = (await agent.run(message)).output

    ids = {u.id for u in cfg.registry.use_cases}
    if ans.use_case not in ids:
        return Route("decline", message=msgs.decline, confidence=ans.confidence)
    if ans.confidence < cfg.runtime.router.confidence_threshold:
        return Route("clarify", message=msgs.clarify, confidence=ans.confidence)
    uc = cfg.use_case(ans.use_case)
    declared = set(uc.required_slots) | set(uc.optional_slots)
    stated = {k: v.strip() for k, v in ans.slots.items() if k in declared and v and v.strip()}
    # Slots the open screen supplies are re-read every turn: the open case may have changed since the last one.
    keep = {k: v for k, v in session.resolved_slots.items() if k not in uc.context_slots} if session.active_use_case == uc.id else {}
    return _finish(cfg, uc, principal, session, {**keep, **stated}, ans.confidence)


def _finish(cfg: CopilotConfig, uc: UseCase, principal: Principal, session: Session, slots: dict, conf: float) -> Route:
    msgs = cfg.runtime.messages
    if not principal.can(uc.permissions):
        return Route("forbidden", uc.id, message=msgs.forbidden, confidence=conf)
    for slot, key in uc.context_slots.items():
        open_value = session.context.get(key)
        if open_value in (None, ""):
            continue
        named = slots.get(slot)
        if named and str(named) != str(open_value):
            if cfg.runtime.context_wins:
                return Route("context_differs", uc.id, message=msgs.context_case_differs.format(open=open_value, named=named), confidence=conf)
            continue  # the named value wins
        slots[slot] = str(open_value)
    for slot in uc.required_slots:
        if not slots.get(slot):
            return Route("ask", uc.id, slots, pending_slot=slot, message=uc.slot_questions[slot], confidence=conf)
    return Route("use_case", uc.id, slots, confidence=conf)
