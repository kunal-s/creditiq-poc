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
from .tables import NUM_RX, Header, Seg, TableResult, build_table, segments

_YEAR = re.compile(r"\b(20\d{2})\b")


def _rule(spec: KwTable, defs: list[ColumnDef]) -> TableRule:
    """The table's rule for the row reader: its columns in the schema's order, the label first."""
    types = {d.name: d.type for d in defs}
    names = [spec.label] + [d.name for d in defs if d.name != spec.label] + [c for c in spec.ignore if c not in types]
    cols = [ColRule(name=n, header="", align=spec.align.get(n, "right" if types.get(n) == "number" else "left"),
                    emit=n not in spec.ignore, join=spec.join.get(n, " ")) for n in names]
    return TableRule(start="", columns=cols, row_start=spec.row_start, row_start_col=spec.row_start_col,
                     text_only=spec.text_only, attach=spec.attach, skip_rows=spec.skip_rows, drop_lines=spec.drop_lines,
                     max_attach=spec.max_attach, multi_page=spec.multi_page, optional=spec.optional,
                     dash_is_zero=spec.dash_is_zero, repair=spec.repair, y_tol=spec.y_tol)


class KwHeader(Header):
    def __init__(self, cfg: IngestionConfig, spec: KwTable, gap: float, others: list[KwTable] | None = None):
        self.cfg, self.spec, self.gap = cfg, spec, gap
        self.others = [KwHeader(cfg, o, gap) for o in (others or []) if o is not spec]
        self.kw = cfg.keywords
        self.confused = self.kw.settings.matching.confused_digits if self.kw else None
        self.fy = self.kw.settings.identity.financial_year_start_month if self.kw else 4
        self.vocab = vocab(self.kw.settings.periods if self.kw else None)
        self.titles: dict[int, str] = {}
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
        """Whether the line opens the region the header is looked for in: a title of the table's part, or one of its
        start words."""
        if self.spec.start_words and self._has(self.spec.start_words, line.text):
            return True
        if self.spec.part and self.kw and id(line) in self.titles:
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
            if got and (best is None or got[0] > best[0]):
                best = (got[0], i, got[1], got[2])
                if got[0] >= len(spec.headings) + len(spec.periods):
                    break                      # every heading named: no better header below
            elif best is not None and i > best[1] + spec.header_span:
                break                          # the header found is the table's; a later one is another table's
        return best

    def find(self, pages: list[Page]):
        for pi, p in enumerate(pages):
            self._mark_titles(p)
            got = self._search(p.content_lines())
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
        if spec.end_words and self._has(spec.end_words, line.text):
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
    header = KwHeader(cfg, spec, cfg.routing.reading.column_gap, others)
    for p in pages:
        header._mark_titles(p)
    res = build_table(_rule(spec, defs), defs, pages, cfg.routing.reading, header)
    if res is not None:
        res.method = "keywords"
    return res
