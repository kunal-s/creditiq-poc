"""Pages drawn at the positions measured on a real document of the same kind.

Positions are in points from the page's top-left corner, as pdfplumber reports them, so a builder can be written
straight from a measurement of the template: `top` is the top of a word's box, and the baseline is placed `ASC` x size
below it (ASC is what the template's own font reports). Fills, line widths and colours are the template's.

Fonts: Roboto (Apache-2.0, scripts/fonts/roboto) for the GST portal's printouts; DejaVu Sans for the income tax
portal's; Liberation Sans and Serif (metric twins of Arial and Times New Roman) for Office-made documents; the PDF
base fonts (Helvetica, Times) where the template uses them.

Every page carries the one-line footer of CLAUDE.md rule 8 and nothing else of that kind: no watermark, emblem, seal,
logo or QR code is drawn, even where the template has one.
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from tests import docsets as D

FONT_DIR = Path(__file__).resolve().parent / "fonts"
SYSTEM = Path("/usr/share/fonts/truetype")
_TTF = {
    "Roboto-Regular": FONT_DIR / "roboto/Roboto-Regular.ttf",
    "Roboto-Medium": FONT_DIR / "roboto/Roboto-Medium.ttf",
    "Roboto-Italic": FONT_DIR / "roboto/Roboto-Italic.ttf",
    "Roboto-Bold": FONT_DIR / "roboto/Roboto-Bold.ttf",
    "DejaVuSans": SYSTEM / "dejavu/DejaVuSans.ttf",
    "DejaVuSans-Bold": SYSTEM / "dejavu/DejaVuSans-Bold.ttf",
    "Arial": SYSTEM / "liberation/LiberationSans-Regular.ttf",
    "Arial-Bold": SYSTEM / "liberation/LiberationSans-Bold.ttf",
    "Arial-Italic": SYSTEM / "liberation/LiberationSans-Italic.ttf",
    "TimesNewRoman": SYSTEM / "liberation/LiberationSerif-Regular.ttf",
    "TimesNewRoman-Bold": SYSTEM / "liberation/LiberationSerif-Bold.ttf",
}
for _name, _path in _TTF.items():
    if _name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_name, str(_path)))

SCRIPT_FONTS = {
    "NotoSansDevanagari-Regular": SYSTEM / "noto/NotoSansDevanagari-Regular.ttf",
    "NotoSansDevanagari-Bold": SYSTEM / "noto/NotoSansDevanagari-Bold.ttf",
    "NotoSerifDevanagari-Regular": SYSTEM / "noto/NotoSerifDevanagari-Regular.ttf",
    "NotoSerifDevanagari-Bold": SYSTEM / "noto/NotoSerifDevanagari-Bold.ttf",
}

# baseline below a word's top, per point of size, as each template's font reports it (measured)
ASC = {"Roboto": 0.756, "DejaVuSans": 0.760, "Arial": 0.728, "TimesNewRoman": 0.693, "Helvetica": 0.718, "Times": 0.683}

BLACK = (0, 0, 0)


def rgb(hexcolour: str) -> tuple[float, float, float]:
    h = hexcolour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def width(s: str, font: str, size: float) -> float:
    return stringWidth(s, font, size)


def _asc(font: str) -> float:
    for k, v in ASC.items():
        if font.startswith(k):
            return v
    return 0.75


class Sheet:
    """Pages of drawing operations in top-left coordinates; render() adds the footer line to each page."""

    def __init__(self, w: float = 595.3, h: float = 841.9, *, footer_x: float = 20.0, footer_y: float = 14.0):
        self.w, self.h, self.footer_x, self.footer_y = w, h, footer_x, footer_y
        self.pages: list[list] = []
        self.page()

    def page(self):
        self.ops: list = []
        self.pages.append(self.ops)
        return self

    # --- primitives (template coordinates)
    def fill(self, x0, top, x1, bottom, colour: str):
        self.ops.append(("f", x0, top, x1, bottom, rgb(colour)))

    def line(self, x0, top, x1, bottom, lw: float = 1.0, colour: str = "#000000"):
        self.ops.append(("l", x0, top, x1, bottom, lw, rgb(colour)))

    def gradient(self, x0, top, x1, bottom, colours: list[str], *, vertical: bool = False, radius: float = 0.0):
        """A rectangle (rounded when radius > 0) filled with a linear gradient, left to right or top to bottom."""
        self.ops.append(("g", x0, top, x1, bottom, [rgb(c) for c in colours], vertical, radius))

    def dashed(self, x0, top, x1, bottom, lw: float = 0.6, dash=(3, 2), colour: str = "#000000"):
        self.ops.append(("d", x0, top, x1, bottom, lw, dash, rgb(colour)))

    def rotated(self, x, top, s: str, font: str, size: float, angle: float, colour: str = "#000000"):
        """Text turned by angle degrees (90 reads bottom to top) about its start point."""
        self.ops.append(("rt", x, top, s, font, size, angle, rgb(colour)))

    def script(self, x, top, s: str, size: float, *, font: str = "NotoSansDevanagari-Regular", colour: str = "#000000",
               align: str = "l", fit_w: float | None = None, fit_h: float | None = None):
        """Text in a script that needs shaping (Devanagari), set by Pillow and placed as an image: `top` is the top of
        its ink, x its left edge (or right edge / centre). fit_w stretches it to a measured width."""
        from PIL import Image, ImageDraw, ImageFont
        scale = 8
        f = ImageFont.truetype(str(SCRIPT_FONTS[font]), int(size * scale), layout_engine=ImageFont.Layout.RAQM)
        l, t, r, b = f.getbbox(s)
        img = Image.new("RGBA", (r - l + 4, b - t + 4), (255, 255, 255, 0))
        ImageDraw.Draw(img).text((2 - l, 2 - t), s, font=f, fill=tuple(int(v * 255) for v in rgb(colour)) + (255,))
        w, h = img.width / scale, img.height / scale
        if fit_h:                        # the ink's height as measured; the 2-pixel margin scales with it
            ratio = fit_h / ((img.height - 4) / scale)
            w, h = w * ratio, h * ratio
        if fit_w:
            w = fit_w * (img.width / (img.width - 4))
        x = x - w if align == "r" else x - w / 2 if align == "c" else x
        self.ops.append(("i", x, top - 2 / scale, w, h, img))

    def box(self, x0, top, x1, bottom, lw: float = 1.0):
        for a in ((x0, top, x1, top), (x0, bottom, x1, bottom), (x0, top, x0, bottom), (x1, top, x1, bottom)):
            self.line(*a, lw=lw)

    def text(self, x, top, s: str, font: str = "Roboto-Regular", size: float = 9, *, align: str = "l",
             colour: str = "#000000", fit_w: float | None = None):
        """x is the left edge (align l), the right edge (r) or the centre (c). fit_w stretches or narrows the text
        horizontally to a measured width (a condensed face set in a common one)."""
        if s == "":
            return
        hs = fit_w / width(str(s), font, size) if fit_w else 1.0
        self.ops.append(("t", x, top + _asc(font) * size, str(s), font, size, align, rgb(colour), hs))

    def para(self, x, top, w, text: str, font: str = "TimesNewRoman", size: float = 12, *, lead: float = 13.5,
             justify: bool = False, colour: str = "#000000", runs: dict | None = None) -> float:
        """A wrapped paragraph from `top`, `w` wide; justified lines (all but the last) when asked. `runs` maps a
        word to another font (a bold value inside a sentence). Returns the top of the next line."""
        words = text.split(" ")
        lines, cur = [], []
        for wd in words:
            trial = cur + [wd]
            if cur and self._words_w(trial, font, size, runs) > w:
                lines.append(cur)
                cur = [wd]
            else:
                cur = trial
        lines.append(cur)
        for k, ln in enumerate(lines):
            gap = width(" ", font, size)
            if justify and k < len(lines) - 1 and len(ln) > 1:
                gap += (w - self._words_w(ln, font, size, runs)) / (len(ln) - 1)
            xx = x
            for wd in ln:
                f = (runs or {}).get(wd, font)
                self.text(xx, top, wd, f, size, colour=colour)
                xx += width(wd, f, size) + gap
            top += lead
        return top

    @staticmethod
    def _words_w(ws, font, size, runs) -> float:
        return sum(width(wd, (runs or {}).get(wd, font), size) for wd in ws) + width(" ", font, size) * (len(ws) - 1)

    # --- a grid table: column edges, rows of cells; returns the bottom of the table
    def grid(self, edges: list[float], top: float, rows: list[dict], *, font="Roboto-Regular", bold="Roboto-Medium",
             size=9.0, line_h=10.5, pad_top=4.1, pad_x=4.5, row_h=15.55, lw=1.0, head_fill="#F2F2F2",
             line_x0: float | None = None) -> float:
        """Each row: {cells: [...], head: bool, bold: bool, align: [...], fill: colour or None, span: [(i, j)]}.
        A cell may hold several lines ("\\n"). Numbers wrap by character when they are wider than the cell, as the
        portal's printouts do. '-' is centred. Returns the bottom of the last row."""
        y = top
        x_first = edges[0] if line_x0 is None else line_x0
        for row in rows:
            cells = list(row["cells"])
            head = row.get("head", False)
            f = bold if head or row.get("bold") else font
            spans = row.get("span") or []
            cols = []
            i = 0
            while i < len(cells):
                j = next((b for a, b in spans if a == i), i)
                cols.append((i, edges[i], edges[j + 1], cells[i]))
                i = j + 1
            texts = []
            for i, x0, x1, val in cols:
                al = (row.get("align") or ["l"] + ["r"] * (len(edges) - 2))[i] if not head else "l"
                cf = f if head or i == 0 else font      # a bold row has its label bold, not its amounts
                lines = []
                for part in str(val).split("\n"):
                    lines += self._wrap(part, cf, size, x1 - x0 - 2 * pad_x, by_char=al == "r")
                texts.append((x0, x1, al, cf, lines))
            n = max(1, max(len(t[4]) for t in texts))
            h = row.get("height") or row_h + (n - 1) * line_h
            fill = row.get("fill", head_fill if head else None)
            if fill:
                for _, x0, x1, _ in cols:
                    self.fill(x0, y, x1, y + h, fill)
            for x0, x1, al, cf, lines in texts:
                for k, s in enumerate(lines):
                    t = y + pad_top + k * line_h
                    if s == "-":
                        self.text((x0 + x1) / 2, t, s, cf, size, align="c")
                    elif al == "r":
                        self.text(x1 - pad_x, t, s, cf, size, align="r")
                    else:
                        self.text(x0 + pad_x, t, s, cf, size)
            # grid: top and bottom of the row, and every cell edge
            self.line(x_first - 0.5, y, edges[-1], y, lw)
            self.line(x_first - 0.5, y + h, edges[-1], y + h, lw)
            for _, x0, x1, _ in cols:
                self.line(x0, y - 0.5, x0, y + h + 0.5, lw)
            self.line(edges[-1], y - 0.5, edges[-1], y + h + 0.5, lw)
            y += h
        return y

    @staticmethod
    def _wrap(s: str, font: str, size: float, room: float, *, by_char: bool) -> list[str]:
        if not s or width(s, font, size) <= room:
            return [s]
        if by_char:
            out, cur = [], ""
            for ch in s:
                if cur and width(cur + ch, font, size) > room:
                    out.append(cur)
                    cur = ch
                else:
                    cur += ch
            return out + [cur]
        out, cur = [], ""
        for word in s.split(" "):
            trial = f"{cur} {word}" if cur else word
            if cur and width(trial, font, size) > room:
                out.append(cur + " ")
                cur = word
            else:
                cur = trial
        return out + [cur]

    def render(self) -> bytes:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(self.w, self.h), invariant=1)
        c.setTitle("")
        for ops in self.pages:
            for op in ops:
                kind = op[0]
                if kind == "f":
                    _, x0, t, x1, b, colour = op
                    c.setFillColorRGB(*colour)
                    c.rect(x0, self.h - b, x1 - x0, b - t, stroke=0, fill=1)
                elif kind == "l":
                    _, x0, t, x1, b, lw, colour = op
                    c.setStrokeColorRGB(*colour)
                    c.setLineWidth(lw)
                    c.line(x0, self.h - t, x1, self.h - b)
                elif kind == "t":
                    _, x, base, s, font, size, al, colour, hs = op
                    c.setFillColorRGB(*colour)
                    c.setFont(font, size)
                    y = self.h - base
                    if hs != 1.0:
                        w = width(s, font, size) * hs
                        x = x - w if al == "r" else x - w / 2 if al == "c" else x
                        c.saveState()
                        c.translate(x, y)
                        c.scale(hs, 1)
                        c.drawString(0, 0, s)
                        c.restoreState()
                    else:
                        (c.drawRightString if al == "r" else c.drawCentredString if al == "c" else c.drawString)(x, y, s)
                elif kind == "g":
                    _, x0, t, x1, b, cols, vertical, radius = op
                    c.saveState()
                    path = c.beginPath()
                    if radius:
                        path.roundRect(x0, self.h - b, x1 - x0, b - t, radius)
                    else:
                        path.rect(x0, self.h - b, x1 - x0, b - t)
                    c.clipPath(path, stroke=0, fill=0)
                    if vertical:
                        c.linearGradient(x0, self.h - t, x0, self.h - b, cols, extend=True)
                    else:
                        c.linearGradient(x0, self.h - b, x1, self.h - b, cols, extend=True)
                    c.restoreState()
                elif kind == "d":
                    _, x0, t, x1, b, lw, dash, colour = op
                    c.saveState()
                    c.setStrokeColorRGB(*colour)
                    c.setLineWidth(lw)
                    c.setDash(*dash)
                    c.line(x0, self.h - t, x1, self.h - b)
                    c.restoreState()
                elif kind == "rt":
                    _, x, t, s, font, size, angle, colour = op
                    c.saveState()
                    c.setFillColorRGB(*colour)
                    c.setFont(font, size)
                    c.translate(x, self.h - t)
                    c.rotate(angle)
                    c.drawString(0, 0, s)
                    c.restoreState()
                elif kind == "i":
                    from reportlab.lib.utils import ImageReader
                    _, x, t, w, h, img = op
                    c.drawImage(ImageReader(img), x, self.h - t - h, w, h, mask="auto")
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 6.5)
            c.drawString(self.footer_x, self.footer_y, D.FOOTER)
            c.showPage()
        c.save()
        return buf.getvalue()


def plain(n: float) -> str:
    """An amount as the GST portal prints it: no grouping, two decimals (9725329.36)."""
    return f"{n:.2f}"
