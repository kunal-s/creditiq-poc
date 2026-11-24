"""Page typing by keywords (FRD F-09, decision 14; config/ingestion/keywords.yaml).

A page is read into zones: its title lines (not a table row, and either in the header band or standing out in print:
larger than the page's body text or bold on a digital page, taller letters on a scan), its footer band, and its body.
Each part (a balance sheet, an auditor's report, a page of transactions) is scored on a page from its title, content
and warning phrases; each document type is scored over a run of pages from the best of its parts and its own words,
which tell look-alike types apart. Matching folds case, punctuation, hyphen-broken and spaced-out words; a phrase of
`fuzzy.min_length` letters or more also matches a near spelling, a shorter one only exactly.

`score_types` returns what the signal scorer of classify.py returns, so classification, the second pass and the
model's guard read either scorer the same way."""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass

from rapidfuzz.distance import Levenshtein

from functools import lru_cache

from ..config.models import IngestionConfig, KeywordsConfig, KwEntry, KwMatching, KwWords
from ..pageindex import Page
from .extract.identifiers import PATTERNS

_DEFAULT = KwMatching()


@lru_cache(maxsize=32)
def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern)
_DASHES = {ord(c): "-" for c in "‐‑‒–—―−"}
_DROP = {ord(c): None for c in "​‌‍­﻿'’‘`"}


def fold(text: str, confused: dict[str, str] | None = None) -> str:
    """What phrases are matched against: compatibility forms folded, apostrophes dropped, a word broken by a hyphen
    at a line end joined, runs of three or more single letters joined ("S T A T E M E N T"), lower case, and every
    other mark a space."""
    t = unicodedata.normalize("NFKC", text).translate(_DASHES).translate(_DROP)
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    t = re.sub(r"(?<!\w)(?:\w ){2,}\w(?!\w)", lambda m: m.group(0).replace(" ", ""), t)
    t = re.sub(r"[^0-9a-z&]+", " ", t.lower())
    table = str.maketrans({k: v.lower() for k, v in (_DEFAULT.confused_digits if confused is None else confused).items()})
    return " ".join(_letters(w, table) for w in t.split())


def _letters(word: str, table: dict) -> str:
    """A word with letters and a digit a scan confuses with a letter (keywords.yaml matching.confused_digits) is read as
    letters: "B0ARD" is board. A number, or a code that starts with a digit (3b, 26as), is left as it is."""
    if sum(c.isalpha() for c in word) >= 2 and any(ord(c) in table for c in word) and not word[:1].isdigit():
        return word.translate(table)
    return word


@dataclass
class Zones:
    title: str
    footer: str
    body: str
    confused: dict[str, str] | None = None

    def __post_init__(self) -> None:
        self.f = {k: fold(getattr(self, k), self.confused) for k in ("title", "footer", "body")}

    @staticmethod
    def join(zs: list[Zones]) -> Zones:
        return Zones(*("\n".join(getattr(z, k) for z in zs) for k in ("title", "footer", "body")),
                     confused=zs[0].confused if zs else None)


def zones(kw: KeywordsConfig, page: Page) -> Zones:
    """The page's title lines, footer and body; kept on the page, since every scorer of a run asks again."""
    cached = getattr(page, "_kw_zones", None)
    if cached is not None:
        return cached
    labels = line_zones(kw, page)
    out = Zones(*("\n".join(l.text for l, z in labels if z == k) for k in ("title", "footer", "body")),
                confused=kw.settings.matching.confused_digits)
    page._kw_zones = out  # type: ignore[attr-defined]
    return out


