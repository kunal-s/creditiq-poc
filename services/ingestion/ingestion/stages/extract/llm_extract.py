"""The model pass (FRD F-15.2): fills only what the deterministic pass left empty.

The model sees numbered lines and returns, per field, the value as printed and the ids of the
lines it was copied from. Code then verifies the value against those lines (F-15.4): a value that
cannot be found there is rejected, and the field stays missing. The model never supplies a page
or a position, and its own confidence is not used."""

from __future__ import annotations

from ...config.models import FieldDef, IngestionConfig
from ...llm.provider import ModelError, ModelRequest
from ...llm.recorder import ModelClient
from ...llm.schema_gen import extract_schema
from ...pageindex import Line, Page
from ...util import fold
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


def _verify(raw: str, text_f: str) -> bool:
    return bool(raw) and fold(raw) in text_f


def fill(cfg: IngestionConfig, type_name: str, fields: list[FieldDef], hints: dict[str, str | None], pages: list[Page],
         model: ModelClient) -> tuple[dict[str, Found], dict[str, str], list[dict]]:
    """Returns (found, reasons for fields the model could not supply, trace entries)."""
    pending = {f.name: f for f in fields}
    found: dict[str, Found] = {}
    reasons: dict[str, str] = {}
    trace: list[dict] = []
    pr = cfg.llm.prompts["extract"]
    for win in windows(pages, cfg.llm.window_chars):
        if not pending:
            break
        by_id: dict[str, tuple[Page, Line]] = {l.id: (p, l) for p in win for l in p.content_lines()}
        user = pr.user.replace("{{fields}}", "\n".join(_field_line(f, hints.get(f.name)) for f in pending.values()))
        user = user.replace("{{lines}}", "\n".join(f"{i}: {l.text}" for i, (_, l) in by_id.items())).strip()
        system = pr.system.replace("{{type_name}}", type_name).strip()
        req = ModelRequest("extract", system, user, extract_schema(list(pending.values())))
        try:
            ans = model.call(req)
        except ModelError as e:
            for n in pending:
                reasons[n] = f"model_unavailable:{e.code}"
            trace.append({"call": "extract", "error": e.code, "message": str(e)[:200]})
            return found, reasons, trace
        got = (ans or {}).get("fields", {})
        for name, f in list(pending.items()):
            ent = got.get(name) or {}
            val, ids = ent.get("value"), ent.get("line_ids") or []
            if val in (None, "", []):
                continue
            if not ids or any(i not in by_id for i in ids):
                reasons[name] = "bad_evidence"
                trace.append({"field": name, "rejected": "bad_evidence", "value": val})
                continue
            ev_text = fold(" ".join(by_id[i][1].text for i in ids))
            elems = val if isinstance(val, list) else [val]
            raws = [(e.get("name") or next(iter(e.values()), "")) if isinstance(e, dict) else str(e) for e in elems]
            ok = [r for r in raws if _verify(str(r), ev_text)]
            if not ok:
                reasons[name] = "not_found_on_page"
                trace.append({"field": name, "rejected": "not_found_on_page", "value": val})
                continue
            parts = []
            for i in ids:
                page, line = by_id[i]
                needle = str(ok[0])
                pos = line.text.casefold().find(needle.casefold())
                parts.append((page, line, pos, pos + len(needle)) if pos >= 0 else (page, line, 0, len(line.text)))
            page0 = parts[0][0]
            ev = evidence_for_lines(page0, [(l, a, b) for (pg, l, a, b) in parts if pg is page0])
            ev.line_ids = list(ids)
            if f.type == "array":
                if f.items and f.items.type == "object":
                    keys = [s.name for s in f.items.fields]
                    value_raw = [e if isinstance(e, dict) else {keys[0]: e} for e in elems if (e.get(keys[0]) if isinstance(e, dict) else e) in ok]
                    found[name] = Found(value_raw, "model", ev)
                else:
                    found[name] = Found(ok, "model", ev)
            else:
                found[name] = Found(str(ok[0]), "model", ev)
            del pending[name]
            reasons.pop(name, None)
    return found, reasons, trace
