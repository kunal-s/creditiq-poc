"""F-07A, use case 2: a scan or a photo that was edited.

The scans are built here, as pixels: paper with or without grain, words drawn as
bars of print at known places (an OCR engine's boxes are then exactly where the
print is), a patch of clean paper pasted onto a grainy scan, a value moved off
its label's line, pages made differently. An engine that reads a fixed answer
stands in for OCR, so the checks are tested, not the engine.
"""

from __future__ import annotations

import io
import zlib

import numpy as np
import pytest
from PIL import Image

from ingestion.integrity import capture as cap
from ingestion.integrity.pagedoc import Box
from ingestion.integrity.regions import odd_regions, page_has_grain
from ingestion.integrity.arithmetic import ARITHMETIC_CHECKS
from ingestion.integrity.scanchecks import SCAN_CHECKS, scan_checks
from ingestion.integrity.textlayer import text_layer_versus_scan
from ingestion.pageindex import Page, Word, build_lines
from ingestion.readers.ocr import OcrResult

DPI = 150
PT = 72 / DPI           # points per pixel
W_PX, H_PX = 1240, 1754  # A4 at 150 dpi


PAPER = 245.0


def _form(*, shift_px: int = 0, grain: float = 6.0, seed: int = 7, clean: tuple | None = None):
    """A form of nine label/value rows on near-white paper; row 5's value `shift_px`
    lower; `clean` (y0, y1, x0, x1) a patch whose paper has no grain. The print's
    edges are softened as a printer and a scanner soften them. Returns (image,
    words): the words in points, top-left origin, where the print is."""
    from PIL import ImageFilter

    ink = np.zeros((H_PX, W_PX))
    words = []
    for row in range(9):
        y = 300 + row * 66
        for x0, x1, dy, text in ((100, 380, 0, f"Label number {row}"),
                                 (600, 820 + 10 * row, shift_px if row == 4 else 0, f"1{row},45,000.00")):
            ink[y + dy:y + dy + 18, x0:x1] = 1.0
            words.append(Word(text, x0 * PT, (y + dy) * PT, x1 * PT, (y + dy + 18) * PT, 0.98))
    ink = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)),
                     dtype=np.float64) / 255
    noise = np.random.default_rng(seed).normal(0, grain, ink.shape) if grain else np.zeros(ink.shape)
    if clean:
        y0, y1, x0, x1 = clean
        noise[y0:y1, x0:x1] = 0.0
    a = PAPER + noise - ink * (PAPER - 30.0)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGB")
    return img, words


def _page(no: int, words: list[Word], source: str = "ocr") -> Page:
    lines = build_lines(no, words, y_tol=3.0, column_gap=12.0, boilerplate=[], min_overlap=0.5)
    return Page(no, source, W_PX * PT, H_PX * PT, words, lines)


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(DPI, DPI))
    return buf.getvalue()


def _policy(cfg) -> dict:
    return cfg.integrity.model_dump(mode="python")


def _by_code(found) -> dict:
    return {f.code: f for f in found}


# --- each measure on its own ---------------------------------------------------------

def test_a_patch_of_clean_paper_on_a_grainy_scan_stands_apart(cfg):
    t = _policy(cfg)["scan"]["regions"]
    img, _ = _form(clean=(560, 720, 560, 900))           # the same print, pasted on paper with no grain
    grey = np.asarray(img.convert("L").resize((round(W_PX * 144 / DPI), round(H_PX * 144 / DPI))),
                      dtype=np.float64)
    assert page_has_grain(grey, t)
    found = odd_regions(grey, t)
    assert found, "the clean patch was not found"
    l, top, r, b = found[0]["rect"]
    assert l < 900 / W_PX and r > 560 / W_PX and top < 720 / H_PX and b > 560 / H_PX


def test_a_page_with_no_grain_is_not_compared(cfg):
    img, _ = _form(grain=0)
    grey = np.asarray(img.convert("L"), dtype=np.float64)
    assert not page_has_grain(grey, _policy(cfg)["scan"]["regions"])


def test_a_flat_level_sheet_is_computer_drawn_and_a_grainy_one_a_scan():
    flat, _ = _form(grain=0)
    grainy, _ = _form(grain=6)
    assert cap.capture_of(1, flat, 1.0).kind == "digital_render"
    assert cap.capture_of(1, grainy, 1.0).kind == "scan_or_photo"


