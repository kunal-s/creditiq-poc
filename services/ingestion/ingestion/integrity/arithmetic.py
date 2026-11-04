"""F-07A: whether a statement's printed figures add up (family `arithmetic`, T0).

Ported from fault_detection (`reconcile.py`, `selfcheck.py`, `annual.py`) onto
what CreditIQ already reads: the extracted transactions table and the opening and
closing balances, the page lines (for printed totals and carried-forward lines),
and the extracted balance sheet.

The checks read what the page **prints** (each row's `raw` text), not the
extraction's repaired cells: extraction repairs a single cell that breaks the
running balance (F-15.3), which is right for reading figures but would hide a
figure edited on a digital statement. On a page of text a printed figure cannot
be misread, so a break there counts; on a page read by OCR a break that one
misread cell explains is listed for a reader, not counted.

Money is compared as whole paise. No model is called: totals and carry lines
are found by their printed labels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ..contracts import IntegrityEvidence, IntegrityFinding
from ..pageindex import Line, Page
from ..stages.extract.normalise import to_number
from .spec import method

__all__ = ["ARITHMETIC_CHECKS", "arithmetic_checks", "not_added_up"]

ARITHMETIC_CHECKS = ("BALANCE_CHAIN", "OPENING_BALANCE", "CLOSING_BALANCE", "SUMMARY_TOTALS",
                     "HEADER_ARITHMETIC", "PAGE_CARRY", "BS_BALANCES")
STATEMENT_CHECKS = ARITHMETIC_CHECKS[:-1]
MAX_EVIDENCE = 12
MONEY = re.compile(r"\(?-?(?:\d{1,3}(?:,\d{2,3})+|\d+)\.\d{2}\)?(?:\s*(?:dr|cr)\b\.?)?", re.I)
COUNT = re.compile(r"(?<![\d,.])\d{1,4}(?![\d,.])")


def _result(cfg: dict, code: str, status: str, finding: str, evidence: list[IntegrityEvidence] | None = None,
            context: bool | None = None) -> IntegrityFinding:
    spec = cfg["checks"][code]
    return IntegrityFinding(code=code, family=spec["family"], status=status, finding=finding,
                            evidence=evidence or [], tier=spec["tier"], impact=spec["impact"],
                            context=bool(spec.get("context", False)) if context is None else context,
                            method=method(spec, cfg["version"]), reads=["figures"])


def not_added_up(cfg: dict, why: str) -> list[IntegrityFinding]:
    """Every arithmetic check, answered before the figures are read (or when they never are)."""
    return [_result(cfg, c, "not_applicable", why) for c in ARITHMETIC_CHECKS if c in cfg["checks"]]


def paise(raw: Any) -> int | None:
    """A printed or extracted amount as whole paise; None when it does not read as one."""
    if raw is None or raw == "":
        return None
    value = raw if isinstance(raw, (int, float)) else to_number(str(raw))
    if value is None:
        return None
    try:
        return int((Decimal(str(value)) * 100).to_integral_value())
    except InvalidOperation:
        return None


def rupees(p: int) -> str:
    """Paise as rupees with Indian grouping: 1,23,456.78."""
    sign, p = ("-" if p < 0 else ""), abs(p)
    whole, frac = divmod(p, 100)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return f"{sign}{s}.{frac:02d}"


@dataclass(slots=True)
class _Row:
    index: int
    page: int | None
    bbox: tuple | None
    debit: int
    credit: int
    balance: int | None
    repaired: bool


def _rows(table: dict, cols: dict) -> list[_Row]:
    repaired = {r["row"] for r in table.get("repairs") or []}
    out = []
    for i, r in enumerate(table.get("rows") or []):
        raw, cells = r.get("raw") or {}, r.get("cells") or {}

        def printed(col: str) -> int | None:
            # What the page prints; the extracted cell only where nothing was printed.
            return paise(raw[col]) if raw.get(col) not in (None, "") else paise(cells.get(col))

        d, c, b = printed(cols["debit"]), printed(cols["credit"]), printed(cols["balance"])
        src = r.get("source") or {}
        out.append(_Row(i, src.get("page"), tuple(src["bbox"]) if src.get("bbox") else None,
                        abs(d or 0), abs(c or 0), b, i in repaired))
    return out


def _breaks(rows: list[_Row], sign: int, tol: int) -> tuple[list[tuple[_Row, int, int]], int]:
    """Rows whose printed balance does not follow: (row, expected, printed), and how many were compared.
    Rows printing no balance carry their movement to the next balance printed."""
    out, compared, prev, moved = [], 0, None, 0
    for r in rows:
        moved += sign * (r.credit - r.debit)
        if r.balance is None:
            continue
        if prev is not None:
            compared += 1
            if abs(prev + moved - r.balance) > tol:
                out.append((r, prev + moved, r.balance))
        prev, moved = r.balance, 0
    return out, compared


def _convention(rows: list[_Row], tol: int) -> tuple[str, list[_Row], int, list, int]:
    """The reading under which the most balances follow: credits raise or lower the
    balance, rows printed oldest or newest first. (name, rows in time order, sign, breaks, compared)."""
    best = None
    # Printed newest first, each row still shows its own movement and the balance
    # after it: read in reverse, it is a statement printed oldest first.
    for order, seq in (("oldest first", rows), ("newest first", rows[::-1])):
        for sign, name in ((1, "credits raise the balance"), (-1, "debits raise the balance")):
            broken, compared = _breaks(seq, sign, tol)
            key = (len(broken), order != "oldest first", sign != 1)
            if best is None or key < best[0]:
                best = (key, f"{name}, rows {order}", seq, sign, broken, compared)
    _, name, seq, sign, broken, compared = best
    return name, seq, sign, broken, compared


def _frac(pages: dict[int, Page], page: int | None, bbox) -> tuple[float, float, float, float] | None:
    pg = pages.get(page) if page else None
    if pg is None or not bbox or not pg.width or not pg.height:
        return None
    x0, y0, x1, y1 = bbox
    c = lambda v: round(min(max(v, 0.0), 1.0), 4)  # noqa: E731
    return (c(x0 / pg.width), c(y0 / pg.height), c(x1 / pg.width), c(y1 / pg.height))


def _line_box(line: Line) -> tuple | None:
    if not line.words:
        return None
    return (min(w.x0 for w in line.words), min(w.y0 for w in line.words),
            max(w.x1 for w in line.words), max(w.y1 for w in line.words))


def _printed(lines: list[Line], label: str, *, count: bool = False) -> tuple[int, Line] | None:
    """The figure printed with a label: on its line after it, or in the line below,
    under it (a summary laid out as a row of headings over a row of figures)."""
    pattern = re.compile(label, re.I)
    for i, line in enumerate(lines):
        hit = pattern.search(line.text)
        if not hit:
            continue
        token = COUNT if count else MONEY
        after = [m for m in token.finditer(line.text, hit.end())]
        if after:
            value = int(after[0].group()) if count else paise(after[0].group())
            if value is not None:
                return value, line
            continue
        if i + 1 >= len(lines):
            continue
        below = lines[i + 1]
        # The heading's place on its line, and the figure below nearest it.
        start = len(line.text[:hit.start()].split())
        heads = line.words[start:start + max(1, len(hit.group().split()))]
        if not heads:
            continue
        centre = (heads[0].x0 + heads[-1].x1) / 2
        figures = [w for w in below.words if (COUNT if count else MONEY).fullmatch(w.text.strip())]
        if figures:
            w = min(figures, key=lambda w: abs((w.x0 + w.x1) / 2 - centre))
            value = int(w.text) if count else paise(w.text)
            if value is not None:
                return value, below
    return None


def _statement(cfg: dict, a: dict, fields: dict, table: dict, pages: dict[int, Page],
               lines: list[Line]) -> dict[str, list]:
    """One statement's figures, checked: per code, a list of (counts, evidence, said)."""
    tol = a["tolerance_paise"]
    out: dict[str, list] = {c: [] for c in STATEMENT_CHECKS}
    rows = _rows(table, a["columns"])
    with_balance = [r for r in rows if r.balance is not None]
    if len(with_balance) < 2:
        return out
    name, seq, sign, broken, compared = _convention(rows, tol)
    limit = max(a["max_breaks"], int(compared * a["max_break_share"]))
    if len(broken) > limit:
        out["BALANCE_CHAIN"].append(("unread", None, f"{len(broken)} of {compared} balances break whichever way "
                                                     f"the rows are read, so the columns were not read as printed"))
    else:
        out["BALANCE_CHAIN"].append(("compared", None, f"{compared} balances, {name}"))
        for r, expected, printed in broken:
            on_text = (pages.get(r.page).source if pages.get(r.page) else "ocr") != "ocr"
            misread = not on_text and r.repaired
            ev = IntegrityEvidence(
                page=r.page or 1, rect=_frac(pages, r.page, r.bbox),
                observed=f"row {r.index + 1}: printed balance {rupees(printed)}; the balance before it and the row's "
                         f"movement give {rupees(expected)} (a difference of {rupees(printed - expected)})"
                         + ("; one misread cell explains it, on a page read by OCR" if misread else ""),
                threshold=f"each balance = the one before + credits − debits, within {rupees(tol)}")
            out["BALANCE_CHAIN"].append(("misread" if misread else "break", ev, None))
    first, last = seq[0], next(r for r in reversed(seq) if r.balance is not None)
    first_bal = next(r for r in seq if r.balance is not None)
    moved_before = sum(sign * (r.credit - r.debit) for r in seq[:seq.index(first_bal) + 1])
    for code, field, mine, what in (("OPENING_BALANCE", a["opening_field"], first_bal.balance - moved_before,
                                     "the first row's balance less its movement"),
                                    ("CLOSING_BALANCE", a["closing_field"], last.balance, "the last row's balance")):
        f = fields.get(field) or {}
        stated = paise(f.get("raw_text")) if f.get("raw_text") else paise(f.get("value"))
        if f.get("status") != "found" or stated is None:
            continue
        src = f.get("source") or {}
        ok = abs(stated - mine) <= tol
        out[code].append(("agree" if ok else "differ", IntegrityEvidence(
            page=src.get("page") or (first.page if code == "OPENING_BALANCE" else last.page) or 1,
            rect=_frac(pages, src.get("page"), src.get("bbox")),
            observed=f"printed {rupees(stated)}; {what} is {rupees(mine)}"
                     + ("" if ok else f" (a difference of {rupees(stated - mine)})"),
            threshold=f"the same within {rupees(tol)}"), None))
    sums = {"credits": sum(r.credit for r in rows), "debits": sum(r.debit for r in rows),
            "count": sum(1 for r in rows if r.credit or r.debit)}
    printed_totals = {}
    for key, label in (("credits", a["labels"]["total_credits"]), ("debits", a["labels"]["total_debits"]),
                       ("count", a["labels"]["count"])):
        found = _printed(lines, label, count=key == "count")
        if found is None:
            continue
        value, line = found
        printed_totals[key] = value
        mine = sums[key]
        ok = (value == mine) if key == "count" else abs(value - mine) <= tol
        shown = (lambda v: str(v)) if key == "count" else rupees
        out["SUMMARY_TOTALS"].append(("agree" if ok else "differ", IntegrityEvidence(
            page=line.page, rect=_frac(pages, line.page, _line_box(line)),
            observed=f"printed total {key} {shown(value)}; the rows add up to {shown(mine)}",
            threshold="the printed total equals the rows' sum"), None))
    f_open, f_close = fields.get(a["opening_field"]) or {}, fields.get(a["closing_field"]) or {}
    o = paise(f_open.get("raw_text") or f_open.get("value")) if f_open.get("status") == "found" else None
    c = paise(f_close.get("raw_text") or f_close.get("value")) if f_close.get("status") == "found" else None
    if None not in (o, c) and {"credits", "debits"} <= set(printed_totals):
        gives = o + sign * (printed_totals["credits"] - printed_totals["debits"])
        ok = abs(gives - c) <= tol
        out["HEADER_ARITHMETIC"].append(("agree" if ok else "differ", IntegrityEvidence(
            page=(f_close.get("source") or {}).get("page") or last.page or 1, rect=None,
            observed=f"opening {rupees(o)} + total credits {rupees(printed_totals['credits'])} − total debits "
                     f"{rupees(printed_totals['debits'])} = {rupees(gives)}; printed closing {rupees(c)}",
            threshold=f"the summary adds up within {rupees(tol)}"), None))
    for key, label in (("carried", a["labels"]["carried_forward"]), ("brought", a["labels"]["brought_forward"])):
        for line in lines:
            if not re.search(label, line.text, re.I):
                continue
            found = _printed([line], label)
            if found is None:
                continue
            value = found[0]
            before = [r for r in rows if r.balance is not None and r.page is not None
                      and (r.page <= line.page if key == "carried" else r.page < line.page)]
            if not before:
                continue
            mine = before[-1].balance
            ok = abs(value - mine) <= tol
            out["PAGE_CARRY"].append(("agree" if ok else "differ", IntegrityEvidence(
                page=line.page, rect=_frac(pages, line.page, _line_box(line)),
                observed=f"page {line.page} prints {key} forward {rupees(value)}; the last balance "
                         f"{'on' if key == 'carried' else 'before'} it is {rupees(mine)}",
                threshold="a carried figure equals the balance it carries"), None))
    return out


