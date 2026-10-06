"""Image measures behind the quality grade (FRD F-07.2): blur, skew, shadow, blankness.
Numpy only; thresholds come from quality.yaml."""

from __future__ import annotations

import numpy as np
from PIL import Image


def _gray(img: Image.Image, max_side: int = 1000) -> np.ndarray:
    g = img.convert("L")
    s = max(g.size) / max_side
    if s > 1:
        g = g.resize((int(g.width / s), int(g.height / s)), Image.BILINEAR)
    return np.asarray(g, dtype=np.float32)


def sharpness(img: Image.Image) -> float:
    a = _gray(img)
    lap = a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return float(lap.var())


def ink_ratio(img: Image.Image) -> float:
    a = _gray(img)
    return float((a < 128).mean())


def shadow_spread(img: Image.Image, grid: int = 8) -> float:
    """Spread of background brightness across the page: even light gives a small number."""
    a = _gray(img)
    h, w = a.shape
    means = []
    for i in range(grid):
        for j in range(grid):
            blk = a[i * h // grid:(i + 1) * h // grid, j * w // grid:(j + 1) * w // grid]
            if blk.size:
                means.append(float(np.percentile(blk, 90)))  # paper brightness, ignoring ink
    return float(np.std(means))


def skew_degrees(img: Image.Image, limit: float = 5.0, step: float = 0.25) -> float:
    g = img.convert("L")
    s = max(g.size) / 600
    if s > 1:
        g = g.resize((int(g.width / s), int(g.height / s)), Image.BILINEAR)
    best, best_angle = -1.0, 0.0
    a = 0.0
    angles = []
    while a <= limit + 1e-9:
        angles += [a, -a] if a else [0.0]
        a += step
    for ang in angles:
        r = np.asarray(g.rotate(ang, resample=Image.BILINEAR, fillcolor=255), dtype=np.float32) < 128
        v = float(r.sum(axis=1).var())
        if v > best:
            best, best_angle = v, ang
    return abs(best_angle)
