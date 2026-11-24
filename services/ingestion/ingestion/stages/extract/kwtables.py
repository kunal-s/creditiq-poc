"""Tables found by their column headings (FRD F-15.13; Epic 5 of the classification restructure).

One reader for every layout of a table (fields.yaml `table_keywords`): the header is the line, with up to
`header_span` lines below it, where the most configured headings match, as keywords match (case, punctuation and near
spellings folded); each column sits under the heading that names it; year columns are told apart by the date or year in
their headings and taken latest first, so the current year is not assumed to come first. A configured region opens with
`start_words`; the table ends at `end_words` or at a title line of another part. Rows are then read as every table is
(tables.build_table)."""

from __future__ import annotations

import re
from datetime import date

from ...config.models import ColRule, ColumnDef, IngestionConfig, KwEntry, KwTable, TableRule
from ...pageindex import Line, Page
from .. import keywords as K
from ..periods import DATE, _date_of, _year_end_of, in_line, vocab
from .normalise import to_number
from .tables import NUM_RX, Header, Seg, TableResult, build_table, repair_running_balance, segments

_YEAR = re.compile(r"\b(20\d{2})\b")


def _rule(spec: KwTable, defs: list[ColumnDef]) -> TableRule:
    """The table's rule for the row reader: its columns in the schema's order, the label first."""
    types = {d.name: d.type for d in defs}
    names = [spec.label] + [d.name for d in defs if d.name != spec.label] + [c for c in spec.ignore if c not in types]
    signed = set((spec.signed or {}).get(k) for k in ("amount", "marker")) - {None}
    names += [c for c in signed if c not in names]
    cols = [ColRule(name=n, header="", align=spec.align.get(n, "right" if types.get(n) == "number" or n == (spec.signed or {}).get("amount") else "left"),
                    emit=n not in spec.ignore or n in signed, join=spec.join.get(n, " ")) for n in names]
    return TableRule(start="", columns=cols, row_start=spec.row_start, row_start_col=spec.row_start_col,
                     text_only=spec.text_only, attach=spec.attach, skip_rows=spec.skip_rows, drop_lines=spec.drop_lines,
                     max_attach=spec.max_attach, multi_page=spec.multi_page, optional=spec.optional,
                     dash_is_zero=spec.dash_is_zero, repair=None if spec.signed else spec.repair, y_tol=spec.y_tol)


_WRAP_END = re.compile(r"(?:[:,&/\-]|\b(?:and|or|of|the|for|to|in|on|with|by))\s*$", re.I)


