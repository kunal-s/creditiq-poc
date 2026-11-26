"""Table contracts: what a right reading of a table holds (fields.yaml `table_contracts`).

Every reader proposes the table: a header its headings or dated columns name, wherever it is; each configured layout;
the model last. Each reading is held against the table's contract (the rows it must hold, the sums its printed figures
make, how many rows) and the one that meets it best is kept. A reading that does not meet it is still reported, with
what failed, so that a person looks at it: it is never taken as a right reading."""

from __future__ import annotations

import re

from ...config.models import TableContract, parse_identity
from .normalise import to_number
from .tables import TableResult

# A leading list marker: a roman numeral, a letter or a number set off by a bracket, a full stop or a space ("I", "IV",
# "(a)", "b)", "1.", "(ii)"), or a dash or bullet. Only a marker followed by more text is set aside.
_ROMAN = r"(?=[ivx])x{0,3}(?:ix|iv|v?i{0,3})"     # i to xxxix, not a word that only uses those letters ("civil")
_MARKER = re.compile(rf"^(?:\(?(?:{_ROMAN}|[a-z]|\d{{1,3}})[).]\s*|(?:{_ROMAN}|\d{{1,3}})\s+|[-–—•*]\s*)(?=\S)")


def label_key(text: str) -> str:
    """A label's comparison form: lower case, "&" read as "and", punctuation as spaces, leading list markers set aside."""
    t = str(text or "").casefold().replace("&", " and ")
    t = re.sub(r"\s+", " ", t).strip()
    while True:
        cut = _MARKER.sub("", t, count=1)
        if cut == t:
            break
        t = cut
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z]+", " ", t)).strip()


def _holds(label: str, alias: str) -> bool:
    """A label holds an alias as whole words; an alias written "=total" must be the whole label (a bare "TOTAL")."""
    if alias.startswith("="):
        return label == label_key(alias[1:])
    a = label_key(alias)
    return bool(a) and f" {a} " in f" {label} "


def holds_any(contract: TableContract, rows: list[dict]) -> bool:
    """Whether a reading holds at least one of the rows the table must have, with a figure: the evidence a reading
    found without its part's title above it needs before it counts as the table at all."""
    if not contract.must_have:
        return True
    return len(evaluate(contract, rows)["missing"]) < len(contract.must_have)


def _figure(v: object) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    n = to_number(str(v))
    return float(n) if n is not None else None


def evaluate(contract: TableContract, rows: list[dict]) -> dict:
    """How a reading meets the contract: {met, missing, failed, passed, rows}. `rows` are the reading's rows (cells)."""
    labels = [label_key((r.get("cells") or {}).get(contract.label) or "") for r in rows]
    figured = [any(_figure((r.get("cells") or {}).get(c)) is not None for c in contract.columns) for r in rows]
    where: dict[str, int] = {}
    for name, aliases in contract.rows.items():
        # The first row whose label matches and that prints a figure: a section's heading often shares its words with
        # the total under it ("Cash flow from operating activities", "Net cash from operating activities").
        hits = [i for i, label in enumerate(labels) if label and any(_holds(label, a) for a in aliases)]
        if hits:
            where[name] = next((i for i in hits if figured[i]), hits[0])

    def value(name: str, col: str) -> float | None:
        i = where.get(name)
        return None if i is None else _figure((rows[i].get("cells") or {}).get(col))

    missing = [n for n in contract.must_have if all(value(n, c) is None for c in contract.columns)]
    failed: list[dict] = []
    passed = 0
    for text in contract.identities:
        left, terms = parse_identity(text)   # the contract was checked when it loaded
        for col in contract.columns:
            lv = value(left, col)
            parts = [(s, value(n, col)) for s, n in terms]
            if lv is None or any(v is None for _, v in parts):
                continue
            rv = sum(s * v for s, v in parts)
            if abs(lv - rv) <= max(contract.tolerance, contract.tolerance_ratio * max(abs(lv), abs(rv))):
                passed += 1
            else:
                failed.append({"identity": text, "column": col, "left": lv, "right": round(rv, 6)})
    met = not missing and not failed and len(rows) >= contract.min_rows
    return {"met": met, "missing": missing, "failed": failed, "passed": passed, "rows": len(rows)}


def rank(verdict: dict) -> tuple:
    """Higher is better: meets the contract; then fewer missing rows; then sums that hold over sums that fail; then
    more rows."""
    return (verdict["met"], -len(verdict["missing"]), verdict["passed"] - 2 * len(verdict["failed"]), verdict["rows"])


def choose(contract: TableContract, readings: list[TableResult]) -> tuple[TableResult | None, dict | None, list[dict]]:
    """The reading that meets the contract best (the first of equals, in the order the readers ran), its verdict, and
    what each reading scored, for the trace."""
    best: tuple[TableResult, dict] | None = None
    seen: list[dict] = []
    for r in readings:
        v = evaluate(contract, r.rows)
        seen.append({"method": r.method, "page": r.page_start, "rows": v["rows"], "met": v["met"],
                     "missing": v["missing"], "failed": len(v["failed"]), "passed": v["passed"]})
        if best is None or rank(v) > rank(best[1]):
            best = (r, v)
    return (best[0], best[1], seen) if best else (None, None, seen)


def summary(verdict: dict) -> str:
    """What failed, in words, for a person."""
    parts = []
    if verdict["missing"]:
        parts.append("no " + ", ".join(n.replace("_", " ") for n in verdict["missing"]))
    for f in verdict["failed"][:3]:
        parts.append(f"{f['identity']} does not hold in {f['column'].replace('_', ' ')} ({f['left']:g} against {f['right']:g})")
    if not parts and not verdict["met"]:
        parts.append(f"only {verdict['rows']} rows")
    return "; ".join(parts)