def test_a_page_made_differently_from_the_rest_is_named():
    scans = [cap.Capture(i, "scan_or_photo", {"dpi": 150}) for i in (1, 2, 4)]
    odd = cap.mixed_origins({1: "picture", 2: "picture", 3: "picture", 4: "picture"},
                            scans + [cap.Capture(3, "digital_render", {"dpi": 150})], dpi_differ=0.15, dpi_agree=0.05)
    assert odd == [(3, "a picture of a computer-drawn page among scans")]
    resized = [cap.Capture(i, "scan_or_photo", {"dpi": d}) for i, d in ((1, 150), (2, 150), (3, 300))]
    assert cap.mixed_origins({1: "picture", 2: "picture", 3: "picture"}, resized,
                             dpi_differ=0.15, dpi_agree=0.05)[0][0] == 3


def _tok(text, x0, x1, y, conf=0.95):
    class T:
        pass
    t = T()
    t.text, t.box, t.confidence = text, Box(x0, y, x1, y + 10), conf
    return t


def test_a_text_layer_saying_another_number_than_the_picture_read_twice_is_found():
    tokens = [_tok("12,500.00", 100, 160, 700), _tok("4,000.00", 100, 150, 680), _tok("9,999.00", 100, 150, 660)]
    seen = [_tok("12,500.00", 100, 160, 700), _tok("4,000.00", 100, 150, 680), _tok("8,999.00", 100, 150, 660)]
    res = text_layer_versus_scan(1, tokens, seen, lambda box: ("8,999.00", 0.95), confirm=0.8, min_agreement=0.5)
    assert res.applicable and [(d.text_says, d.page_shows) for d in res.disagreements] == [("9,999.00", "8,999.00")]
    # Read once only (the second reading disagrees): nothing is said.
    once = text_layer_versus_scan(1, tokens, seen, lambda box: ("9,999.00", 0.95), confirm=0.8, min_agreement=0.5)
    assert once.disagreements == []
    # A usual misreading (O for 0) is not a disagreement.
    misread = [_tok("12,500.00", 100, 160, 700), _tok("4,000.00", 100, 150, 680), _tok("9,999.O0", 100, 150, 660)]
    assert text_layer_versus_scan(1, tokens, misread, lambda box: ("9,999.O0", 0.95), confirm=0.8,
                                  min_agreement=0.5).disagreements == []


# --- the checks over a file -------------------------------------------------------------

def test_a_value_moved_off_its_line_on_a_scan_is_found(cfg):
    img, words = _form(shift_px=14)
    found = _by_code(scan_checks(_png(img), "png", [_page(1, words)], _policy(cfg)))
    hit = found["IMG_VALUE_IN_LINE"]
    assert hit.status == "warning" and len(hit.evidence) == 1
    l, top, r, b = hit.evidence[0].rect
    assert abs(top - (300 + 4 * 66 + 14) / H_PX) < 0.01 and l > 0.45   # the moved value, where it is
    assert "below its label's line" in hit.evidence[0].observed


def test_a_form_whose_values_sit_on_their_lines_passes(cfg):
    img, words = _form()
    found = _by_code(scan_checks(_png(img), "png", [_page(1, words)], _policy(cfg)))
    assert found["IMG_VALUE_IN_LINE"].status == "pass"
    assert found["IMG_PAGE_ORIGIN"].status == "pass"          # a scan: listed, not a finding
    assert found["PDF_FIGURE_IS_PICTURE"].status == "not_applicable"   # an image file is one picture


def test_pages_of_a_scan_made_differently_are_found(cfg):
    a, wa = _form(seed=1)
    b, wb = _form(seed=2)
    c, wc = _form(grain=0)
    buf = io.BytesIO()
    a.save(buf, "TIFF", save_all=True, append_images=[b, c], dpi=(DPI, DPI))
    pages = [_page(1, wa), _page(2, wb), _page(3, wc)]
    found = _by_code(scan_checks(buf.getvalue(), "tiff", pages, _policy(cfg)))
    hit = found["PAGES_SAME_ORIGIN"]
    assert hit.status == "warning" and hit.evidence[0].page == 3
    assert found["IMG_PAGE_ORIGIN"].status == "warning" and found["IMG_PAGE_ORIGIN"].context
    assert not hit.context                                    # one page swapped in counts

    compiled = _policy(cfg)
    compiled["scan"]["origin"]["max_odd_pages"] = 0
    many = _by_code(scan_checks(buf.getvalue(), "tiff", pages, compiled))["PAGES_SAME_ORIGIN"]
    assert many.status == "warning" and many.context and "put together" in many.finding