class KwHeader(Header):
    def __init__(self, cfg: IngestionConfig, spec: KwTable, gap: float, others: list[KwTable] | None = None,
                 label_type: str | None = None):
        self.cfg, self.spec, self.gap = cfg, spec, gap
        self.label_is_date = label_type == "date"
        self.others = [KwHeader(cfg, o, gap) for o in (others or []) if o is not spec]
        self.kw = cfg.keywords
        self.confused = self.kw.settings.matching.confused_digits if self.kw else None
        self.fy = self.kw.settings.identity.financial_year_start_month if self.kw else 4
        self.vocab = vocab(self.kw.settings.periods if self.kw else None)
        self.titles: dict[int, str] = {}
        self.start_gate = bool(spec.start_words)
        self.part_gate = bool(spec.part)
        self.footers: set[int] = set()
        self.drop_trailing_text = True
        self.row = re.compile(self.kw.settings.matching.table_row) if self.kw else None

    # --- matching ----------------------------------------------------------------------------------------------------

    def _matched(self, phrases: list[str], text: str, cover: float = 0.0) -> int:
        """The length of the longest of `phrases` the text holds (0: none): a more specific heading wins a segment. With
        `cover`, a phrase counts only when it makes up that share of the text's letters (a heading, not a sentence)."""
        letters = len(re.sub(r"[^0-9a-z]", "", text.lower())) or 1
        ok = [p for p in phrases if p.strip() and len(re.sub(r"[^0-9a-z]", "", p.lower())) >= cover * letters]
        if not self.kw:
            return max((len(p) for p in ok if p.lower() in text.lower()), default=0)
        z = K.Zones(text, "", "", confused=self.confused)
        return max((len(p) for p in ok if K._found(self.kw, KwEntry(phrase=p), z, "title")), default=0)

    def _has(self, phrases: list[str], text: str) -> bool:
        return self._matched(phrases, text) > 0

    def _period_date(self, text: str) -> date | None:
        got = [p.end for p in in_line(text, self.fy, self.vocab)]
        if got:
            return max(got)
        m = DATE.search(text)
        if m and (d := _date_of(m)):
            return d
        y = _YEAR.findall(text)
        return _year_end_of(max(int(x) for x in y), self.fy) if y else None

    # --- the header --------------------------------------------------------------------------------------------------

    def _block(self, lines: list[Line], i: int) -> tuple[int, int, dict[str, tuple[float, float]]] | None:
        """(score, header lines below the first, anchors) for a header opening at line i."""
        spec = self.spec
        first = lines[i]
        if self.row and self.row.search(first.text):
            return None
        if self._data(first):
            return None
        block = [first]
        for l in lines[i + 1:i + 1 + spec.header_span]:
            if self._data(l):
                break                          # the first row, not a heading
            block.append(l)
        # Each heading segment goes to the column whose heading it matches most specifically ("Value Date" is the value
        # date's, though it holds "Date"); each column takes the first segment it wins.
        anchors: dict[str, tuple[float, float]] = {}
        used = 0
        for li, line in enumerate(block):
            for sg in segments(line, self.gap):
                scores = [(self._matched(ph, sg.text, spec.heading_cover), col) for col, ph in spec.headings.items()
                          if col not in anchors]
                best = max(scores, default=(0, None))
                if best[0] and best[1]:
                    anchors[best[1]] = (sg.x0, sg.x1)
                    used = max(used, li)
        if not anchors or not any(self._matched(p, sg.text, spec.heading_cover)
                                  for sg in segments(first, self.gap) for p in spec.headings.values()):
            # The header line itself must name a column; a line above the table that happens to hold a year does not.
            if not self._dated(first):
                return None
        # Every line straight below the header that holds headings is part of it, though it names no new column (a
        # header printed twice, or wrapped).
        for li in range(1, len(block)):
            if li - 1 <= used and any(self._matched(ph, sg.text, spec.heading_cover)
                                      for sg in segments(block[li], self.gap) for ph in spec.headings.values()):
                used = max(used, li)
        periods = self._period_columns(block, anchors)
        for col, (seg, li) in zip([c for c in spec.periods if c not in anchors], periods):
            anchors[col] = (seg.x0, seg.x1)
            used = max(used, li)
        score = len([c for c in anchors if c in spec.headings]) + min(len(periods), len(spec.periods))
        if score < spec.min_headings:
            return None
        if spec.label not in anchors:
            others = [a[0] for a in anchors.values()]
            left = min(w.x0 for l in block for w in l.words)
            anchors[spec.label] = (left, max(left, min(others) - self.gap))
        return score, used, anchors

    def continues(self, previous: str, text: str) -> bool:
        """A label that is visibly unfinished (a bracket left open, or ending on a comma, colon, dash, ampersand or a
        joining word) carries on in the text-only line below it, as does a line starting in lower case."""
        prev = previous.strip()
        return bool(prev) and (prev.count("(") > prev.count(")") or bool(_WRAP_END.search(prev))
                               or text.strip()[:1].islower())

    def _data(self, line: Line) -> bool:
        """A line with an amount, or with a plain number that is not a year or a date: a row, not a heading."""
        if self.row and self.row.search(line.text):
            return True
        for sg in segments(line, self.gap):
            t = sg.text.strip()
            if NUM_RX.match(t) and not _YEAR.fullmatch(t) and t not in ("-",):
                return True
        return False

    def _dated(self, line: Line) -> bool:
        return any(self._period_date(sg.text) for sg in segments(line, self.gap))

    def _period_columns(self, block: list[Line], anchors: dict) -> list[tuple[Seg, int]]:
        """The block's year columns, latest first: segments that name a date or year, merged with those above or below
        them in the same column, not under a configured heading."""
        taken = list(anchors.values())
        cols: list[list[tuple[Seg, int, date | None]]] = []
        for li, line in enumerate(block):
            for sg in segments(line, self.gap):
                d = self._period_date(sg.text)
                if d is None and not (self.kw and self._has(self.kw.settings.periods.column_headings, sg.text)):
                    continue
                if any(sg.x0 < b and a < sg.x1 for a, b in taken):
                    continue
                home = next((c for c in cols if any(sg.x0 < s.x1 and s.x0 < sg.x1 for s, _, _ in c)), None)
                if home is None:
                    cols.append([(sg, li, d)])
                else:
                    home.append((sg, li, d))
        dated = [(max((d for _, _, d in c if d), default=None), c) for c in cols]
        dated = [(d, c) for d, c in dated if d]
        if not dated:
            return []
        # Latest first; columns printing the same date keep their left-to-right order.
        dated.sort(key=lambda dc: (-dc[0].toordinal(), dc[1][0][0].x0))
        out = []
        for _, c in dated:
            x0, x1 = min(s.x0 for s, _, _ in c), max(s.x1 for s, _, _ in c)
            out.append((Seg(c[0][0].text, x0, x1, [w for s, _, _ in c for w in s.words]), max(li for _, li, _ in c)))
        return out

    def _opens(self, line: Line) -> bool:
        """Whether the line opens the region the header is looked for in: one of the table's start words (where the
        document prints any), or a title of its part (where the document titles its parts)."""
        if self.start_gate and self._has(self.spec.start_words, line.text):
            return True
        if self.part_gate and id(line) in self.titles:
            from ..pages import _titles_of
            return self.spec.part in _titles_of(self.kw, line.text)
        return False

    def _search(self, lines: list[Line], gated: bool = True) -> tuple[int, int, int, dict] | None:
        """The best header among the lines: under the part's title or start words when the table has them (a profit and
        loss is not read from the balance sheet above it); a repeated header on a later page needs neither."""
        spec = self.spec
        open_ = not gated or not (spec.start_words or spec.part)
        best = None
        for i, line in enumerate(lines):
            if not open_:
                open_ = self._opens(line)
                if not open_:
                    continue
            got = self._block(lines, i)
            # A header another table of the document names more fully is that table's (IGST, CGST and SGST head both
            # a return's outward supplies and its input tax credit; "taxable value" only the first).
            if got and any((o := other._block(lines, i)) and o[0] > got[0] for other in self.others):
                got = None
            if got and (best is None or got[0] > best[0]):
                best = (got[0], i, got[1], got[2])
                if got[0] >= len(spec.headings) + len(spec.periods):
                    break                      # every heading named: no better header below
            elif best is not None and i > best[1] + spec.header_span:
                break                          # the header found is the table's; a later one is another table's
        return best

    def find(self, pages: list[Page]):
        for p in pages:
            self._mark_titles(p)
        # Start words gate the search where the document prints any (a return that does not number its tables is
        # searched everywhere); the part's title gates it where the document titles any part, so a balance sheet is
        # not read from the profit and loss page of statements that have none, while an untitled spreadsheet is.
        from ..pages import _titles_of
        lines = [l for p in pages for l in p.content_lines()]
        self.start_gate = bool(self.spec.start_words) and any(self._has(self.spec.start_words, l.text) for l in lines)
        self.part_gate = bool(self.spec.part and self.kw) and any(_titles_of(self.kw, self.titles[id(l)])
                                                                 for l in lines if id(l) in self.titles)
        titled = self.start_gate or self.part_gate
        for pi, p in enumerate(pages):
            got = self._search(p.content_lines(), gated=titled)
            if got:
                _, li, extra, anchors = got
                return pi, li, extra, anchors
        return None

    def repeat(self, lines: list[Line]):
        got = self._search(lines, gated=False)
        return (got[1], got[2], got[3]) if got else None

    # --- the end -----------------------------------------------------------------------------------------------------

    def _mark_titles(self, page: Page) -> None:
        if not self.kw:
            return
        for l, z in K.line_zones(self.kw, page):
            if z == "title":
                self.titles[id(l)] = l.text
            elif z == "footer":
                self.footers.add(id(l))

    def drops(self, line: Line) -> bool:
        return id(line) in self.footers

    def ends(self, line: Line) -> bool:
        spec = self.spec
        # End words end the table on a heading line, never on a row (a "5." heading, not the 5 of "5,18,590").
        if spec.end_words and not self._data(line) and self._has(spec.end_words, line.text):
            return True
        first = K.fold(line.text, self.confused).split()[:1]
        if first and any(K.fold(w, self.confused) == first[0] for w in spec.end_starts):
            return True
        # The header of another table of the same document ends this one.
        if any(o._block([line], 0) for o in self.others):
            return True
        if spec.part and self.kw and id(line) in self.titles:
            from ..pages import _titles_of
            others = _titles_of(self.kw, line.text) - {spec.part}
            return bool(others)
        return False


