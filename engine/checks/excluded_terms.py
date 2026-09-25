"""Excluded-terms check (plan.md C11/C12; CLAUDE.md rule 3).

The stakeholder-name list is private material that stays out of this
repository. This module never prints its contents: `check` reports only
locations (file:line, term redacted), and `check_candidates` reports only
a yes/no per name the caller already knows.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "dist",
    ".output",
    ".nitro",
    ".tanstack",
    "__pycache__",
    # Local-only area: holds the name list itself and pre-strip captures.
    "workflow",
}
# Binary / generated files a text sweep should not open.
DEFAULT_SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".ico", ".lock"}


def _load_terms(names_path: Path) -> list[str]:
    terms = []
    for line in names_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    return terms


def _iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in DEFAULT_SKIP_SUFFIXES:
            continue
        yield path


@dataclass
class Hit:
    file: Path
    line_no: int
    term_len: int


def check(names_path: Path, root: Path) -> list[Hit]:
    """Sweep `root` for any term in `names_path`. Never prints the terms."""
    terms = _load_terms(names_path)
    patterns = [re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE) for t in terms]
    hits: list[Hit] = []
    for file in _iter_text_files(root):
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if pattern.search(line):
                    hits.append(Hit(file=file, line_no=line_no, term_len=len(pattern.pattern)))
    return hits


def check_candidates(names_path: Path, candidates: list[str]) -> dict[str, bool]:
    """Return {candidate: is_excluded} for a short list of proposed names."""
    terms = {t.lower() for t in _load_terms(names_path)}
    result = {}
    for candidate in candidates:
        parts = {p.lower() for p in re.split(r"\s+", candidate.strip()) if p}
        result[candidate] = bool(parts & terms)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check excluded-terms")
    parser.add_argument("--names", required=True, type=Path, help="path to the private term list")
    parser.add_argument("--root", type=Path, help="sweep this directory tree for hits")
    parser.add_argument(
        "--check",
        nargs="+",
        metavar="NAME",
        help="instead of sweeping, just say yes/no for each of these candidate names",
    )
    args = parser.parse_args(argv)

    if args.check:
        results = check_candidates(args.names, args.check)
        ok = True
        for name, excluded in results.items():
            print(f"{'EXCLUDED' if excluded else 'ok'}: {name}")
            ok = ok and not excluded
        return 0 if ok else 1

    if not args.root:
        parser.error("--root is required unless --check is given")

    hits = check(args.names, args.root)
    if not hits:
        print(f"excluded-terms: 0 hits under {args.root}")
        return 0

    print(f"excluded-terms: {len(hits)} hit(s) under {args.root}")
    for hit in hits:
        print(f"  {hit.file}:{hit.line_no} — [REDACTED, {hit.term_len} chars]")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