def test_every_scan_check_answers_on_a_file_of_text_pages_only(cfg):
    from tests.test_integrity_file import _FIGURE, _drawn

    found = scan_checks(_drawn(_FIGURE), "pdf", [], _policy(cfg))
    assert [f.code for f in found] == list(SCAN_CHECKS) or {f.code for f in found} == set(SCAN_CHECKS)
    assert all(f.status in ("not_applicable", "pass") for f in found)


# --- a small picture carrying a figure, on a scan --------------------------------------

class _Reader:
    """Stands in for OCR: a small picture reads `small`, a page reads nothing."""

    name = "test-reader"

    def __init__(self, small: str):
        self.small = small

    def recognise(self, img, dpi):
        if img.width < 600:
            return OcrResult([Word(self.small, 1, 1, 50, 10, 0.97)], 97.0)
        return OcrResult([], 0.0)


def _scan_pdf(patch: bytes | None) -> bytes:
    """One page: a grainy scan as a picture, and optionally a small picture laid on it."""
    from tests.test_integrity_file import _save

    rng = np.random.default_rng(3)
    scan = np.clip(PAPER + rng.normal(0, 6, (420, 300)), 0, 255).astype(np.uint8).tobytes()
    small = np.full((24, 120), 40, np.uint8).tobytes()
    content = b"q 300 0 0 420 0 0 cm /Scan Do Q" + (b"\nq 60 0 0 12 120 300 cm /Patch Do Q" if patch else b"")

    def image(w, h, raw):
        body = zlib.compress(raw)
        return (b"<</Type/XObject/Subtype/Image/Width %d/Height %d/ColorSpace/DeviceGray/BitsPerComponent 8"
                b"/Filter/FlateDecode/Length %d>>stream\n" % (w, h, len(body)) + body + b"\nendstream ")

    xobjects = b"/Scan 5 0 R" + (b"/Patch 6 0 R" if patch else b"")
    objects = {
        1: b"<</Type/Catalog/Pages 2 0 R>>",
        2: b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        3: b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 420]/Contents 4 0 R/Resources<</XObject<<" + xobjects
           + b">>>>>>",
        4: b"<</Length %d>>stream\n" % len(content) + content + b"\nendstream ",
        5: image(300, 420, scan),
    }
    if patch:
        objects[6] = image(120, 24, small)
    return _save(b"%PDF-1.4\n", objects, b"/Root 1 0 R")


def test_a_small_picture_carrying_a_figure_pasted_on_a_scan_is_found(cfg):
    data = _scan_pdf(patch=b"yes")
    page = Page(1, "ocr", 300.0, 420.0, [], [])
    hit = _by_code(scan_checks(data, "pdf", [page], _policy(cfg), _Reader("4,85,20,000.00")))["PDF_FIGURE_IS_PICTURE"]
    assert hit.status == "review_required" and hit.evidence[0].rect is not None
    l, top, r, b = hit.evidence[0].rect
    assert l == pytest.approx(120 / 300, abs=0.01) and top == pytest.approx((420 - 312) / 420, abs=0.01)


def test_a_stamp_reading_as_a_sentence_with_a_date_is_not_a_figure(cfg):
    data = _scan_pdf(patch=b"yes")
    page = Page(1, "ocr", 300.0, 420.0, [], [])
    reader = _Reader("Signature valid Digitally signed by the issuer Date 2022.07.14")
    assert _by_code(scan_checks(data, "pdf", [page], _policy(cfg), reader))["PDF_FIGURE_IS_PICTURE"].status == "pass"


def test_without_optical_reading_the_pictures_are_not_judged(cfg):
    data = _scan_pdf(patch=b"yes")
    page = Page(1, "ocr", 300.0, 420.0, [], [])
    found = _by_code(scan_checks(data, "pdf", [page], _policy(cfg), None))
    assert found["PDF_FIGURE_IS_PICTURE"].status == "not_applicable"


