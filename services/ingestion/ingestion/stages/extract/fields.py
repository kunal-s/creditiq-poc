"""The deterministic pass for scalar and list fields (FRD F-15.2): identifier scan, label
aliases, patterns. Everything is read from the page index; nothing is inferred."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ...config.models import FieldRule, Pattern, re_flags
from ...pageindex import Page
from ...util import collapse_ws
from . import identifiers
from .evidence import Evidence, evidence_for_lines, lines_overlapping


@dataclass
class Found:
    raw: object            # str, or list[str] for array fields
    method: str            # identifier | alias | pattern | model
    evidence: Evidence


def _pages(pages: list[Page], rule: FieldRule) -> list[Page]:
    if not rule.page_match:
        return pages
    rx = re.compile(rule.page_match, re.I | re.M)
    return [p for p in pages if rx.search(p.text())]


def _identifier(kind: str, pages: list[Page]) -> Iterator[Found]:
    for p in pages:
        text = p.text()
        m = identifiers.find(kind, text)
        if m:
            ev = evidence_for_lines(p, lines_overlapping(p, m.start(), m.end()))
            yield Found(m.group(0), "identifier", ev)


def _alias(aliases: list[str], rule: FieldRule, pages: list[Page]) -> Iterator[Found]:
    for alias in aliases:
        rx = re.compile(r"(?:^|\s{2})(?:%s)(?=\s|:|$)" % alias, re.I)
        for p in pages:
            lines = p.content_lines()
            for i, line in enumerate(lines):
                m = rx.search(line.text)
                if not m:
                    continue
                rest = line.text[m.end():]
                lead = len(rest) - len(rest.lstrip(" :"))
                start = m.end() + lead
                rest = rest.lstrip(" :")
                src_line, base = line, start
                if not rest.strip():
                    if not rule.next_line or i + 1 >= len(lines):
                        continue
                    src_line, base, rest = lines[i + 1], 0, lines[i + 1].text
                if rule.take == "segment":
                    seg = re.split(r"\s{2,}", rest, maxsplit=1)[0]
                else:
                    seg = rest
                seg = seg.strip()
                if not seg:
                    continue
                a = base + (len(rest) - len(rest.lstrip()))
                ev = evidence_for_lines(p, [(src_line, a, a + len(seg))])
                yield Found(seg, "alias", ev)


def _split_elems(pat: Pattern, captured: str) -> list[str]:
    parts = re.split(pat.split, collapse_ws(captured)) if pat.split else [collapse_ws(captured)]
    out = []
    for part in parts:
        if pat.strip:
            part = re.sub(pat.strip, "", part)
        part = part.strip(" .,;")
        if part:
            out.append(part)
    return out


def _spanning(pat: Pattern, pages: list[Page]) -> Iterator[Found]:
    """One regex over the pages joined; evidence starts on the page where the value starts."""
    rx = re.compile(pat.regex, re_flags(pat.flags))
    texts = [p.text() for p in pages]
    offs, pos = [], 0
    for t in texts:
        offs.append(pos)
        pos += len(t) + 1
    m = rx.search("\n".join(texts))
    if not m or m.group(pat.group) is None:
        return
    s, e = m.start(pat.group), m.end(pat.group)
    parts_ev = []
    for p, o, t in zip(pages, offs, texts):
        if o < e and o + len(t) > s:
            parts_ev.append(evidence_for_lines(p, lines_overlapping(p, max(s - o, 0), min(e - o, len(t)))))
    ev = parts_ev[0]
    ev.line_ids = [i for x in parts_ev for i in x.line_ids]
    yield Found(collapse_ws(m.group(pat.group)), "pattern", ev)


def _pattern(pats: list[Pattern], pages: list[Page]) -> Iterator[Found]:
    for pat in pats:
        if pat.span_pages and not pat.multi:
            yield from _spanning(pat, pages)
            continue
        rx = re.compile(pat.regex, re_flags(pat.flags))
        if pat.multi:
            vals, evs = [], []
            for p in pages:
                text = p.text()
                for m in rx.finditer(text):
                    g = m.group(pat.group)
                    if g is None:
                        continue
                    vals += _split_elems(pat, g)
                    evs.append(evidence_for_lines(p, lines_overlapping(p, m.start(pat.group), m.end(pat.group))))
            if vals:
                ev = evs[0]
                ev.line_ids = [i for e in evs for i in e.line_ids]
                yield Found(vals, "pattern", ev)
            continue
        for p in pages:
            text = p.text()
            for m in rx.finditer(text):
                if m.group(pat.group) is None:
                    continue
                s, e = m.start(pat.group), m.end(pat.group)
                ev = evidence_for_lines(p, lines_overlapping(p, s, e))
                yield Found(collapse_ws(m.group(pat.group)), "pattern", ev)


def candidates(rule: FieldRule, pages: list[Page]) -> Iterator[Found]:
    """Every place the rule finds a value, in a fixed order: identifier scan, then label aliases (in
    the order configured, each over the pages in order), then patterns."""
    cand = _pages(pages, rule)
    if rule.identifier:
        yield from _identifier(rule.identifier, cand)
    if rule.aliases:
        yield from _alias(rule.aliases, rule, cand)
    if rule.patterns:
        yield from _pattern(rule.pattern_list(), cand)


def extract_scalar(rule: FieldRule, pages: list[Page], accept: Callable[[Found], bool] | None = None) -> Found | None:
    """The first candidate `accept` allows, so a label that is followed by something that is not a
    value (a heading, a sentence) does not hide the real one further down. When none is accepted the
    first candidate is returned, so the field is reported with the text as printed and why it failed."""
    first = None
    for f in candidates(rule, pages):
        if first is None:
            first = f
        if accept is None or accept(f):
            return f
    return first