def _balance_sheet(a: dict, table: dict, pages: dict[int, Page]) -> list:
    """The balance sheet's two grand totals, each year: (agree|differ, evidence)."""
    pattern = re.compile(a["balance_sheet_totals"], re.I)
    totals = [r for r in table.get("rows") or [] if pattern.search(str((r.get("cells") or {}).get("particulars") or ""))]
    if len(totals) < 2:
        return []
    out = []
    one, two = totals[0], totals[1]
    for col in a["balance_sheet_columns"]:
        va = to_number(str((one.get("raw") or {}).get(col) or (one.get("cells") or {}).get(col) or ""))
        vb = to_number(str((two.get("raw") or {}).get(col) or (two.get("cells") or {}).get(col) or ""))
        if va is None or vb is None:
            continue
        ok = abs(va - vb) <= a["balance_sheet_tolerance_units"]
        src = two.get("source") or {}
        out.append(("agree" if ok else "differ", IntegrityEvidence(
            page=src.get("page") or 1, rect=_frac(pages, src.get("page"), src.get("bbox")),
            observed=f"{col.replace('_', ' ')}: “{(one.get('cells') or {}).get('particulars')}” {va:,} against "
                     f"“{(two.get('cells') or {}).get('particulars')}” {vb:,}"
                     + ("" if ok else f" (a difference of {abs(va - vb):,})"),
            threshold=f"the two totals agree within {a['balance_sheet_tolerance_units']:g} of the printed unit"),
            None))
    return out


