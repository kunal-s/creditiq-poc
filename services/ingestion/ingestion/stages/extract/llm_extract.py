"""The model pass (FRD F-15.2): fills only what the deterministic pass left empty.

The model sees numbered lines and returns, per field, the value as printed and the ids of the
lines it was copied from. Code then verifies the value against those lines (F-15.4): a value that
cannot be found there is rejected, and the field stays missing. The model never supplies a page
or a position, and its own confidence is not used."""

from __future__ import annotations

import re

from ...config.models import FieldDef, IngestionConfig
from ...llm.provider import ModelError, ModelRequest
from ...llm.recorder import ModelClient
from ...llm.schema_gen import extract_schema
from ...pageindex import Line, Page
from ...util import fold
from . import printed
from .evidence import Evidence, evidence_for_lines
from .fields import Found


def windows(pages: list[Page], limit: int) -> list[list[Page]]:
    out, cur, size = [], [], 0
    for p in pages:
        n = sum(len(l.text) + 12 for l in p.content_lines())
        if cur and size + n > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += n
    if cur:
        out.append(cur)
    return out


def _field_line(f: FieldDef, hint: str | None) -> str:
    kind = f.type
    if f.type == "array":
        kind = "list of objects with keys " + ", ".join(s.name for s in (f.items.fields if f.items else [])) if f.items and f.items.type == "object" else "list of strings"
    return f"- {f.name} ({kind}){': ' + (hint or f.description) if (hint or f.description) else ''}"


def _locate(raw: str, ids: list[str], by_id: dict[str, tuple[Page, Line]], ratio: float) -> tuple[str, dict] | None:
    """The text the named lines print for `raw` (Story 6.6), and where: on one line, or across the lines joined (a
    value that wraps)."""
    spans = {}
    for i in ids:
        hit = printed.find(raw, by_id[i][1].text, ratio)
        if hit is not None:
            spans[i] = hit
            return by_id[i][1].text[hit[0]:hit[1]], spans
    joined = " ".join(by_id[i][1].text for i in ids)
    hit = printed.find(raw, joined, ratio)
    if hit is not None:
        return joined[hit[0]:hit[1]], {}
    # A value that wraps onto the next line, where the model named only the line it starts on.
    for i in ids:
        page, line = by_id[i]
        lines = page.content_lines()
        at = next((k for k, x in enumerate(lines) if x.id == line.id), None)
        if at is None or at + 1 >= len(lines):
            continue
        both = f"{line.text} {lines[at + 1].text}"
        hit = printed.find(raw, both, ratio)
        if hit is not None:
            return both[hit[0]:hit[1]], {}
    return None


def ground(val, ids: list[str], by_id: dict[str, tuple[Page, Line]], ratio: float = 90
           ) -> tuple[list, list[str], Evidence, dict[str, str]] | str:
    """A model's value checked against the lines it names (F-15.4, Story 6.6): the elements, the raw values found
    there, their evidence, and for each the text as printed; or the reason it is rejected (bad_evidence,
    not_found_on_page)."""
    if not ids or any(i not in by_id for i in ids):
        return "bad_evidence"
    elems = val if isinstance(val, list) else [val]
    raws = [(e.get("name") or next(iter(e.values()), "")) if isinstance(e, dict) else str(e) for e in elems]
    shown: dict[str, str] = {}
    spans: dict = {}
    for r in raws:
        got = _locate(str(r), ids, by_id, ratio)
        if got is not None:
            shown[str(r)] = got[0]
            if not spans:
                spans = got[1]
    ok = [r for r in raws if str(r) in shown]
    if not ok:
        return "not_found_on_page"
    parts = []
    for i in ids:
        page, line = by_id[i]
        a, b = spans.get(i, (0, len(line.text)))
        parts.append((page, line, a, b))
    page0 = parts[0][0]
    ev = evidence_for_lines(page0, [(l, a, b) for (pg, l, a, b) in parts if pg is page0])
    ev.line_ids = list(ids)
    return elems, ok, ev, shown


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", fold(label).lower()).strip("_")[:40] or "field"


