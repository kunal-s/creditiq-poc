"""The scanned-document path, without a real OCR engine: a fake engine returns the words the page
really contains, so the tests exercise routing, grading, caching and what grades do downstream."""

import io

import pytest
from PIL import Image, ImageFilter

from ingestion.pipeline import Ingestor
from ingestion.readers import imagequal
from ingestion.readers.ocr import OcrResult, split_line_box
from ingestion.readers.pdf_text import read_text_layer, render_page
from ingestion.store import Store
from ingestion.util import sha256_hex

from .conftest import fixture_doc, spec, values

COI = "Southgate_Certificate_of_Incorporation.pdf"


class FakeOcr:
    name = "fake"

    def __init__(self, cfg, src: str, conf: float = 97.0):
        self.words = read_text_layer(fixture_doc(src), cfg.routing.reading)[0].words
        self.conf, self.calls = conf, 0

    def recognise(self, img, dpi):
        self.calls += 1
        return OcrResult(list(self.words), self.conf)


@pytest.fixture()
def relaxed(cfg):
    """Image-measure thresholds out of the way, so only the OCR confidence decides the grade."""
    c = cfg.model_copy(deep=True)
    c.quality.blur_sharpness_min, c.quality.skew_degrees_max, c.quality.shadow_spread_max = 0, 90, 10_000
    return c


def scanned_pdf(name=COI) -> bytes:
    img = render_page(fixture_doc(name), 1, 200)
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=200)
    return buf.getvalue()


def test_image_only_pdf_goes_through_ocr_and_extracts(relaxed):
    ocr = FakeOcr(relaxed, COI)
    data = scanned_pdf()
    r = Ingestor(relaxed, Store(), None, ocr).process_file("C", spec("scan.pdf", data), data)
    assert r.pages[0].source == "ocr" and r.pages[0].grade == "A" and r.pages[0].ocr_conf == 97.0
    assert r.classification.type == "certificate_of_incorporation"
    assert values(r.documents[0])["cin"] == "U17291TZ2016PTC027431" and r.route["ocr_pages"] == 1


def test_png_photo_is_read_by_ocr(relaxed):
    buf = io.BytesIO()
    render_page(fixture_doc(COI), 1, 200).save(buf, "PNG")
    data = buf.getvalue()
    r = Ingestor(relaxed, Store(), None, FakeOcr(relaxed, COI)).process_file("C", spec("photo.png", data, "image/png"), data)
    assert r.source["kind"] == "png" and r.pages[0].source == "ocr"
    assert values(r.documents[0])["date_of_incorporation"] == "2016-03-18"


def test_poor_ocr_confidence_grades_c_and_sends_every_key_field_to_review(relaxed):
    data = scanned_pdf()
    r = Ingestor(relaxed, Store(), None, FakeOcr(relaxed, COI, conf=55.0)).process_file("C", spec("scan.pdf", data), data)
    assert r.pages[0].grade == "C" and "ocr_floor" in r.pages[0].reasons and r.grade == "C"
    d = r.documents[0]
    assert all(f.confidence <= 0.6 for f in d.fields.values() if f.status == "found")
    assert r.decision == "human_review" and {x["kind"] for x in r.review_reasons} == {"field_review"}


def test_degraded_confidence_grades_b(relaxed):
    data = scanned_pdf()
    r = Ingestor(relaxed, Store(), None, FakeOcr(relaxed, COI, conf=70.0)).process_file("C", spec("scan.pdf", data), data)
    assert r.pages[0].grade == "B" and r.documents[0].fields["cin"].components["page_grade"] == 0.8


def test_ocr_result_is_cached_by_page_image(relaxed):
    ocr, store = FakeOcr(relaxed, COI), Store()
    data = scanned_pdf()
    ing = Ingestor(relaxed, store, None, ocr)
    a = ing.process_file("C", spec("scan.pdf", data), data)
    b = ing.process_file("C2", spec("scan.pdf", data), data)
    assert ocr.calls == 1 and a.documents[0].fields["cin"].value == b.documents[0].fields["cin"].value


def test_no_ocr_engine_means_unreadable_with_a_reason_not_a_guess(cfg):
    data = scanned_pdf()
    r = Ingestor(cfg, Store(), None, None).process_file("C", spec("scan.pdf", data), data)
    assert r.pages[0].grade == "U" and r.pages[0].reasons == ["ocr_unavailable"]
    assert r.decision == "reject" and r.documents == [] and r.classification.type is None
    assert "ocr_unavailable" in cfg.quality.reason_codes


def test_a_blank_scan_is_a_blank_page_not_a_document(relaxed):
    buf = io.BytesIO()
    Image.new("RGB", (1654, 2339), "white").save(buf, "PNG")
    r = Ingestor(relaxed, Store(), None, FakeOcr(relaxed, COI)).process_file("C", spec("b.png", buf.getvalue(), "image/png"), buf.getvalue())
    assert r.pages[0].blank and r.pages[0].grade == "U" and r.grade == "U" and r.decision == "reject"


def test_low_resolution_image_is_at_most_grade_b(relaxed):
    buf = io.BytesIO()
    render_page(fixture_doc(COI), 1, 100).save(buf, "PNG", dpi=(100, 100))
    r = Ingestor(relaxed, Store(), None, FakeOcr(relaxed, COI)).process_file("C", spec("lo.png", buf.getvalue(), "image/png"), buf.getvalue())
    assert "resolution" in r.pages[0].reasons and r.pages[0].grade == "B"


def test_image_measures_see_blur_skew_and_shadow():
    img = render_page(fixture_doc(COI), 1, 150)
    assert imagequal.sharpness(img) > imagequal.sharpness(img.filter(ImageFilter.GaussianBlur(2.5)))
    assert imagequal.skew_degrees(img.rotate(3, fillcolor="white", expand=True)) >= 2.0 > imagequal.skew_degrees(img)
    w, h = img.size
    ramp = Image.linear_gradient("L").resize((w, h)).convert("RGB")
    shaded = Image.blend(img, ramp, 0.5)
    assert imagequal.shadow_spread(shaded) > imagequal.shadow_spread(img) + 20
    assert imagequal.ink_ratio(Image.new("RGB", (400, 400), "white")) == 0.0


def test_line_box_is_split_into_words_in_proportion():
    ws = split_line_box("ab cdef", 0, 0, 70, 10, 0.9)
    assert [w.text for w in ws] == ["ab", "cdef"] and ws[0].x0 == 0 and abs(ws[1].x1 - 70) < 1e-6 and ws[0].x1 < ws[1].x0
