"""Stage 3b: group pages into instances (FRD F-08.3). A file may hold several instances of one
type; a page matching the type's `start` pattern opens a new one and earlier pages are front matter."""

from __future__ import annotations

import re
from typing import Callable

from ..config.models import IngestionConfig
from ..pageindex import Page


def split_instances(cfg: IngestionConfig, doc_type: str, pages: list[Page]) -> tuple[list[int], list[list[Page]]]:
    """(front_matter_page_numbers, [pages of instance 1, pages of instance 2, ...])"""
    real = [p for p in pages if not p.blank]
    rule = cfg.signals.types[doc_type].instances
    if not rule:
        return [], [real] if real else []
    n = cfg.signals.head_lines

    def text(p: Page) -> str:
        if rule.zone == "head":
            return "\n".join(l.text for l in p.content_lines()[:n])
        return p.text()

    if rule.key_pattern:
        if rule.first_key_pattern:
            first = re.compile(rule.first_key_pattern, re.I | re.M)
            if any(first.search(text(p)) for p in real):
                return _lead(rule.leading, real, *_by_key(first, real, text))
        return _lead(rule.leading, real, *_by_key(re.compile(rule.key_pattern, re.I | re.M), real, text))
    rx = re.compile(rule.start, re.I | re.M)
    starts = [i for i, p in enumerate(real) if rx.search(text(p))]
    if not starts:
        return [], [real] if real else []
    front = [p.no for p in real[:starts[0]]]
    groups = []
    for a, b in zip(starts, starts[1:] + [len(real)]):
        groups.append(real[a:b])
    return _lead(rule.leading, real, front, groups)


def _lead(leading: str, real: list[Page], front: list[int], groups: list[list[Page]]) -> tuple[list[int], list[list[Page]]]:
    """Pages before the first instance stay front matter, or (`leading: first`) open the first instance."""
    if leading != "first" or not front or not groups:
        return front, groups
    lead = [p for p in real if p.no in set(front)]
    return [], [lead + groups[0], *groups[1:]]


def _norm_key(v: str) -> str:
    return re.sub(r"[\s\-/,.]+", "", v).upper()


def _by_key(rx: re.Pattern, real: list[Page], text: Callable[[Page], str]) -> tuple[list[int], list[list[Page]]]:
    """A page that names a different key value opens a new instance; a page that names none (a
    continuation, a cover sheet) stays with the instance before it. Pages before the first key are
    front matter. A key on every page of one return therefore never splits it."""
    groups: list[list[Page]] = []
    current: str | None = None
    front: list[int] = []
    for p in real:
        keys = {_norm_key(m) for m in rx.findall(text(p))}
        if keys and (current is None or current not in keys):
            current = sorted(keys)[0]
            groups.append([p])
        elif groups:
            groups[-1].append(p)
        else:
            front.append(p.no)
    if not groups:
        return [], [real] if real else []
    return front, groups
