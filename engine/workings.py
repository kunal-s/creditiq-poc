"""How a statement figure was arrived at (FRD F-22.3): where it was read and in what unit, whether it is nil,
not printed or a person's edit, and for a sum the lines it adds. The spread and the policy norms show these
from one place, so they say the same thing about the same figure."""

from __future__ import annotations

from .config import load_roles_config
from .contracts import CellEdit, CellInput, CellSource, CellWorking, EditTarget
from . import facts as facts_module
from . import statements
from .policy import INPUT_LABELS

def editor(user_id: str) -> str:
    return next((u["name"] for u in load_roles_config()["users"] if u["id"] == user_id), user_id)


def unit_label(doc: facts_module.Doc) -> str | None:
    unit = doc.get("amount_unit")
    return f"INR {str(unit.value).strip().lower()}" if unit and statements.unit_scale(doc) != 1.0 else None


def source(line: statements.Line, doc: facts_module.Doc) -> CellSource:
    page = line.evidence[0].page if line.evidence and line.state != "not_printed" else None
    return CellSource(document_id=doc.id, document=doc.label, page=page, row_label=line.label, printed=line.raw,
                      printed_value=None if line.state == "not_printed" else line.printed, unit_label=unit_label(doc),
                      scale=line.scale, column=line.column or "current_period")


def edit(line: statements.Line) -> CellEdit | None:
    e = line.edit
    if e is None:
        return None
    return CellEdit(id=e.id, original=e.original, value=e.value, reason=e.reason, edited_by=editor(e.edited_by),
                    edited_at=e.edited_at)


def target(line: statements.Line, doc: facts_module.Doc, name: str) -> EditTarget:
    return EditTarget(document_id=doc.id, line=name, column=line.column or "current_period")


def cell_input(line: statements.Line, label: str, sign: int, doc: facts_module.Doc) -> CellInput:
    own = line.state != "derived"
    return CellInput(key=line.key or "", label=label, value=line.value, sign=sign, state=line.state,  # type: ignore[arg-type]
                     parts=[cell_input(p.line, INPUT_LABELS.get(p.name, p.name), p.sign, doc)
                            for p in line.parts if p.line is not None],
                     source=source(line, doc) if own else None, edit=edit(line),
                     target=target(line, doc, line.key or "") if own and line.key else None)


def line_working(line: statements.Line, doc: facts_module.Doc, name: str, editable: bool) -> CellWorking:
    if line.state == "derived":
        def joined(texts: list[tuple[int, str]]) -> str:
            return " ".join(("− " if sign < 0 else "") + text if i == 0 else ("− " if sign < 0 else "+ ") + text
                            for i, (sign, text) in enumerate(texts))

        parts = [(p, INPUT_LABELS.get(p.name, p.name)) for p in line.parts]
        return CellWorking(state="derived", formula=joined([(p.sign, label) for p, label in parts]),
                           substituted=joined([(p.sign, f"{p.value:,.0f}") for p, _ in parts]),
                           inputs=[cell_input(p.line, label, p.sign, doc) for p, label in parts if p.line])
    return CellWorking(state=line.state, source=source(line, doc), edit=edit(line),  # type: ignore[arg-type]
                       target=target(line, doc, name) if editable else None)


