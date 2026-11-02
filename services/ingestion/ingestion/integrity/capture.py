"""How a picture of a page was made, and pages made differently (F-07A, use case 2).

A scan of paper carries the paper: a background that is never perfectly even,
a little skew, a sheet's proportions. A page a computer drew and delivered as a
picture — a screenshot, a re-rendered copy — has a background that is perfectly
even and text that is perfectly level; a screenshot is, besides, cropped to a
screen rather than a sheet. Pages issued together are made alike; one made
differently may have come from another document.

Both are evidence about how a page was made, never about who made it.

Ported from RBL/fault_detection `raster.capture_of`, `_dilate`, `_skew_ratio` and
`origin.mixed_origins` (PROVENANCE.md). The thresholds are fault_detection's
first measurements (one screenshot and three renders against eleven scanned
pages), kept as constants beside the code that measures them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Capture", "capture_of", "mixed_origins", "describe", "made_as", "MADE_AS"]

#: Paper sizes, as height / width.
_PAPER = {"A4": 297 / 210, "Letter": 11 / 8.5, "Legal": 14 / 8.5, "A5": 210 / 148}
PAPER_TOLERANCE = 0.04
FLAT_STD_MAX = 0.10            # p90 of the spread of flat 16 px blocks (scans: 0.16 and up)
FLAT_PURE_MIN = 0.90           # share of flat blocks entirely the paper's colour
OFF_PAPER_MAX = 0.015          # share of background away from ink not the paper's colour
SKEW_RATIO_MAX = 1.05          # best skewed projection over the level one
RENDER_OFF_PAPER_MAX = 0.006
RENDER_FLAT_PURE_MIN = 0.95
DIGITAL = ("screen_crop", "digital_render", "possibly_digital")


@dataclass(slots=True)
class Capture:
    """How one picture page appears to have been made."""

    page: int
    """1-based."""
    kind: str
    """screen_crop | digital_render | possibly_digital | scan_or_photo | unknown"""
    features: dict[str, Any] = field(default_factory=dict)


def _dilate(mask, radius: int):
    import numpy as np  # noqa: PLC0415

    out = mask.copy()
    for axis in (0, 1):
        grown = out.copy()
        for step in range(1, radius + 1):
            grown |= np.roll(out, step, axis=axis)
            grown |= np.roll(out, -step, axis=axis)
        out = grown
    return out


def _skew_ratio(ink) -> float:
    """How much sharper rows of ink line up when the page is turned a little than
    when taken as it is: 1.0 means level."""
    import numpy as np  # noqa: PLC0415

    ys, xs = np.nonzero(ink)
    if len(ys) < 500:
        return 1.0
    if len(ys) > 200_000:
        pick = np.linspace(0, len(ys) - 1, 200_000).astype(np.int64)
        ys, xs = ys[pick], xs[pick]
    xs = xs - xs.mean()

    def score(angle_deg: float) -> float:
        t = np.tan(np.radians(angle_deg))
        rows = np.round(ys - xs * t).astype(np.int64)
        rows -= rows.min()
        counts = np.bincount(rows)
        return float((counts.astype(np.float64) ** 2).sum())

    level = score(0.0)
    best = max(score(a / 10.0) for a in range(-30, 31) if a)
    return max(best, level) / max(level, 1.0)


def capture_of(page: int, image, coverage: float, *, dpi: float | None = None) -> Capture:
    """Classify a page picture. `image` is PIL; `coverage` the share of the page it covers."""
    import numpy as np  # noqa: PLC0415

    grey = np.asarray(image.convert("L"), dtype=np.int16)
    h, w = grey.shape
    if h < 64 or w < 64:
        return Capture(page, "unknown", {"reason": "too small to judge"})
    hist = np.bincount(grey.ravel(), minlength=256)
    paper = int(np.argmax(hist[160:]) + 160)
    features: dict[str, Any] = {"paper_level": paper}
    if dpi:
        features["dpi"] = round(dpi)

    bh, bw = h // 16, w // 16
    blocks = grey[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16).swapaxes(1, 2).reshape(bh * bw, 256)
    ranges = blocks.max(axis=1) - blocks.min(axis=1)
    means = blocks.mean(axis=1)
    flat = (ranges < 40) & (means > paper - 30)
    if flat.sum() < 20:
        return Capture(page, "unknown", {**features, "reason": "too little blank paper to judge"})
    stds = blocks[flat].std(axis=1)
    features["flat_std_p90"] = round(float(np.percentile(stds, 90)), 3)
    features["flat_pure_share"] = round(float(((ranges[flat] == 0) & (blocks[flat][:, 0] == paper)).mean()), 4)

    ink = grey < 230
    background = ~_dilate(ink, 5)
    features["off_paper_share"] = (round(float((grey[background] != paper).mean()), 4)
                                   if background.sum() > 0 else 1.0)
    features["skew_ratio"] = round(_skew_ratio(ink), 3)

    aspect = h / w
    aspect = max(aspect, 1 / aspect) if aspect > 0 else aspect
    features["aspect"] = round(aspect, 4)
    features["nearest_paper"], off = min(((name, abs(aspect / ratio - 1)) for name, ratio in _PAPER.items()),
                                         key=lambda t: t[1])
    features["off_paper_size"] = round(off, 4)
    features["coverage"] = round(coverage, 4)

    digital = (features["flat_std_p90"] <= FLAT_STD_MAX and features["flat_pure_share"] >= FLAT_PURE_MIN
               and features["off_paper_share"] <= OFF_PAPER_MAX and features["skew_ratio"] <= SKEW_RATIO_MAX)
    if not digital:
        return Capture(page, "scan_or_photo", features)
    if off > PAPER_TOLERANCE or coverage < 0.93:
        return Capture(page, "screen_crop", features)
    if features["off_paper_share"] <= RENDER_OFF_PAPER_MAX and features["flat_pure_share"] >= RENDER_FLAT_PURE_MIN:
        return Capture(page, "digital_render", features)
    return Capture(page, "possibly_digital", features)


_WORDS = {
    "screen_crop": "a picture of a computer-drawn page cut to a screen's shape (a screenshot)",
    "digital_render": "a computer-drawn page flattened into a picture",
    "possibly_digital": "a picture that looks computer-drawn and is shaped like a sheet of paper",
    "scan_or_photo": "a scan or a photograph of a page",
    "unknown": "a picture whose making could not be measured",
}


def describe(c: Capture) -> str:
    """One page's capture in plain words, with what was measured."""
    f = c.features
    said = [f"page {c.page} is {_WORDS.get(c.kind, c.kind)}"]
    if c.kind in DIGITAL:
        said.append("its background is perfectly even (no paper texture)")
        if f.get("skew_ratio") is not None and f["skew_ratio"] <= SKEW_RATIO_MAX:
            said.append("its text is perfectly level")
    if c.kind == "screen_crop" and f.get("off_paper_size", 0) > PAPER_TOLERANCE:
        said.append(f"its shape matches no paper size (the nearest, {f.get('nearest_paper')}, is "
                    f"{f.get('off_paper_size', 0):.0%} off)")
    if c.kind == "unknown" and f.get("reason"):
        said.append(f["reason"])
    return ", ".join(said)