def discover_schema() -> dict:
    item = {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"},
                                              "line_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["label", "value", "line_ids"], "additionalProperties": False}
    return {"type": "object", "properties": {"fields": {"type": "array", "items": item}}, "required": ["fields"],
            "additionalProperties": False}


def discover(cfg: IngestionConfig, type_name: str, description: str | None, pages: list[Page],
             model: ModelClient) -> tuple[dict[str, tuple[str, Found]], list[dict]]:
    """The model proposes a case document type's key fields (F-15.8): {name: (label, found)}, at most the
    configured number, each value checked on its page like any other. A label met again keeps its first value,
    and a value met again on the same lines under another label is the same fact, reported once."""
    limit = cfg.llm.discover_max_fields
    pr = cfg.llm.prompts["discover"]
    found: dict[str, tuple[str, Found]] = {}
    facts: set[tuple[str, tuple[str, ...]]] = set()
    trace: list[dict] = []
    system = (pr.system.replace("{{type_name}}", type_name).replace("{{description}}", description or "")
              .replace("{{max}}", str(limit)).strip())
    for win in windows(pages, cfg.llm.window_chars):
        if len(found) >= limit:
            break
        by_id: dict[str, tuple[Page, Line]] = {l.id: (p, l) for p in win for l in p.content_lines()}
        user = pr.user.replace("{{lines}}", "\n".join(f"{i}: {l.text}" for i, (_, l) in by_id.items())).strip()
        try:
            ans = model.call(ModelRequest("discover", system, user, discover_schema()))
        except ModelError as e:
            trace.append({"call": "discover", "error": e.code, "message": str(e)[:200]})
            break
        for ent in (ans or {}).get("fields", []):
            label, val, ids = str(ent.get("label") or "").strip(), ent.get("value"), ent.get("line_ids") or []
            if not label or val in (None, ""):
                continue
            name, fact = _slug(label), (fold(str(val)), tuple(ids))
            if name in found or fact in facts or len(found) >= limit:
                continue
            grounded = ground(str(val), ids, by_id, cfg.llm.evidence_text_ratio)
            if isinstance(grounded, str):
                trace.append({"field": name, "rejected": grounded, "value": val})
                continue
            _, ok, ev, shown = grounded
            found[name] = (label, Found(shown[str(ok[0])], "model", ev))
            facts.add(fact)
    return found, trace


def fill(cfg: IngestionConfig, type_name: str, fields: list[FieldDef], hints: dict[str, str | None], pages: list[Page],
         model: ModelClient, prompt: str = "extract", subs: dict[str, str] | None = None) -> tuple[dict[str, Found], dict[str, str], list[dict]]:
    """Returns (found, reasons for fields the model could not supply, trace entries). `prompt` names the
    configured prompt and the task; `subs` fills its other placeholders (the second pass names the file's type)."""
    pending = {f.name: f for f in fields}
    found: dict[str, Found] = {}
    reasons: dict[str, str] = {}
    trace: list[dict] = []
    pr = cfg.llm.prompts[prompt]
    for win in windows(pages, cfg.llm.window_chars):
        if not pending:
            break
        by_id: dict[str, tuple[Page, Line]] = {l.id: (p, l) for p in win for l in p.content_lines()}
        user = pr.user.replace("{{fields}}", "\n".join(_field_line(f, hints.get(f.name)) for f in pending.values()))
        user = user.replace("{{lines}}", "\n".join(f"{i}: {l.text}" for i, (_, l) in by_id.items())).strip()
        system = pr.system.replace("{{type_name}}", type_name)
        for k, v in (subs or {}).items():
            system = system.replace("{{%s}}" % k, v)
        req = ModelRequest(prompt, system.strip(), user, extract_schema(list(pending.values())))
        try:
            ans = model.call(req)
        except ModelError as e:
            for n in pending:
                reasons[n] = f"model_unavailable:{e.code}"
            trace.append({"call": prompt, "error": e.code, "message": str(e)[:200]})
            return found, reasons, trace
        got = (ans or {}).get("fields", {})
        for name, f in list(pending.items()):
            ent = got.get(name) or {}
            val, ids = ent.get("value"), ent.get("line_ids") or []
            if val in (None, "", []):
                continue
            grounded = ground(val, ids, by_id, cfg.llm.evidence_text_ratio)
            if isinstance(grounded, str):
                reasons[name] = grounded
                trace.append({"field": name, "rejected": grounded, "value": val})
                continue
            elems, ok, ev, shown = grounded
            if f.type == "array":
                if f.items and f.items.type == "object":
                    keys = [s.name for s in f.items.fields]
                    value_raw = [e if isinstance(e, dict) else {keys[0]: e} for e in elems if (e.get(keys[0]) if isinstance(e, dict) else e) in ok]
                    found[name] = Found(value_raw, "model", ev)
                else:
                    found[name] = Found([shown[str(r)] for r in ok], "model", ev)
            else:
                found[name] = Found(shown[str(ok[0])], "model", ev)
            del pending[name]
            reasons.pop(name, None)
    return found, reasons, trace
