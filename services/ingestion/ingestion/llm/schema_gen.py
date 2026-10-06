"""JSON schemas for the model's answers, generated from the document types (strict mode: every
property required, no extras)."""

from __future__ import annotations

from ..config.models import FieldDef


def _scalar() -> dict:
    return {"type": ["string", "null"]}


def value_schema(f: FieldDef) -> dict:
    if f.type == "array":
        if f.items and f.items.type == "object":
            props = {s.name: _scalar() for s in f.items.fields}
            return {"type": "array", "items": {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}}
        return {"type": "array", "items": {"type": "string"}}
    return _scalar()


def extract_schema(fields: list[FieldDef]) -> dict:
    per = {f.name: {"type": "object", "properties": {"value": value_schema(f), "line_ids": {"type": "array", "items": {"type": "string"}}},
                    "required": ["value", "line_ids"], "additionalProperties": False} for f in fields}
    return {"type": "object", "properties": {"fields": {"type": "object", "properties": per, "required": list(per), "additionalProperties": False}},
            "required": ["fields"], "additionalProperties": False}


def classify_schema(type_ids: list[str]) -> dict:
    return {"type": "object", "properties": {"type": {"type": "string", "enum": [*type_ids, "none_of_these"]}, "reason": {"type": "string"}},
            "required": ["type", "reason"], "additionalProperties": False}