def line_zones(kw: KeywordsConfig, page: Page) -> list[tuple]:
    """Each content line of the page with its zone: title, footer or body."""
    cached = getattr(page, "_kw_lines", None)
    if cached is not None:
        return cached
    z = kw.settings.zones
    labelled: list[tuple] = []
    lines = page.content_lines()
    if not page.height:
        # A spreadsheet's sheet has no page to place a line on: no header band, no footer band, no print.
        labelled = [(l, "body") for l in lines]
        page._kw_lines = labelled  # type: ignore[attr-defined]
        return labelled
    sized = [w for l in lines for w in l.words if w.size]
    if sized:
        by_size: Counter = Counter()
        for w in sized:
            by_size[w.size] += len(w.text)
        body_size = by_size.most_common(1)[0][0]
    heights = [statistics.median([w.y1 - w.y0 for w in l.words]) for l in lines] if lines else []
    typical = statistics.median(heights) if heights else 0.0
    for l, h in zip(lines, heights):
        top = min(w.y0 for w in l.words) / (page.height or 1)
        row = _rx(kw.settings.matching.table_row).search(l.text) is not None
        if row:
            stands_out = False
        elif sized:
            chars = sum(len(w.text) for w in l.words) or 1
            stands_out = (max((w.size or 0.0) for w in l.words) >= z.title_size_ratio * body_size
                          or sum(len(w.text) for w in l.words if w.bold) >= z.title_bold_share * chars)
        else:
            stands_out = h >= z.title_height_ratio * typical
        if stands_out or (top <= z.header_band and not row):
            labelled.append((l, "title"))
        elif top >= 1 - z.footer_band:
            labelled.append((l, "footer"))
        else:
            labelled.append((l, "body"))
    page._kw_lines = labelled  # type: ignore[attr-defined]
    return labelled


def _found(kw: KeywordsConfig, e: KwEntry, z: Zones, zone: str, *, exact: bool = False) -> bool:
    """Whether the entry is in the zone: an identifier by its format; a phrase exactly, word for word, or, when it has
    `fuzzy.min_length` letters or more and `exact` is not asked, as a near spelling: a run of as many whole words, each
    within its share of wrong letters (a word too short to have a share must match exactly), or a run of one word more
    or fewer (a word split or joined by a scan) whose letters, spaces aside, are within the phrase's share."""
    if e.identifier:
        return re.search(PATTERNS[e.identifier], getattr(z, zone)) is not None
    text = z.f[zone]
    p = fold(e.phrase or "", kw.settings.matching.confused_digits)
    if not p or not text:
        return False
    if f" {p} " in f" {text} ":
        return True
    f = kw.settings.fuzzy
    if exact or len(p.replace(" ", "")) < f.min_length:
        return False
    words = text.split()
    want = p.split()
    joined = p.replace(" ", "")
    share = 1 - f.min_ratio

    def near(a: str, b: str) -> bool:
        # A near spelling never changes a number: form numbers and codes (GSTR-9, 3B, ITR-6) tell documents apart.
        if re.sub(r"\D", "", a) != re.sub(r"\D", "", b):
            return False
        allowed = int(len(a) * share)
        return a == b if allowed == 0 else Levenshtein.distance(a, b, score_cutoff=allowed) <= allowed

    n = len(want)
    for i in range(len(words) - n + 1):
        if all(near(a, b) for a, b in zip(want, words[i:i + n])):
            return True
    for size in {max(1, n - 1), n + 1} - {n}:
        for i in range(len(words) - size + 1):
            if near(joined, "".join(words[i:i + size])):
                return True
    return False


@dataclass
class Score:
    score: float
    ruled_out: str | None
    title: list[str]
    content: list[str]
    warnings: list[str]
    titled: bool


def score_words(kw: KeywordsConfig, words: KwWords, z: Zones, *, needs_title: bool = False) -> Score:
    s = kw.settings
    total, titled = 0.0, False
    title_hits, content_hits, warn_hits = [], [], []
    for e in words.title:
        if _found(kw, e, z, "title"):
            total += e.weight * s.zone_weights.get("title", 3)
            titled = True
            title_hits.append(e.phrase or e.identifier or "")
        elif _found(kw, e, z, "footer"):
            total += e.weight * s.zone_weights.get("footer", 2)
            title_hits.append(e.phrase or e.identifier or "")
    for e in words.content:
        if any(_found(kw, e, z, k) for k in ("title", "footer", "body")):
            total += e.weight
            content_hits.append(e.phrase or e.identifier or "")
    ruled_out = None
    for e in words.warning:
        name = e.phrase or e.identifier or ""
        # A warning matches only exactly: the near spellings that matter are opposites (audited, unaudited).
        if e.zone == "title":
            if _found(kw, e, z, "title", exact=True):
                ruled_out = ruled_out or name
                warn_hits.append(name)
        elif any(_found(kw, e, z, k, exact=True) for k in ("title", "footer", "body")):
            total -= e.weight
            warn_hits.append(name)
    full = words.full or s.full
    sc = max(0.0, min(total, full) / full)
    if ruled_out or (needs_title and not titled):
        sc = 0.0
    return Score(round(sc, 4), ruled_out, title_hits, content_hits, warn_hits, titled)