def read(cfg: IngestionConfig, spec: KwTable, defs: list[ColumnDef], pages: list[Page],
         others: list[KwTable] | None = None) -> TableResult | None:
    """The table, by its headings; `others` are the document type's other tables, whose headers end it."""
    label_type = next((d.type for d in defs if d.name == spec.label), None)
    header = KwHeader(cfg, spec, cfg.routing.reading.column_gap, others, label_type)
    for p in pages:
        header._mark_titles(p)
    res = build_table(_rule(spec, defs), defs, pages, cfg.routing.reading, header)
    if res is None:
        return None
    res.method = "keywords"
    if spec.signed:
        _split_signed(res, spec, cfg)
        if spec.repair and spec.repair.get("kind") == "running_balance":
            repair_running_balance(res, spec.repair, {d.name: d.type for d in defs})
    return res


def _split_signed(res: TableResult, spec: KwTable, cfg: IngestionConfig) -> None:
    """Each row's single amount put in its debit or credit column, by the row's marker (its own column, or printed
    with the figure) or else by its sign; the amount and marker columns are not reported."""
    s = spec.signed or {}
    amt, mark, debit, credit = s.get("amount"), s.get("marker"), s.get("debit", "debit"), s.get("credit", "credit")
    forms = cfg.fields.numbers
    dr = {w.lower().rstrip(".") for w in forms.debit_markers}
    cr = {w.lower().rstrip(".") for w in forms.credit_markers}
    for row in res.rows:
        raw = row["raw"]
        if row["cells"].get(debit) is None and row["cells"].get(credit) is None and raw.get(amt):
            text = raw[amt]
            marker = (raw.get(mark) or "").strip().lower().rstrip(".")
            suffix = re.search(r"(?i)\b([a-z]{2})\.?\s*$", text)
            word = marker or (suffix.group(1).lower() if suffix else "")
            value = to_number(re.sub(r"(?i)\b[a-z]{2}\.?\s*$", "", text).strip()) if suffix else to_number(text)
            if value is not None:
                is_debit = word in dr or (word not in cr and value < 0)
                row["cells"][debit if is_debit else credit] = abs(value)
        for k in (amt, mark):
            raw.pop(k, None)


def candidate_pages(cfg: IngestionConfig, spec: KwTable, pages: list[Page]) -> list[Page]:
    """The pages to show the model for a table no header was found for (Story 6.7): those where the table's part scores
    as a page placed by keywords does, or, for a table with no part, those holding the most of its headings, or else the
    document's first pages; at most `model_pages`, in page order."""
    kw = cfg.keywords
    if kw and spec.part and spec.part in kw.parts:
        th = kw.settings.page_threshold
        hit = [p for p in pages if K.part_scores(kw, p)[spec.part].score >= th]
        return hit[:spec.model_pages]
    header = KwHeader(cfg, spec, cfg.routing.reading.column_gap)
    counted = []
    for p in pages:
        n = sum(1 for l in p.content_lines() for ph in spec.headings.values() if header._has(ph, l.text))
        if n >= 2:
            counted.append((n, p))
    best = sorted(counted, key=lambda x: -x[0])[:spec.model_pages]
    if not best:
        return pages[:spec.model_pages]     # nothing names it: the document's own pages, in order
    return sorted((p for _, p in best), key=lambda p: p.no)
