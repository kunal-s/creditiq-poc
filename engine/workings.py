"""How a statement figure was arrived at (FRD F-22.3): where it was read and in what unit, whether it is nil,
not printed or a person's edit, and for a sum the lines it adds. The spread and the policy norms show these
from one place, so they say the same thing about the same figure."""

from __future__ import annotations

import re

from .config import load_roles_config
from .contracts import CellEdit, CellInput, CellSource, CellWorking
from . import facts as facts_module
from . import statements
from .policy import INPUT_LABELS
from .util import printed_row_line

def editor(user_id: str) -> str:
    return next((u["name"] for u in load_roles_config()["users"] if u["id"] == user_id), user_id)


def unit_label(doc: facts_module.Doc) -> str | None:
    unit = doc.get("amount_unit")
    return f"INR {str(unit.value).strip().lower()}" if unit and statements.unit_scale(doc) != 1.0 else None


_CELL = re.compile(r"^(\w+\[\d+\])\.(\w+)$")


def row_line(doc: facts_module.Doc, field_id: str | None) -> str | None:
    """The printed line of the table row a cell sits in, rebuilt from the row when the reading did not give it."""
    name = next((k for k, v in doc.fields.items() if v.field_id == field_id), None) if field_id else None
    m = _CELL.match(name or "")
    if not m:
        return None
    return printed_row_line([(k.split(".", 1)[1], v.raw if v.raw not in (None, "") else v.value)
                             for k, v in doc.fields.items() if k.startswith(m[1] + ".") and v.value is not None])


def source(line: statements.Line, doc: facts_module.Doc) -> CellSource:
    read = line.state != "not_printed"
    ev = line.evidence[0] if line.evidence and read else None
    field_id = line.field_ids[0] if line.field_ids and read else None
    cell = next((v for v in doc.fields.values() if v.field_id == field_id), None) if field_id else None
    changed = bool(line.manual) and line.state == "printed" and cell is not None and cell.read is not None
    try:
        given = float(str(cell.read).replace(",", "")) if changed else None
    except ValueError:
        given = None
    return CellSource(document_id=doc.id, document=doc.label, page=ev.page if ev else None, row_label=line.label,
                      printed=line.raw, printed_value=line.printed if read else None, unit_label=unit_label(doc),
                      scale=line.scale, column=line.column or "current_period", file_name=doc.file_name,
                      line=(ev.line or row_line(doc, field_id)) if ev else None, bbox=ev.bbox if ev else None,
                      field_id=field_id,
                      changed=changed, document_value=given)


def edit(line: statements.Line) -> CellEdit | None:
    e = line.edit
    if e is None:
        return None
    return CellEdit(id=e.id, original=e.original, value=e.value, reason=e.reason, edited_by=editor(e.edited_by),
                    edited_at=e.edited_at)


def cell_input(line: statements.Line, label: str, sign: int, doc: facts_module.Doc) -> CellInput:
    own = line.state != "derived"
    return CellInput(key=line.key or "", label=label, value=line.value, sign=sign, state=line.state,  # type: ignore[arg-type]
                     parts=[cell_input(p.line, INPUT_LABELS.get(p.name, p.name), p.sign, doc)
                            for p in line.parts if p.line is not None],
                     source=source(line, doc) if own else None, edit=edit(line))


def line_working(line: statements.Line, doc: facts_module.Doc, name: str, editable: bool) -> CellWorking:
    if line.state == "derived":
        def joined(texts: list[tuple[int, str]]) -> str:
            return " ".join(("− " if sign < 0 else "") + text if i == 0 else ("− " if sign < 0 else "+ ") + text
                            for i, (sign, text) in enumerate(texts))

        parts = [(p, INPUT_LABELS.get(p.name, p.name)) for p in line.parts]
        return CellWorking(state="derived", formula=joined([(p.sign, label) for p, label in parts]),
                           substituted=joined([(p.sign, f"{p.value:,.0f}") for p, _ in parts]),
                           inputs=[cell_input(p.line, label, p.sign, doc) for p, label in parts if p.line])
    # No edit target: a statement figure is changed on the Extractions tab, where a second person checks it.
    return CellWorking(state=line.state, source=source(line, doc), edit=edit(line))  # type: ignore[arg-type]


