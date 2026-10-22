"""A statement prints nil as a lone dash that the OCR engine skips; it is read from the image."""

from PIL import Image, ImageDraw

from ingestion.readers.marks import find_dashes
from ingestion.pageindex import Word


def _page(draw) -> Image.Image:
    img = Image.new("RGB", (800, 400), "white")
    draw(ImageDraw.Draw(img))
    return img


def test_a_lone_dash_is_found_in_points():
    img = _page(lambda d: d.rectangle([400, 200, 408, 202], fill="black"))
    (w,) = find_dashes(img, 200, [])
    assert w.text == "-" and round(w.x0) == 144 and round(w.y0) == 72


def test_a_dash_inside_a_recognised_word_is_left_to_that_word():
    img = _page(lambda d: d.rectangle([400, 200, 408, 202], fill="black"))
    assert find_dashes(img, 200, [(140, 70, 150, 76)]) == []


def test_a_rule_a_glyph_and_a_dash_touching_text_are_not_dashes():
    def draw(d):
        d.rectangle([50, 100, 700, 102], fill="black")          # a table rule: too long
        d.rectangle([300, 200, 303, 215], fill="black")         # a vertical stroke: too tall
        d.rectangle([500, 300, 508, 302], fill="black")         # a dash with ink right beside it
        d.rectangle([511, 296, 513, 306], fill="black")
    assert find_dashes(_page(draw), 200, []) == []


def test_found_marks_are_words():
    assert isinstance(find_dashes(_page(lambda d: d.rectangle([100, 50, 108, 52], fill="black")), 200, [])[0], Word)
