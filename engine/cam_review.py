"""The draft CAM's review (docs/functional-requirements.md F-23): a section in a person's words or
redrafted by the copilot and kept, the figures a person overrode, and the data asked for from a
section. The engine's draft is never changed: this is laid over it when the memo is read, and every
change is kept with who made it and when, in the decision log too.

A section's words replace its drafted paragraphs one for one, so paragraph n keeps the citations of
the drafted paragraph n; key facts and tables stay as drafted. A figure overridden is listed under
the section with the value drafted, the value given and the reason. Data asked for goes on the
query list (queries.py) and is listed under the section.
"""

from __future__ import annotations

import json
import sqlite3

from .config import find_user_by_id
from .contracts import Cam, CamBlock, CamOverride, CamRequest, CamReview, CamTable, CamText
from .db import log_decision
from .util import now_iso, stable_id

SUMMARY = "summary"
RECOMMENDATION = "recommendation"


class ReviewError(Exception):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def section_ids(cam: Cam) -> list[str]:
    """Every section a person may review: the drafted ones, the risk assessment, the recommendation."""
    return [s.id for s in cam.sections] + [SUMMARY, RECOMMENDATION]


def _name(user_id: str | None) -> str | None:
    user = find_user_by_id(user_id) if user_id else None
    return user.get("name") if user else None


def reviews(conn: sqlite3.Connection, case_id: str) -> dict[str, CamReview]:
    out: dict[str, CamReview] = {}
    for r in conn.execute("SELECT * FROM cam_reviews WHERE case_id = ?", (case_id,)):
        out[r["section_id"]] = CamReview(state=r["state"], by=r["by"], by_name=_name(r["by"]), at=r["at"],
                                         model=r["model"], paragraphs=json.loads(r["paragraphs"]))
    for r in conn.execute("SELECT * FROM cam_overrides WHERE case_id = ? ORDER BY at", (case_id,)):
        out.setdefault(r["section_id"], CamReview()).overrides.append(CamOverride(
            id=r["id"], figure=r["figure"], original=r["original"], value=r["value"], reason=r["reason"],
            by=r["by"], by_name=_name(r["by"]), at=r["at"]))
    for r in conn.execute("SELECT * FROM cam_requests WHERE case_id = ? ORDER BY at", (case_id,)):
        out.setdefault(r["section_id"], CamReview()).requests.append(CamRequest(
            id=r["id"], text=r["text"], by=r["by"], by_name=_name(r["by"]), at=r["at"]))
    return out


def _overrides_table(overrides: list[CamOverride]) -> CamBlock:
    return CamBlock(kind="table", table=CamTable(
        title="Figures overridden by the analyst", columns=["Figure", "As drafted", "Overridden to", "Reason", "By"],
        rows=[[CamText(text=o.figure), CamText(text=o.original), CamText(text=o.value), CamText(text=o.reason),
               CamText(text=f"{o.by_name or o.by}, {o.at[:10]}")] for o in overrides]))


def _requests_note(requests: list[CamRequest]) -> CamBlock:
    return CamBlock(kind="note", text="Data requested: " + "; ".join(r.text for r in requests) + ".")


def _replace_paragraphs(blocks: list[CamBlock], words: list[str]) -> list[CamBlock]:
    """The section's paragraphs in other words, one for one, each keeping the citations of the
    paragraph in its place; words beyond the drafted paragraphs follow the last, uncited."""
    out: list[CamBlock] = []
    left = list(words)
    for b in blocks:
        if b.kind == "paragraph" and b.paragraph is not None:
            if left:
                out.append(CamBlock(kind="paragraph", paragraph=CamText(text=left.pop(0),
                                                                         citations=b.paragraph.citations)))
            continue
        out.append(b)
    if left:
        # Placed after the last paragraph, or first where there was none.
        at = max((i for i, b in enumerate(out) if b.kind == "paragraph"), default=-1) + 1
        out[at:at] = [CamBlock(kind="paragraph", paragraph=CamText(text=w)) for w in left]
    return out


def apply(conn: sqlite3.Connection, cam: Cam) -> None:
    found = reviews(conn, cam.case_id)
    for s in cam.sections:
        review = found.get(s.id)
        if not review:
            continue
        s.review = review
        if review.paragraphs:
            s.blocks = _replace_paragraphs(s.blocks, review.paragraphs)
        if review.overrides:
            s.blocks = [*s.blocks, _overrides_table(review.overrides)]
        if review.requests:
            s.blocks = [*s.blocks, _requests_note(review.requests)]
    if SUMMARY in found:
        cam.summary_review = found[SUMMARY]
    if RECOMMENDATION in found:
        cam.recommendation_review = found[RECOMMENDATION]
        if found[RECOMMENDATION].paragraphs:
            cam.recommendation = "\n\n".join(found[RECOMMENDATION].paragraphs)