MADE_AS = ("digital", "mixed", "scanned", "design_tool", "computer_drawn", "screenshot")


def made_as(kinds: dict[int, str], captures: list[str], editor: str | None) -> str | None:
    """How the file was made, in one word for a reader (`MADE_AS`).

    Pages with their own text and none that are pictures: digital. Both kinds:
    mixed. Pictures only: written by a design or editing tool, a screenshot, a
    computer-drawn page flattened into a picture, or else a scan or a photo.
    None when nothing was read."""
    if not kinds and not captures:
        return None
    text = sum(1 for k in kinds.values() if k == "text")
    pictures = len(kinds) - text if kinds else len(captures)
    if text and not pictures:
        return "digital"
    if text and pictures:
        return "mixed"
    if editor:
        return "design_tool"
    if "screen_crop" in captures:
        return "screenshot"
    if any(c in DIGITAL for c in captures):
        return "computer_drawn"
    return "scanned"


def mixed_origins(kinds: dict[int, str], captures: list[Capture], *, dpi_differ: float,
                  dpi_agree: float) -> list[tuple[int, str]]:
    """Pages made differently from the document's others: (page, why).

    `kinds` is each page's kind ("text" or "picture"). Three ways, none about
    what a page says: a picture page among pages of text (or the reverse); a
    computer-drawn picture among scans (or the reverse); and, with three or more
    picture pages, one whose resolution differs where the others agree.
    """
    if len(kinds) < 2:
        return []
    out: list[tuple[int, str]] = []
    text = [i for i, k in kinds.items() if k == "text"]
    pictures = [i for i, k in kinds.items() if k == "picture"]
    if text and pictures:
        minority = pictures if len(pictures) <= len(text) else text
        why = ("a picture of a page among pages of original text" if minority is pictures
               else "a page of original text among pictures of pages")
        out += [(i, why) for i in sorted(minority)]
    digital = [c.page for c in captures if c.kind in DIGITAL]
    scans = [c.page for c in captures if c.kind == "scan_or_photo"]
    if digital and scans:
        minority = digital if len(digital) <= len(scans) else scans
        why = ("a picture of a computer-drawn page among scans" if minority is digital
               else "a scan among pictures of computer-drawn pages")
        out += [(i, why) for i in sorted(minority) if all(i != j for j, _ in out)]
    resolutions = {c.page: c.features["dpi"] for c in captures if c.features.get("dpi")}
    if len(resolutions) >= 3:
        for i, r in resolutions.items():
            others = [v for j, v in resolutions.items() if j != i]
            mid = sorted(others)[len(others) // 2]
            if (abs(r / mid - 1) > dpi_differ and all(abs(v / mid - 1) <= dpi_agree for v in others)
                    and all(i != j for j, _ in out)):
                out.append((i, f"its picture's resolution ({r} dpi) differs from the other pages' ({mid} dpi)"))
    return sorted(out)
