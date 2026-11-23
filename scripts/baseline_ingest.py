#!/usr/bin/env python3
"""Run the document-processing pipeline over a marked-up document set and score it against the answer key.

    services/ingestion/.venv/bin/python scripts/baseline_ingest.py [--key workflow/baseline/expected.yaml] [--label NAME]

Runs in-process with no model and no OCR, so a run is deterministic and needs no keys. Writes
workflow/baseline/<label>/results.json (every file's outcome) and summary.md (the scores), so every epic of the
classification and extraction restructure can be compared with the one before. The answer key lists, per file,
the documents in it by page range; a type ending in * is a type not yet published (scored as "should be
unclassified" until it exists).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ingestion"))

from ingestion.config.loader import load_dir  # noqa: E402
from ingestion.contracts import FileSpec  # noqa: E402
from ingestion.pipeline import Ingestor  # noqa: E402
from ingestion.store import Store  # noqa: E402
from ingestion.util import sha256_hex  # noqa: E402


def expected_pages(entry: list[dict], published: set[str]) -> dict[int, str | None]:
    out: dict[int, str | None] = {}
    for d in entry:
        t = d["type"]
        if t and t.endswith("*"):
            t = t[:-1] if t[:-1] in published else None
        for p in range(d["pages"][0], d["pages"][1] + 1):
            out[p] = t
    return out


def predicted_pages(res, n_pages: int) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {p: set() for p in range(1, n_pages + 1)}
    for d in res.documents:
        for p in (d.pages or range(d.page_from, d.page_to + 1)):
            out.setdefault(p, set()).add(d.document_type)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=str(ROOT / "workflow" / "baseline" / "expected.yaml"))
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--config", default=str(ROOT / "config" / "ingestion"))
    a = ap.parse_args()

    cfg = load_dir(a.config, version=a.label)
    published = set(cfg.fields.types)
    key = yaml.safe_load(Path(a.key).read_text())
    ing = Ingestor(cfg, Store(), None, None)

    files, page_hits, per_type = [], Counter(), defaultdict(Counter)
    confusion: Counter = Counter()
    fields, tables = defaultdict(Counter), defaultdict(Counter)
    for i, (rel, entry) in enumerate(key.items()):
        data = (ROOT / rel).read_bytes()
        spec = FileSpec(file_id=f"f{i}", sha256=sha256_hex(data), original_name=Path(rel).name, content_type="application/pdf")
        res = ing.process_file("BASELINE", spec, data)
        exp = expected_pages(entry, published)
        pred = predicted_pages(res, max(exp))
        for p, t in exp.items():
            got = pred.get(p, set())
            ok = (got == {t}) if t else not got
            page_hits["correct" if ok else "wrong"] += 1
            per_type[t or "(none)"]["correct" if ok else "wrong"] += 1
            if not ok:
                confusion[(t or "(none)", "+".join(sorted(got)) or "(none)")] += 1
        exp_docs = [d for d in entry if d["type"] and not (d["type"].endswith("*") and d["type"][:-1] not in published)]
        for d in res.documents:
            for name, f in d.fields.items():
                fields[d.document_type][f.status] += 1
            for name, t in d.tables.items():
                tables[d.document_type][t.status] += 1
        files.append({
            "file": rel, "status": res.status, "error": res.error,
            "file_type": res.classification.type if res.classification else None,
            "tier": res.classification.tier if res.classification else None,
            "candidates": [c.model_dump() for c in res.classification.candidates] if res.classification else [],
            "expected_documents": len(exp_docs), "documents": len(res.documents),
            "found": [{"type": d.document_type, "pages": d.pages or list(range(d.page_from, d.page_to + 1)),
                       "key": d.instance_key, "origin": d.origin,
                       "fields": {k: (f.value if f.status == "found" else None) for k, f in d.fields.items()},
                       "tables": {k: (len(t.rows) if t.status == "found" else t.reason) for k, t in d.tables.items()}}
                      for d in res.documents],
        })

    out = ROOT / "workflow" / "baseline" / a.label
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(files, indent=1, default=str))

    tot = sum(page_hits.values())
    lines = [f"# Ingestion baseline: {a.label}", "",
             f"Configuration `{a.config}`, no model, no OCR. {len(files)} files, {tot} pages.", "",
             f"**Pages typed correctly: {page_hits['correct']} of {tot} ({100 * page_hits['correct'] / tot:.1f}%)**", "",
             "| Expected type | Pages | Correct |", "|---|---|---|"]
    for t, c in sorted(per_type.items()):
        n = sum(c.values())
        lines.append(f"| {t} | {n} | {c['correct']} ({100 * c['correct'] / n:.0f}%) |")
    lines += ["", "Most common errors (expected → got, pages):", "", "| Expected | Got | Pages |", "|---|---|---|"]
    for (e, g), n in confusion.most_common(15):
        lines.append(f"| {e} | {g} | {n} |")
    docs_ok = sum(f["documents"] == f["expected_documents"] for f in files)
    lines += ["", f"Files with the expected number of documents: {docs_ok} of {len(files)}",
              f"Files not processed: {sum(f['status'] != 'processed' for f in files)}", "",
              "| Type | Fields found | Fields missing | Tables found | Tables missing |", "|---|---|---|---|---|"]
    for t in sorted(set(fields) | set(tables)):
        lines.append(f"| {t} | {fields[t]['found']} | {fields[t]['missing']} | {tables[t]['found']} | {tables[t]['missing']} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