def drafted_paragraphs(cam: Cam, section_id: str) -> list[str]:
    """A section's paragraphs as the engine drafted them (before any review), the words a person
    starts from and the copilot redrafts."""
    if section_id == SUMMARY:
        return [i.text for i in cam.summary]
    if section_id == RECOMMENDATION:
        return [p for p in cam.recommendation.split("\n\n") if p.strip()] if cam.recommendation else []
    s = next((s for s in cam.sections if s.id == section_id), None)
    if s is None:
        raise ReviewError(f"no section {section_id!r} in the memo", 404)
    blocks = [b for p in s.parts for b in p.blocks] if s.parts else s.blocks
    return [b.paragraph.text for b in blocks if b.kind == "paragraph" and b.paragraph]


def _check_section(cam: Cam, section_id: str) -> None:
    if section_id not in section_ids(cam):
        raise ReviewError(f"no section {section_id!r} in the memo", 404)


def save_words(conn: sqlite3.Connection, cam: Cam, section_id: str, paragraphs: list[str], user: dict, *,
               state: str = "edited", model: str | None = None) -> None:
    _check_section(cam, section_id)
    words = [p.strip() for p in paragraphs if p.strip()]
    if not words:
        raise ReviewError("The section needs at least one paragraph.")
    at = now_iso()
    conn.execute(
        """INSERT INTO cam_reviews (case_id, section_id, state, paragraphs, model, by, at) VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (case_id, section_id) DO UPDATE SET state = excluded.state, paragraphs = excluded.paragraphs,
           model = excluded.model, by = excluded.by, at = excluded.at""",
        (cam.case_id, section_id, state, json.dumps(words), model, user["id"], at))
    log_decision(conn, at=at, actor=user["id"], action=f"cam.{state}", case_id=cam.case_id,
                 detail=json.dumps({"section": section_id, "model": model}))
    conn.commit()


def restore(conn: sqlite3.Connection, cam: Cam, section_id: str, user: dict) -> None:
    """Back to the engine's draft: a person's or the copilot's words are set aside."""
    _check_section(cam, section_id)
    at = now_iso()
    conn.execute("DELETE FROM cam_reviews WHERE case_id = ? AND section_id = ?", (cam.case_id, section_id))
    log_decision(conn, at=at, actor=user["id"], action="cam.restored", case_id=cam.case_id,
                 detail=json.dumps({"section": section_id}))
    conn.commit()


def add_override(conn: sqlite3.Connection, cam: Cam, section_id: str, figure: str, original: str, value: str,
                 reason: str, user: dict) -> None:
    _check_section(cam, section_id)
    fields = {"figure": figure.strip(), "original": original.strip(), "value": value.strip(), "reason": reason.strip()}
    if not all(fields.values()):
        raise ReviewError("The figure, the value as drafted, your value and the reason are all needed.")
    if len(fields["reason"]) < 3:
        raise ReviewError("A reason of at least 3 characters is required.")
    at = now_iso()
    oid = stable_id("OV", cam.case_id, section_id, fields["figure"], at)
    conn.execute(
        "INSERT INTO cam_overrides (id, case_id, section_id, figure, original, value, reason, by, at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (oid, cam.case_id, section_id, *fields.values(), user["id"], at))
    log_decision(conn, at=at, actor=user["id"], action="cam.override", case_id=cam.case_id,
                 detail=json.dumps({"section": section_id, **fields}))
    conn.commit()


def add_request(conn: sqlite3.Connection, cam: Cam, section_id: str, text: str, user: dict) -> None:
    _check_section(cam, section_id)
    text = text.strip()
    if len(text) < 3:
        raise ReviewError("Say what is needed, in at least 3 characters.")
    at = now_iso()
    rid = stable_id("RQ", cam.case_id, section_id, text, at)
    conn.execute("INSERT INTO cam_requests (id, case_id, section_id, text, by, at) VALUES (?, ?, ?, ?, ?, ?)",
                 (rid, cam.case_id, section_id, text, user["id"], at))
    log_decision(conn, at=at, actor=user["id"], action="cam.request", case_id=cam.case_id,
                 detail=json.dumps({"section": section_id, "text": text}))
    conn.commit()


def requests_for_queries(conn: sqlite3.Connection, case_id: str) -> list[tuple[str, str]]:
    """(source ref, text) for each request made from the memo, for the query list."""
    return [(f"cam:{r['section_id']}:{r['id']}", r["text"]) for r in conn.execute(
        "SELECT id, section_id, text FROM cam_requests WHERE case_id = ? ORDER BY at", (case_id,))]
