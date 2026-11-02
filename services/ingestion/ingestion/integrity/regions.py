"""Regions of a scan with another grain or sharpness than their page (F-07A, use case 2).

A scan or photo has one grain and one sharpness across its print: the same
sensor, the same lens, the same compression. Text pasted in from another
picture — cut from another scan, typed and rendered, or patched in an image
editor — brings its own: cleaner paper behind it, crisper or softer edges.
The page is cut into tiles; for each tile holding text, its paper grain (what
is left after a light blur) and its sharpness (edge strength against its
contrast) are compared with the page's median in robust deviations.
Adjoining tiles beyond the thresholds are a region to look at.

Measured on the bank's genuine picture pages: most are pictures made from a
digital page, with no grain at all, so a page is compared only when its paper
has a grain (`min_page_grain`), and a region is flagged only in the direction a
paste goes: cleaner than its page, or cleaner by half that and sharper. A page
with more than `max_regions_per_page` such regions varies by nature.

Ported unchanged from RBL/fault_detection `regions.py` (PROVENANCE.md).
"""

from __future__ import annotations

from typing import Any

__all__ = ["odd_regions", "page_has_grain"]


def _box_blur(a, k: int = 3):
    import numpy as np  # noqa: PLC0415

    pad = k // 2
    p = np.pad(a, pad, mode="edge")
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def page_has_grain(grey, params: dict[str, Any]) -> bool:
    """Whether the page's paper carries a grain to compare (a scan or a photo, not a
    picture made from a digital page)."""
    import numpy as np  # noqa: PLC0415

    paper = float(np.percentile(grey, 90))
    resid = (grey - _box_blur(grey))[grey >= paper - 30]
    return resid.size > 0 and float(resid.std()) >= float(params["min_page_grain"])


def odd_regions(grey, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Regions of a page image (2-D float array) whose grain or sharpness stands apart:
    [{rect: [l, t, r, b] fractions of the image, tiles, grain_z, sharp_z}]."""
    import numpy as np  # noqa: PLC0415

    tile = int(params["tile_px"])
    min_ink = float(params["min_ink_share"])
    nz, sz = float(params["noise_z"]), float(params["sharpness_z"])
    min_tiles = int(params["min_tiles"])
    min_grain = float(params["min_page_grain"])
    h, w = grey.shape
    paper = float(np.percentile(grey, 90))
    ink = grey < paper - 60
    resid = grey - _box_blur(grey)
    gy, gx = np.gradient(grey)
    grad = np.hypot(gx, gy)
    rows, cols = h // tile, w // tile
    grain = np.full((rows, cols), np.nan)
    sharp = np.full((rows, cols), np.nan)
    for r in range(rows):
        for c in range(cols):
            sl = (slice(r * tile, (r + 1) * tile), slice(c * tile, (c + 1) * tile))
            t_ink = ink[sl]
            share = float(t_ink.mean())
            if share < min_ink or share > 0.6:
                continue                            # no text here, or a solid block
            bg = ~t_ink
            if bg.mean() < 0.3:
                continue
            grain[r, c] = float(resid[sl][bg].std())
            contrast = float(np.percentile(grey[sl], 95) - np.percentile(grey[sl], 5)) or 1.0
            edges = grad[sl] > 0.25 * contrast
            if edges.any():
                sharp[r, c] = float(grad[sl][edges].mean() / contrast)

    def robust_z(a, floor):
        v = a[~np.isnan(a)]
        if v.size < 12:
            return np.zeros_like(a)
        med = np.median(v)
        mad = max(np.median(np.abs(v - med)) * 1.4826, floor)
        return np.nan_to_num((a - med) / mad)

    measured = grain[~np.isnan(grain)]
    if measured.size < 12 or float(np.median(measured)) < min_grain:
        return []                                   # no grain on this page to compare
    zg, zs = robust_z(grain, 0.25), robust_z(sharp, 0.01)
    flagged = (zg <= -nz) | ((zg <= -nz / 2) & (zs >= sz))
    seen = np.zeros_like(flagged)
    out = []
    for r in range(rows):
        for c in range(cols):
            if not flagged[r, c] or seen[r, c]:
                continue
            stack, comp = [(r, c)], []
            seen[r, c] = True
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < rows and 0 <= xx < cols and flagged[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
            if len(comp) < min_tiles:
                continue
            ys, xs = [p[0] for p in comp], [p[1] for p in comp]
            out.append({"rect": [round(min(xs) * tile / w, 4), round(min(ys) * tile / h, 4),
                                 round((max(xs) + 1) * tile / w, 4), round((max(ys) + 1) * tile / h, 4)],
                        "tiles": len(comp),
                        "grain_z": round(float(max((zg[p] for p in comp), key=abs)), 1),
                        "sharp_z": round(float(max((zs[p] for p in comp), key=abs)), 1)})
    return out