def arithmetic_checks(cfg: dict, doc_type: str | None, pages: list[Page], extracted: list[dict]) -> list[IntegrityFinding]:
    """Every arithmetic check, over the file's extracted statements or balance sheets."""
    a = cfg["arithmetic"]
    by_no = {p.no: p for p in pages}
    lines = [line for p in pages for line in p.lines]
    out: list[IntegrityFinding] = []
    statement = doc_type in a["statement_types"]
    sheet = doc_type in a["balance_sheet_types"]
    if not statement:
        why = "Not a bank statement: there is no running balance to add up."
        out += [_result(cfg, c, "not_applicable", why) for c in STATEMENT_CHECKS]
    else:
        got: dict[str, list] = {c: [] for c in STATEMENT_CHECKS}
        for e in extracted:
            table = (e.get("tables") or {}).get(a["statement_table"]) or {}
            if table.get("status") != "found":
                continue
            for code, items in _statement(cfg, a, e.get("fields") or {}, table, by_no, lines).items():
                got[code] += items
        out += _statement_results(cfg, got)
    if not sheet:
        out.append(_result(cfg, "BS_BALANCES", "not_applicable",
                           "Not audited financial statements: there is no balance sheet to add up."))
    else:
        items = []
        for e in extracted:
            table = (e.get("tables") or {}).get(a["balance_sheet_table"]) or {}
            if table.get("status") == "found":
                items += _balance_sheet(a, table, by_no)
        out.append(_compared(cfg, "BS_BALANCES", items, "the balance sheet's two grand totals",
                             "No balance sheet with two grand totals was read."))
    return [f for f in out if f.code in cfg["checks"]]