# --- through the stage ----------------------------------------------------------------

def test_an_image_upload_now_gets_integrity_from_its_pixels(cfg):
    from ingestion.stages.integrity_file import run_integrity_file
    from ingestion.stages.integrity_page import run_integrity_page

    img, words = _form(shift_px=14)
    data = _png(img)
    first = run_integrity_file(data, "png", cfg.integrity)
    assert first.findings == []                                   # the file checks are for PDFs
    whole = run_integrity_page(data, "png", first, cfg.integrity, None, set(), [_page(1, words)])
    assert {f.code for f in whole.findings} == set(SCAN_CHECKS) | set(ARITHMETIC_CHECKS)   # figures: once read
    assert whole.recommendation["code"] == "needs_review"          # one medium-impact indicator
    assert any(s["code"] == "IMG_VALUE_IN_LINE" for s in whole.recommendation["signals"])


# --- a dark mark drawn over a page's picture (fault_detection L3.DARK_MARK_ON_PICTURE) ---

def _marked_scan(mark: bytes | None, *, under: bool = False) -> bytes:
    """One page: a grainy scan as a picture, and a shape drawn over it (or under it)."""
    from tests.test_integrity_file import _save

    rng = np.random.default_rng(5)
    scan = np.clip(PAPER + rng.normal(0, 6, (420, 300)), 0, 255).astype(np.uint8).tobytes()
    picture = b"q 300 0 0 420 0 0 cm /Scan Do Q"
    content = (mark + b"\n" + picture if under else picture + (b"\n" + mark if mark else b""))
    body = zlib.compress(scan)
    objects = {
        1: b"<</Type/Catalog/Pages 2 0 R>>",
        2: b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        3: b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 420]/Contents 4 0 R/Resources<</XObject<</Scan 5 0 R>>>>>>",
        4: b"<</Length %d>>stream\n" % len(content) + content + b"\nendstream ",
        5: b"<</Type/XObject/Subtype/Image/Width 300/Height 420/ColorSpace/DeviceGray/BitsPerComponent 8"
           b"/Filter/FlateDecode/Length %d>>stream\n" % len(body) + body + b"\nendstream ",
    }
    return _save(b"%PDF-1.4\n", objects, b"/Root 1 0 R")


BAR = b"0 0 0 rg 60 300 50 12 re f"


def _covered(cfg, data):
    from ingestion.integrity.pagechecks import page_checks

    return {f.code: f for f in page_checks(data, _policy(cfg), {1})}["PDF_COVERED_TEXT"]


def test_a_solid_dark_bar_drawn_over_a_scan_is_found(cfg):
    hit = _covered(cfg, _marked_scan(BAR))
    assert hit.status == "review_required" and "dark mark" in hit.finding
    left, top, right, bottom = hit.evidence[0].rect
    assert (round(left, 2), round(right, 2)) == (0.2, 0.37) and 0.25 < top < bottom < 0.32


def test_a_bar_under_the_picture_or_a_grey_one_is_not_a_mark(cfg):
    assert _covered(cfg, _marked_scan(BAR, under=True)).status == "not_applicable"
    assert _covered(cfg, _marked_scan(b"0.6 0.6 0.6 rg 60 300 50 12 re f")).status == "not_applicable"


def test_dark_letters_drawn_as_shapes_are_not_a_solid_mark(cfg):
    # Thin strokes inside a bar-shaped outline: dark, but not a solid block.
    strokes = b"0 0 0 rg " + b" ".join(b"%d 300 2 12 re" % x for x in range(60, 110, 8)) + b" f"
    assert _covered(cfg, _marked_scan(strokes)).status == "not_applicable"


# --- how the file was made ---------------------------------------------------------------

def test_how_a_file_was_made_is_one_word():
    assert cap.made_as({1: "text", 2: "text"}, [], None) == "digital"
    assert cap.made_as({1: "text", 2: "picture"}, ["scan_or_photo"], None) == "mixed"
    assert cap.made_as({1: "picture"}, ["scan_or_photo"], None) == "scanned"
    assert cap.made_as({1: "picture"}, ["scan_or_photo"], "Canva") == "design_tool"
    assert cap.made_as({1: "picture"}, ["screen_crop"], None) == "screenshot"
    assert cap.made_as({1: "picture"}, ["digital_render"], None) == "computer_drawn"
    assert cap.made_as({}, [], None) is None


