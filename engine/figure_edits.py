"""A person's change to an extracted figure, checked by a second person (F-17.5 with F-03.4).

The Credit Analyst (a maker: `manual.make`) proposes a new value for a figure read from a document,
gives the reason and, where there is one, attaches the paper that supports it (an auditor's letter,
a revised statement). The proposal waits on a manual-entry review item (from, to, reason, the
attachment) for the Credit Manager (a checker: `manual.check`, never the maker). Until then the
field is untouched and the figure in force is what it was: nothing downstream reads an unchecked
number. Approved, the person's figure is kept beside the system's (`corrected_value`, status
`corrected`); sent back with a reason, nothing on the field changes. Every step is written to the
decision log.

The attachment is stored with the case, outside its documents: it is evidence for the change, not
a document of the appraisal, so it is never read, classified or counted on the checklist.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path

from .db import log_decision, transaction
from .review_items import close_item, reopen_item
from .store import cases_dir
from .util import now_iso

# What a supporting file may be: the kinds a person scans or saves a letter as.
ATTACHMENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
REASON_MIN = 10


class EditError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _require(ok: bool, message: str, status: int = 422) -> None:
    if not ok:
        raise EditError(status, message)


def attachments_dir(root: Path, case_id: str) -> Path:
    return cases_dir(root) / case_id / "attachments"


def parse_value(text: str, system: object) -> int | float:
    """The person's figure, as a number in the type of the one it replaces: Indian or Western digit
    grouping, a rupee sign or "Rs", brackets or a minus for a negative. Only a figure is changed
    this way: a value the document gave as text (a name, a date) is not."""
    raw = text.strip()
    _require(raw != "", "give the new figure")
    _require(system is None or (isinstance(system, (int, float)) and not isinstance(system, bool)),
             "only a figure (a number) is changed here")
    negative = raw.startswith("(") and raw.endswith(")")
    digits = re.sub(r"[,\s₹]|^INR|^Rs\.?", "", raw.strip("()"), flags=re.I)
    _require(re.fullmatch(r"-?\d+(\.\d+)?", digits) is not None, f"{raw!r} is not a number")
    number = float(digits)
    number = -number if negative else number
    return int(number) if number.is_integer() and not isinstance(system, float) else number


def shown(value: object) -> str:
    """A figure as the summary line shows it: an amount in Indian digit grouping."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—" if value is None else str(value)
    sign, number = ("-" if value < 0 else ""), abs(value)
    whole, _, fraction = f"{number:.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    text = ",".join([*groups, tail]) if groups else tail
    return sign + text + ("" if isinstance(value, int) or fraction == "00" else "." + fraction)


def edit_figure(
    conn: sqlite3.Connection,
    root: Path,
    *,
    case_id: str,
    field_id: str,
    value: str,
    reason: str,
    user: dict,
    attachment: tuple[str, Path] | None = None,
) -> str:
    """Record the maker's change and open it for a checker; returns the review item's id."""
    _require("manual.make" in set(user["permissions"]), "changing a figure needs the maker permission", 403)
    reason = (reason or "").strip()
    _require(len(reason) >= REASON_MIN, f"say why the figure changes (at least {REASON_MIN} characters)")
    fv = conn.execute("SELECT * FROM field_values WHERE id = ? AND case_id = ?", (field_id, case_id)).fetchone()
    _require(fv is not None, "no such field on this case", 404)
    system = json.loads(fv["value"]) if fv["value"] is not None else None
    corrected = json.loads(fv["corrected_value"]) if fv["corrected_value"] is not None else None
    # The figure in force, as everything downstream reads it (engine/facts.py).
    current = corrected if fv["status"] == "corrected" and corrected is not None else system
    new = parse_value(value, current)
    _require(new != current, "the new figure is the same as the one on record")

    stored = None
    if attachment is not None:
        name, path = attachment
        suffix = Path(name).suffix.lower()
        _require(suffix in ATTACHMENT_TYPES, "attach a PDF, an image, a Word or an Excel file")
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        target = attachments_dir(root, case_id) / f"{sha[:16]}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(path, target)
        stored = {"name": Path(name).name, "file": target.name, "size": len(data), "sha256": sha,
                  "content_type": ATTACHMENT_TYPES[suffix]}

    # A change still waiting for its check is replaced by the new one (the same review item).
    at = now_iso()
    detail = {
        "field_value_id": field_id,
        "document_id": fv["document_id"],
        "field": fv["field"],
        "from": current,
        "to": new,
        "reason": reason,
        "attachment": stored,
        "maker_name": user["name"],
        "at": at,
    }
    with transaction(conn):
        item_id = reopen_item(
            conn,
            case_id=case_id,
            kind="manual_entry",
            ref=f"field:{field_id}",
            summary=(f"{user['name']} changed {fv['field'].replace('_', ' ')} from {shown(current)} to {shown(new)};"
                     " awaiting the Credit Manager's check"),
            detail=detail,
            maker=user["id"],
        )
        log_decision(conn, at=at, actor=user["id"], case_id=case_id, action="figure.edited",
                     detail=json.dumps({"item_id": item_id, **{k: detail[k] for k in ("field_value_id", "field",
                                                                                     "from", "to", "reason")},
                                        "attachment": stored["name"] if stored else None}))
    return item_id


def pending_edit(conn: sqlite3.Connection, case_id: str, field_id: str) -> bool:
    """Whether a change to this figure is waiting for its check."""
    return conn.execute(
        "SELECT 1 FROM review_items WHERE case_id = ? AND kind = 'manual_entry' AND ref = ? AND status = 'open'",
        (case_id, f"field:{field_id}"),
    ).fetchone() is not None


def check_edit(conn: sqlite3.Connection, detail: dict, decision: str, log: dict, *, checker: str) -> None:
    """The checker's decision on a changed figure, inside the review decision's transaction: approve
    (the person's figure is kept beside the system's and is in force) or send back (the field stays
    as it is)."""
    fv = conn.execute("SELECT id, case_id FROM field_values WHERE id = ?", (detail["field_value_id"],)).fetchone()
    _require(fv is not None, "the field no longer exists", 409)
    if decision == "confirm":
        conn.execute(
            "UPDATE field_values SET corrected_value = ?, status = 'corrected' WHERE id = ?",
            (json.dumps(detail["to"]), fv["id"]),
        )
        # The approved figure also settles a check of the value the system read, if one was open.
        field_item = conn.execute(
            "SELECT id FROM review_items WHERE case_id = ? AND kind = 'field' AND ref = ? AND status = 'open'",
            (fv["case_id"], f"field:{fv['id']}"),
        ).fetchone()
        if field_item is not None:
            close_item(conn, item_id=field_item["id"], decision="correct",
                       reason="settled by the approved change to this figure", decided_by=checker)
    elif decision != "waive":
        raise EditError(422, "a changed figure is approved (confirm) or sent back (waive) with a reason")
    log.update(field_value_id=fv["id"], field=detail.get("field"), from_value=detail.get("from"),
               to_value=detail.get("to"), approved=decision == "confirm")
