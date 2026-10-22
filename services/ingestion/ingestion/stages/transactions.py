"""Filing bank-statement transactions under a closed list of categories with the model.

This runs only for the narrations the engine's rules could not settle. The engine sends the categories it
publishes and the narrations; the model picks one category per transaction (or "unknown") and says how sure it
is. It never supplies an amount, a date or a name, and a key it was not given is dropped. Narrations are data:
they are passed as JSON lines and the prompt tells the model to ignore anything written in them."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from ..config.models import IngestionConfig
from ..llm.provider import ModelRequest
from ..llm.recorder import ModelClient

UNKNOWN = "unknown"
CONFIDENCE = ("high", "medium", "low")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


class Category(BaseModel):
    id: str
    direction: str
    label: str


class Item(BaseModel):
    key: str
    direction: str
    narration: str
    amount: float = 0


class ClassifyRequest(BaseModel):
    config_version: str = "dev"
    categories: list[Category]
    items: list[Item] = Field(max_length=2000)


class Result(BaseModel):
    key: str
    category: str
    confidence: str
    reason: str


class ClassifyResponse(BaseModel):
    model: str
    calls: int
    results: list[Result]


def _schema(ids: list[str]) -> dict:
    row = {"type": "object",
           "properties": {"key": {"type": "string"}, "category": {"type": "string", "enum": [*ids, UNKNOWN]},
                          "confidence": {"type": "string", "enum": list(CONFIDENCE)}, "reason": {"type": "string"}},
           "required": ["key", "category", "confidence", "reason"], "additionalProperties": False}
    return {"type": "object", "properties": {"results": {"type": "array", "items": row}}, "required": ["results"],
            "additionalProperties": False}


def _clean(text: str) -> str:
    return _CONTROL.sub(" ", text).strip()[:240]


def classify(cfg: IngestionConfig, model: ModelClient, req: ClassifyRequest) -> ClassifyResponse:
    pr = cfg.llm.prompts["transactions"]
    size = cfg.llm.transactions.batch_size
    out: list[Result] = []
    calls_before = model.calls
    for direction in ("credit", "debit"):
        cats = [c for c in req.categories if c.direction == direction]
        items = [i for i in req.items if i.direction == direction]
        if not cats or not items:
            for i in items:
                out.append(Result(key=i.key, category=UNKNOWN, confidence="low", reason="no categories for this direction"))
            continue
        ids = [c.id for c in cats]
        system = pr.system.strip()
        listing = "\n".join(f"- {c.id}: {c.label}" for c in cats)
        for start in range(0, len(items), size):
            batch = items[start:start + size]
            lines = "\n".join(json.dumps({"key": i.key, "amount": round(i.amount), "narration": _clean(i.narration)},
                                          ensure_ascii=False) for i in batch)
            user = pr.user.replace("{{direction}}", direction).replace("{{categories}}", listing).replace("{{items}}", lines).strip()
            answer = model.call(ModelRequest("transactions", system, user, _schema(ids)))
            given = {i.key for i in batch}
            seen: set[str] = set()
            for r in answer.get("results", []):
                key = r.get("key")
                if key not in given or key in seen:
                    continue    # a key it was not given, or a second answer for one: ignored
                seen.add(key)
                out.append(Result(key=key, category=r["category"], confidence=r["confidence"], reason=_clean(r["reason"])[:120]))
            for i in batch:
                if i.key not in seen:
                    out.append(Result(key=i.key, category=UNKNOWN, confidence="low", reason="the model gave no answer"))
    order = {i.key: n for n, i in enumerate(req.items)}
    out.sort(key=lambda r: order.get(r.key, 0))
    return ClassifyResponse(model=model.name, calls=model.calls - calls_before, results=out)