def test_an_image_upload_says_how_it_was_made(cfg):
    from ingestion.stages.integrity_file import IntegrityResult
    from ingestion.stages.integrity_page import run_integrity_page

    img, words = _form(seed=4)
    r = run_integrity_page(_png(img), "png", IntegrityResult([], "no_notable_issue", None, None, []),
                           cfg.integrity, None, set(), pages=[_page(1, words)])
    assert r.facts.made_as.kind == "scanned" and r.facts.made_as.picture_pages == 1


# --- type weight and slant on a scan (fault_detection typestyle) --------------------------

DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf"
needs_fonts = pytest.mark.skipif(not __import__("os").path.exists(DEJAVU.format("")), reason="DejaVu fonts")


def _ink(text: str, face: str = "", size: int = 48):
    from PIL import ImageDraw, ImageFont

    img = Image.new("L", (40 + size * len(text), size * 2), 255)
    ImageDraw.Draw(img).text((20, size // 3), text, fill=0, font=ImageFont.truetype(DEJAVU.format(face), size))
    ink = np.asarray(img) < 128
    rows, cols = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    return ink[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


@needs_fonts
def test_bold_type_has_thicker_strokes_and_oblique_type_leans():
    from ingestion.integrity.typestyle import stroke_and_slant

    regular, bold = _ink("Statement 2024"), _ink("Statement 2024", "-Bold")
    (r_stroke, r_slant), (b_stroke, _) = stroke_and_slant(regular), stroke_and_slant(bold)
    assert b_stroke / bold.shape[0] >= 1.3 * r_stroke / regular.shape[0]
    assert abs(r_slant) < 8 and stroke_and_slant(_ink("Statement 2024", "-Oblique"))[1] >= 8
    assert stroke_and_slant(np.zeros((6, 6), bool)) is None


def _ledger(bold_row: int | None):
    """A scanned column of figures, right-aligned, with labels; one row set in bold."""
    from PIL import ImageDraw, ImageFont

    img = Image.new("L", (W_PX, H_PX), 245)
    draw = ImageDraw.Draw(img)
    regular, bold = (ImageFont.truetype(DEJAVU.format(f), 22) for f in ("", "-Bold"))
    words = []
    for i, (label, value) in enumerate([("Salary credit", "1,25,400.00"), ("Rent paid", "38,000.00"),
                                        ("Interest", "2,315.75"), ("Transfer out", "64,120.00"),
                                        ("Card payment", "9,870.50"), ("Cash deposit", "50,000.00")]):
        y = 300 + i * 60
        draw.text((150, y), label, fill=20, font=regular)
        font = bold if i == bold_row else regular
        right = 1000
        width = draw.textlength(value, font=font)
        draw.text((right - width, y), value, fill=20, font=font)
        for text, x0, x1 in [(label.split()[0], 150, 150 + draw.textlength(label.split()[0], font=regular)),
                             (value, right - width, right)]:
            # OCR's padded box, in points from the top left.
            words.append(Word(text, (x0 - 6) * PT, (y - 4) * PT, (x1 + 6) * PT, (y + 30) * PT, 0.96))
    return img.convert("RGB"), words


@needs_fonts
def test_a_figure_set_bold_in_a_column_of_regular_figures_is_found(cfg):
    img, words = _ledger(bold_row=3)
    found = _by_code(scan_checks(_png(img), "png", [_page(1, words)], _policy(cfg)))
    hit = found["IMG_TYPE_IN_COLUMN"]
    assert hit.status == "warning" and hit.context
    assert len(hit.evidence) == 1 and "64,120.00" in hit.evidence[0].observed and "bold" in hit.evidence[0].observed
    assert hit.evidence[0].rect is not None


@needs_fonts
def test_a_column_set_alike_passes(cfg):
    img, words = _ledger(bold_row=None)
    found = _by_code(scan_checks(_png(img), "png", [_page(1, words)], _policy(cfg)))
    assert found["IMG_TYPE_IN_COLUMN"].status == "pass"
