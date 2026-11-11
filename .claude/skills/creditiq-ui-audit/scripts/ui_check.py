#!/usr/bin/env python3
"""The mechanical part of a CreditIQ UI audit: what a reader of the code can check line by line.

    python3 .claude/skills/creditiq-ui-audit/scripts/ui_check.py [paths…] [--all] [--json]

With no paths it checks the .tsx/.ts files under src/ that git sees as changed (staged, unstaged or
new); --all checks every file under src/. Standard library only. Exit 1 when any error is found.

Each finding has a rule id, a level (error / warn), the file and line, and the reason in a sentence.
The rules are the house style of the `creditiq-ui` skill: tokens instead of raw colours, pale tints
for areas and readable red for words, copy from the terminology, no page jumps, no excluded words.
They are heuristics: a warning is a question to look at, not a verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           check=False).stdout.strip() or ".")

PALETTE = ("slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|"
           "indigo|violet|purple|fuchsia|pink|rose")
UTILITIES = "bg|text|border|ring|fill|stroke|from|to|via|outline|divide|decoration|shadow|accent|caret"

RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    ("raw-palette", "error",
     re.compile(rf"\b(?:{UTILITIES})-(?:{PALETTE})-\d{{2,3}}\b"),
     "Tailwind's default palette: use a token (positive, flag, critical-text, info, muted-foreground …)."),
    ("raw-colour", "error",
     re.compile(r"(?:#[0-9a-fA-F]{3,8}\b(?![0-9a-zA-Z-])|\b(?:rgb|rgba|hsl|hsla|oklch)\()"),
     "A colour value in a component: colours come from the tokens in src/styles.css."),
    ("solid-red-area", "warn",
     re.compile(r"\bbg-(?:destructive|critical)(?![-/\w])"),
     "A solid red fill: fine for a dot, a thin rule or a destructive action button; a chip, banner, bar or card "
     "takes a pale tint (bg-critical-soft/60, bg-destructive/30)."),
    ("strong-red-words", "warn",
     re.compile(r"(?=[^\"'`]*\btext-destructive\b)(?=[^\"'`]*\bfont-(?:semibold|bold)\b)"),
     "Bold dark-red words: use text-critical-text at normal weight, or a critical Chip."),
    ("red-words", "warn",
     re.compile(r"\btext-destructive\b"),
     "text-destructive on words: words take text-critical-text; keep text-destructive for glyphs."),
    ("page-jump", "warn",
     re.compile(r"\.scrollIntoView\("),
     "scrollIntoView scrolls every ancestor: right for a jump the reader asked for (a link to a row), wrong on "
     "first render or for a selection inside a scrolling box — scroll the box there."),
    ("inline-colour-style", "warn",
     re.compile(r"style=\{\{[^}]*\b(?:color|background(?:Color)?|borderColor)\s*:"),
     "A colour in an inline style: use a token class."),
    ("html-injection", "error",
     re.compile(r"dangerouslySetInnerHTML"),
     "Raw HTML: render text as text."),
    ("excluded-word", "error",
     re.compile(r"\b(?:fraud\w*|forg(?:ed|ery|eries)|fake\w*|tamper\w*)\b", re.IGNORECASE),
     "A word that must never be on screen (fraud, forged, fake, tampered): say what was found instead."),
    ("browser-record", "warn",
     re.compile(r"\b(?:localStorage|sessionStorage)\.setItem\("),
     "Browser storage: only for view preferences; a person's change is the engine's record."),
]

BUTTON = re.compile(r"<button\b(?![^>]*\btype=)", re.DOTALL)
IMG = re.compile(r"<img\b(?![^>]*\balt=)", re.DOTALL)
# A JSX text node with words in it: >Some words< (not an expression, not whitespace only).
TEXT_NODE = re.compile(r">\s*([A-Za-z][^<>{}\n]*[A-Za-z.!?…:)])\s*<")
# A prop that is read aloud or shown, given a literal.
LITERAL_PROP = re.compile(r"\b(aria-label|title|placeholder|alt)=\"([^\"]*[A-Za-z][^\"]*)\"")

SKIP_LINE = re.compile(r"^\s*(?://|\*|/\*)")
# A line that styles a glyph, a dot or a thin rule, where a saturated colour is the point.
GLYPH = re.compile(r"\b(?:size-(?:0|1|1\.5|2|2\.5|3|3\.5|4)|[hw]-(?:0\.5|1|1\.5|2|3|3\.5|4)|dot|glyph|icon|Icon|"
                   r"tile|ring-|outline-|border-[ltrb]-|stroke-|fill-)\b")
# Text that is code, not words: comparisons, member access, assignments.
CODE = re.compile(r"&&|\|\||[=;]|\b\w+\.\w+|\w\(")
# Files that cannot use the tokens: the static page served when the app itself fails to load.
EXEMPT = ("src/lib/error-page.ts",)


@dataclass
class Finding:
    rule: str
    level: str
    file: str
    line: int
    text: str
    why: str


def changed_files() -> list[Path]:
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True,
                         text=True, cwd=ROOT, check=False).stdout
    paths = []
    for row in out.splitlines():
        name = row[3:].split(" -> ")[-1].strip().strip('"')
        if row[:2].strip() != "D" and name.startswith("src/") and name.endswith((".tsx", ".ts")):
            paths.append(ROOT / name)
    return paths


def all_files() -> list[Path]:
    return sorted(p for p in (ROOT / "src").rglob("*") if p.suffix in (".ts", ".tsx"))


def skip(path: Path) -> bool:
    name = path.as_posix()
    return (name.endswith(".gen.ts") or "/components/ui/" in name or name.endswith("routeTree.gen.ts")
            or "/api/schema" in name or name.endswith(EXEMPT))


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def check(path: Path) -> list[Finding]:
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() else path.as_posix()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    found: list[Finding] = []
    for n, line in enumerate(lines, start=1):
        if SKIP_LINE.match(line):
            continue
        for rule, level, pattern, why in RULES:
            if rule == "red-words" and any(f.rule == "strong-red-words" and f.line == n for f in found):
                continue
            if rule in ("red-words", "solid-red-area") and GLYPH.search(line):
                continue
            if pattern.search(line):
                found.append(Finding(rule, level, rel, n, line.strip()[:140], why))
    if path.suffix == ".tsx":
        for m in BUTTON.finditer(text):
            found.append(Finding("button-type", "warn", rel, line_of(text, m.start()), "<button …>",
                                 'A button without type="button" submits any form around it.'))
        for m in IMG.finditer(text):
            found.append(Finding("img-alt", "error", rel, line_of(text, m.start()), "<img …>",
                                 "An image without alt: give it one from t(), or alt=\"\" if decorative."))
        for m in TEXT_NODE.finditer(text):
            words = m.group(1).strip()
            if len(words) < 3 or re.fullmatch(r"[A-Z]{1,3}\d*|[•·→←…]+", words) or CODE.search(words):
                continue
            n = line_of(text, m.start(1))
            if SKIP_LINE.match(lines[n - 1]):
                continue
            found.append(Finding("literal-copy", "warn", rel, n, words[:80],
                                 "Words written in the component: put them in terminology/rbl.yaml and read them with t()."))
        for m in LITERAL_PROP.finditer(text):
            found.append(Finding("literal-copy", "warn", rel, line_of(text, m.start()), m.group(0)[:80],
                                 f"A literal {m.group(1)}: read it with t() so the terminology governs it."))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all", action="store_true", help="every .ts/.tsx file under src/")
    ap.add_argument("--json", action="store_true", help="findings as JSON")
    a = ap.parse_args()
    files = [Path(p).resolve() for p in a.paths] if a.paths else (all_files() if a.all else changed_files())
    files = [f for f in files if f.suffix in (".ts", ".tsx") and f.is_file() and not skip(f)]
    findings = [f for path in files for f in check(path)]
    if a.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
    else:
        if not files:
            print("No .ts/.tsx files to check (pass paths, or --all).")
        current = None
        for f in sorted(findings, key=lambda f: (f.file, f.line)):
            if f.file != current:
                current = f.file
                print(f"\n{f.file}")
            print(f"  {f.line:>5}  {f.level:<5} {f.rule:<20} {f.why}\n         {f.text}")
        errors = sum(f.level == "error" for f in findings)
        warns = len(findings) - errors
        print(f"\n{len(files)} file(s) checked: {errors} error(s), {warns} warning(s).")
    return 1 if any(f.level == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