def part_scores(kw: KeywordsConfig, page: Page) -> dict[str, Score]:
    cached = getattr(page, "_kw_parts", None)
    if cached is not None:
        return cached
    z = zones(kw, page)
    out = {n: score_words(kw, p, z, needs_title=p.needs_title) for n, p in kw.parts.items()}
    page._kw_parts = out  # type: ignore[attr-defined]
    return out


def _best_part(ps: dict[str, Score]) -> str:
    return max(ps, key=lambda n: (ps[n].score, n))


def within(cfg: IngestionConfig, part_type: str, doc_type: str) -> bool:
    """Whether every part of `part_type` is also a part of `doc_type`: its pages may belong to a document of that type
    (an acknowledgement inside a return)."""
    kw = cfg.keywords
    if kw is None or part_type == doc_type or part_type not in kw.types or doc_type not in kw.types:
        return False
    return set(kw.types[part_type].parts) <= set(kw.types[doc_type].parts)


def score_types(cfg: IngestionConfig, pages: list[Page]) -> list[dict]:
    """Every enabled type scored over `pages` taken as one run, best first, in the shape classify.score_types gives:
    a type's score is its best part on any page, scaled by its own words over the run when it has any (so audited and
    provisional statements, which share their parts, are told apart); eligible when it reaches the page threshold, no
    title warning rules it out, and a part it needs is placed in the run. A type whose parts are all among another
    eligible type's parts yields to it (an acknowledgement filed with its computation is read as the return)."""
    kw = cfg.keywords
    assert kw is not None
    s = kw.settings
    enabled = cfg.document_types.enabled_ids()
    pages = [p for p in pages if not p.blank]
    per_page = [part_scores(kw, p) for p in pages]
    run = Zones.join([zones(kw, p) for p in pages]) if pages else Zones("", "", "")
    rows: dict[str, dict] = {}
    for tid, t in kw.types.items():
        if tid not in enabled:
            continue
        best, best_part = 0.0, None
        for ps in per_page:
            for pn in t.parts:
                if ps[pn].score > best:
                    best, best_part = ps[pn].score, pn
        own = score_words(kw, t, run) if t.has_words() else None
        base = s.scoring.lookalike_base
        score = best * (base + (1 - base) * own.score) if own else best
        # A needed part counts on a page where it is the best part: an acknowledgement that also names the return is
        # not a page of the return's form.
        needs = (not t.needs_part) or any(_best_part(ps) in t.needs_part and ps[_best_part(ps)].score >= s.page_threshold
                                          for ps in per_page)
        if not needs:
            score *= s.scoring.missing_part_factor
        ruled = own.ruled_out if own else None
        hits = next((ps[best_part] for ps in per_page if best_part and ps[best_part].score == best), None)
        signals = {"required": (hits.title if hits else []) + (own.title if own else []),
                   "supporting": (hits.content if hits else []) + (own.content if own else []),
                   "contrary": ([ruled] if ruled else []) + ([f"needs one of: {', '.join(t.needs_part)}"] if not needs else []),
                   "part": best_part, "own": own.score if own else 0.0}
        rows[tid] = {"type": tid, "score": round(0.0 if ruled else score, 4),
                     "eligible": bool(not ruled and needs and score >= s.page_threshold), "signals": signals}
    # A default type (audited statements) takes pages of the parts it shares when no look-alike's own words claim them:
    # provisional and projected statements say what they are.
    for tid, t in kw.types.items():
        r = rows.get(tid)
        if not (t.default and r and r["signals"]["part"]) or r["signals"]["contrary"] or r["score"] >= 1:
            continue
        mates = [o for o, ot in kw.types.items() if o != tid and o in rows and set(ot.parts) & set(t.parts)]
        if not any(rows[o]["signals"].get("own", 0) > 0 for o in mates):
            best = max((ps[pn].score for ps in per_page for pn in t.parts), default=0.0)
            r["score"] = round(max(r["score"], best), 4)
            r["eligible"] = r["score"] >= s.page_threshold
    for tid, r in rows.items():
        if not r["eligible"]:
            continue
        mine = set(kw.types[tid].parts)
        if any(o != tid and rows[o]["eligible"] and mine < set(kw.types[o].parts) for o in rows):
            r["score"] = round(r["score"] * s.scoring.subsumed_factor, 4)
            r["eligible"] = r["score"] >= s.page_threshold
    out = sorted(rows.values(), key=lambda r: (-r["score"], r["type"]))
    return out
