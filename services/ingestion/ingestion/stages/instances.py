"""Stage 3b: group pages into instances (FRD F-08.3). A file may hold several instances of one
type; a page matching the type's `start` pattern opens a new one and earlier pages are front matter."""

from __future__ import annotations

import re

from ..config.models import IngestionConfig
from ..pageindex import Page


def split_instances(cfg: IngestionConfig, doc_type: str, pages: list[Page]) -> tuple[list[int], list[list[Page]]]:
    """(front_matter_page_numbers, [pages of instance 1, pages of instance 2, ...])"""
    real = [p for p in pages if not p.blank]
    rule = cfg.signals.types[doc_type].instances
    if not rule:
        return [], [real] if real else []
    rx = re.compile(rule.start, re.I | re.M)
    starts = [i for i, p in enumerate(real) if rx.search(p.text())]
    if not starts:
        return [], [real] if real else []
    front = [p.no for p in real[:starts[0]]]
    groups = []
    for a, b in zip(starts, starts[1:] + [len(real)]):
        groups.append(real[a:b])
    return front, groups