def _compared(cfg: dict, code: str, items: list, what: str, none: str) -> IntegrityFinding:
    if not items:
        return _result(cfg, code, "not_applicable", none)
    differ = [ev for k, ev, _ in items if k == "differ"]
    if differ:
        return _result(cfg, code, "review_required", f"{len(differ)} of {len(items)} comparisons of {what} do not "
                                                     f"agree.", differ[:MAX_EVIDENCE])
    return _result(cfg, code, "pass", f"Every comparison of {what} agrees ({len(items)}).",
                   [ev for _, ev, _ in items][:MAX_EVIDENCE])


def _statement_results(cfg: dict, got: dict[str, list]) -> list[IntegrityFinding]:
    out = []
    chain = got["BALANCE_CHAIN"]
    unread = [s for k, _, s in chain if k == "unread"]
    compared = [s for k, _, s in chain if k == "compared"]
    breaks = [ev for k, ev, _ in chain if k == "break"]
    misreads = [ev for k, ev, _ in chain if k == "misread"]
    if not chain:
        out.append(_result(cfg, "BALANCE_CHAIN", "not_applicable", "No running balance of two rows or more was read."))
    elif unread and not compared:
        out.append(_result(cfg, "BALANCE_CHAIN", "unable_to_determine", "; ".join(unread) + "."))
    elif breaks:
        out.append(_result(cfg, "BALANCE_CHAIN", "review_required",
                           f"The running balance breaks at {len(breaks)} row(s) on pages that carry their own text: "
                           f"the printed balance does not follow from the row before ({'; '.join(compared)}).",
                           (breaks + misreads)[:MAX_EVIDENCE]))
    elif misreads:
        out.append(_result(cfg, "BALANCE_CHAIN", "warning",
                           f"The running balance breaks at {len(misreads)} row(s) on pages read by OCR, each explained "
                           f"by one misread cell ({'; '.join(compared)}).", misreads[:MAX_EVIDENCE], context=True))
    else:
        out.append(_result(cfg, "BALANCE_CHAIN", "pass",
                           f"Every printed balance follows from the one before ({'; '.join(compared)})."))
    out.append(_compared(cfg, "OPENING_BALANCE", got["OPENING_BALANCE"], "the opening balance with the first row",
                         "No opening balance was read to compare with the rows."))
    out.append(_compared(cfg, "CLOSING_BALANCE", got["CLOSING_BALANCE"], "the closing balance with the last row",
                         "No closing balance was read to compare with the rows."))
    out.append(_compared(cfg, "SUMMARY_TOTALS", got["SUMMARY_TOTALS"], "a printed total with the rows",
                         "The statement prints no total credits, total debits or count of transactions."))
    out.append(_compared(cfg, "HEADER_ARITHMETIC", got["HEADER_ARITHMETIC"], "the printed summary",
                         "The statement does not print an opening balance, total credits, total debits and a closing "
                         "balance together."))
    out.append(_compared(cfg, "PAGE_CARRY", got["PAGE_CARRY"], "a carried-forward figure with its balance",
                         "No page prints a carried-forward or brought-forward figure."))
    return out
