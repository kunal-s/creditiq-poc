#!/usr/bin/env python3
"""Suggest keywords for each document type from marked-up sample pages (Story 1.3 of the classification restructure).

    services/ingestion/.venv/bin/python scripts/mine_keywords.py [--key workflow/baseline/expected.yaml] [--top 25]

For every type in the answer key, lists the phrases (one to four words) found on many of the type's pages and on few
pages of any other type, separately for the title zone (header band and large print, table rows left out) and the
rest of the page. It only suggests: a person chooses the keyword lists (config/ingestion/keywords.yaml). The pages'
zones are cached in workflow/baseline/pages.json for the scorer prototype.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion"))

from ingestion.config.loader import load_dir  # noqa: E402
from ingestion.stages.read import read_document  # noqa: E402

AMOUNT = re.compile(r"\d{1,3}(,\d{2,3})+(\.\d+)?")


def fold(s: str) -> str:
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9'&\-]+", " ", s)
    return " ".join(s.split())


def zones(page, z: dict) -> dict[str, list[str]]:
    """The page's title lines, footer and body (keywords.yaml `zones`)."""
    lines = page.content_lines()
    out: dict[str, list[str]] = {"title": [], "body": [], "footer": []}
    if not lines:
        return out
    sized = [w for l in lines for w in l.words if w.size]
    if sized:  # digital page: the body size is the size most characters are printed in
        by_size: Counter = Counter()
        for w in sized:
            by_size[w.size] += len(w.text)
        body = by_size.most_common(1)[0][0]
    heights = [statistics.median([w.y1 - w.y0 for w in l.words]) for l in lines]
    median = statistics.median(heights)
    for l, h in zip(lines, heights):
        top = min(w.y0 for w in l.words) / (page.height or 1)
        if AMOUNT.search(l.text):
            stands_out = False
        elif sized:
            chars = sum(len(w.text) for w in l.words)
            stands_out = (max((w.size or 0) for w in l.words) >= z["title_size_ratio"] * body
                          or sum(len(w.text) for w in l.words if w.bold) >= z["title_bold_share"] * chars)
        else:
            stands_out = h >= z["title_height_ratio"] * median
        if stands_out or (top <= z["header_band"] and not AMOUNT.search(l.text)):
            out["title"].append(l.text)
        elif top >= 1 - z["footer_band"]:
            out["footer"].append(l.text)
        else:
            out["body"].append(l.text)
    return out


def pages_of(key: dict, cfg, kw: dict) -> list[dict]:
    z = kw["settings"]["zones"]
    out = []
    for rel, docs in key.items():
        exp = {}
        for d in docs:
            for n in range(d["pages"][0], d["pages"][1] + 1):
                exp[n] = (d["type"] or "(none)").rstrip("*")
        for p in read_document((ROOT / rel).read_bytes(), "pdf", cfg.quality, cfg.routing, None):
            out.append({"file": rel, "page": p.no, "type": exp.get(p.no, "(none)"),
                        **zones(p, z)})
    return out


def grams(lines: list[str]) -> set[str]:
    out = set()
    for l in lines:
        w = [t for t in fold(l).split() if not t.isdigit()]
        for n in range(1, 5):
            for i in range(len(w) - n + 1):
                g = " ".join(w[i:i + n])
                if len(g) >= 3:
                    out.add(g)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=str(ROOT / "workflow" / "baseline" / "expected.yaml"))
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    kw = yaml.safe_load((ROOT / "config" / "ingestion" / "keywords.yaml").read_text())
    cache = ROOT / "workflow" / "baseline" / "pages.json"
    pages = pages_of(yaml.safe_load(Path(a.key).read_text()), load_dir(ROOT / "config" / "ingestion"), kw)
    cache.write_text(json.dumps(pages))
    by_type: dict[str, list[dict]] = defaultdict(list)
    for p in pages:
        by_type[p["type"]].append(p)
    for zone in ("title", "body"):
        df: dict[str, Counter] = {t: Counter(g for p in ps for g in grams(p[zone] + (p["footer"] if zone == "title" else [])))
                                  for t, ps in by_type.items()}
        print(f"\n######## {zone} zone")
        for t, ps in sorted(by_type.items()):
            if t == "(none)":
                continue
            n = len(ps)
            others = [o for o in by_type if o != t]
            rows = []
            for g, c in df[t].items():
                inside = c / n
                outside = max((df[o][g] / len(by_type[o]) for o in others), default=0)
                if inside >= 0.3 and outside <= 0.2:
                    rows.append((inside - outside, inside, outside, g))
            rows.sort(key=lambda r: (-r[0], -len(r[3])))
            # Keep the longest phrase among those that contain one another, so the list is not ten cuts of one title.
            kept: list[tuple] = []
            for r in rows:
                if not any(r[3] in k[3] and abs(r[1] - k[1]) < 0.05 for k in kept):
                    kept.append(r)
            print(f"\n== {t} ({n} pages)")
            for _, i, o, g in kept[:a.top]:
                print(f"   {i:4.0%} here, {o:4.0%} max elsewhere   {g}")


if __name__ == "__main__":
    main()
