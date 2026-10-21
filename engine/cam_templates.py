"""CAM templates (docs/functional-requirements.md F-23; FRD decision C.4-12): the layouts a draft CAM
can follow, and the one each appraisal follows.

The default is the configured layout (config/cam.yaml). Further templates are made by analysts and
kept, bank-wide, in the case store: a name, a description and its sections in order, each drafted
from parts of the file (the same parts the default draws on, each at most once) or left blank for
the analyst to write. A template only arranges what the engine drafts; it changes no rule, figure
or outcome. A template is never edited in place: a change is a new template, and every template
and every choice of one is kept with who and when, in the decision log too.

The risk assessment and the recommendation always close the memo, under the configured titles.
"""

from __future__ import annotations

import json
import re
import sqlite3

from .config import find_user_by_id
from .configstore.schema import CamPartDef, CamSectionConfig, CamSectionDef
from .db import log_decision
from .util import now_iso, stable_id

DEFAULT = "default"
MAX_SECTIONS = 15

# A part's title where the configured layout does not use it.
KIND_TITLES = {
    "snapshot": "Proposal at a glance", "borrower_profile": "Borrower profile", "promoters": "Promoters and management",
    "proposal": "Proposal and facilities", "financial_performance": "Financial performance",
    "working_capital": "Assessment of working-capital requirement",
    "turnover": "Turnover across sources (GST, income tax and banking)", "banking": "Banking and account conduct",
    "existing_facilities": "Existing facilities and obligations", "cross_verification": "Cross-verification of sources",
    "policy": "Compliance with policy norms", "documentation": "Documentation status",
}


class TemplateError(Exception):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def catalogue(config: CamSectionConfig) -> list[CamPartDef]:
    """Every part a template may draw on, with the id and title the configured layout gives it (so a
    part keeps the id it is linked by, whichever template it sits in)."""
    configured = {p.kind: p for s in config.sections for p in s.drafted_from()}
    return [configured.get(kind) or CamPartDef(id=kind, kind=kind, title=title) for kind, title in KIND_TITLES.items()]


def _name(user_id: str | None) -> str | None:
    user = find_user_by_id(user_id) if user_id else None
    return user.get("name") if user else None


def _default(config: CamSectionConfig) -> dict:
    return {"id": DEFAULT, "name": "Default template", "description": config.template_note or "",
            "default": True, "sections": config.sections, "created_by": None, "created_at": None}


def _row(r: sqlite3.Row, parts: dict[str, CamPartDef]) -> dict:
    sections = [CamSectionDef(id=s["id"], title=s["title"], purpose=s.get("purpose"),
                              parts=[parts[k] for k in s["parts"] if k in parts])
                for s in json.loads(r["sections"])]
    return {"id": r["id"], "name": r["name"], "description": r["description"], "default": False,
            "sections": sections, "created_by": r["created_by"], "created_at": r["created_at"]}


def templates(conn: sqlite3.Connection, config: CamSectionConfig) -> list[dict]:
    parts = {p.kind: p for p in catalogue(config)}
    return [_default(config)] + [_row(r, parts) for r in conn.execute(
        "SELECT * FROM cam_templates ORDER BY created_at")]


def get(conn: sqlite3.Connection, config: CamSectionConfig, template_id: str) -> dict:
    found = next((t for t in templates(conn, config) if t["id"] == template_id), None)
    if found is None:
        raise TemplateError(f"no template {template_id!r}", 404)
    return found


def for_case(conn: sqlite3.Connection, config: CamSectionConfig, case_id: str) -> dict:
    """The template the case's memo follows: the one chosen for it, else the default."""
    row = conn.execute("SELECT template_id FROM case_cam_templates WHERE case_id = ?", (case_id,)).fetchone()
    if row:
        try:
            return get(conn, config, row["template_id"])
        except TemplateError:
            pass
    return _default(config)


def _slug(title: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40] or "section"
    # Not a part's id, nor the closing sections', so links to a part still find it.
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}_{n}", n + 1
    taken.add(slug)
    return slug


def create(conn: sqlite3.Connection, config: CamSectionConfig, name: str, description: str,
           sections: list[dict], user: dict) -> dict:
    name = name.strip()
    if len(name) < 3:
        raise TemplateError("Give the template a name of at least 3 characters.")
    if any(t["name"].lower() == name.lower() for t in templates(conn, config)):
        raise TemplateError(f"A template named “{name}” already exists.", 409)
    if not 1 <= len(sections) <= MAX_SECTIONS:
        raise TemplateError(f"A template needs between 1 and {MAX_SECTIONS} sections.")
    kinds = {p.kind for p in catalogue(config)}
    used: set[str] = set()
    taken = {p.id for p in catalogue(config)} | {"summary", "recommendation"}
    out = []
    for s in sections:
        title = str(s.get("title") or "").strip()
        if not title:
            raise TemplateError("Every section needs a title.")
        parts = [str(k) for k in s.get("parts") or []]
        unknown = [k for k in parts if k not in kinds]
        if unknown:
            raise TemplateError(f"Unknown part {unknown[0]!r}.")
        twice = [k for k in parts if k in used]
        if twice or len(set(parts)) != len(parts):
            raise TemplateError(f"“{KIND_TITLES.get((twice or parts)[0], '')}” is drafted in one section only.")
        used.update(parts)
        out.append({"id": _slug(title, taken), "title": title, "purpose": str(s.get("purpose") or "").strip() or None,
                    "parts": parts})
    at = now_iso()
    tid = stable_id("TPL", name, at)
    conn.execute("INSERT INTO cam_templates (id, name, description, sections, created_by, created_at) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (tid, name, description.strip(), json.dumps(out), user["id"], at))
    log_decision(conn, at=at, actor=user["id"], action="cam.template_created", case_id=None,
                 detail=json.dumps({"template": tid, "name": name, "sections": [s["title"] for s in out]}))
    conn.commit()
    return get(conn, config, tid)


def choose(conn: sqlite3.Connection, config: CamSectionConfig, case_id: str, template_id: str, user: dict) -> None:
    get(conn, config, template_id)
    at = now_iso()
    if template_id == DEFAULT:
        conn.execute("DELETE FROM case_cam_templates WHERE case_id = ?", (case_id,))
    else:
        conn.execute(
            """INSERT INTO case_cam_templates (case_id, template_id, chosen_by, chosen_at) VALUES (?, ?, ?, ?)
               ON CONFLICT (case_id) DO UPDATE SET template_id = excluded.template_id,
               chosen_by = excluded.chosen_by, chosen_at = excluded.chosen_at""",
            (case_id, template_id, user["id"], at))
    log_decision(conn, at=at, actor=user["id"], action="cam.template_chosen", case_id=case_id,
                 detail=json.dumps({"template": template_id}))
    conn.commit()


def view(t: dict) -> dict:
    """A template as the screens read it."""
    return {
        "id": t["id"], "name": t["name"], "description": t["description"] or None, "default": t["default"],
        "created_by": t["created_by"], "created_by_name": _name(t["created_by"]), "created_at": t["created_at"],
        "sections": [{"id": s.id, "title": s.title, "purpose": s.purpose,
                      "parts": [p.kind for p in s.drafted_from()]} for s in t["sections"]],
    }
