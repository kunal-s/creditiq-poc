"""F-07A, use case 1: what a file's bytes say about its own history.

The fixtures are built here rather than committed, so the suite needs no sample
file and no document of the bank's. Each one is the smallest PDF that shows the
thing being measured.
"""

from __future__ import annotations

import pytest

from ingestion.integrity.forensics import examine
from ingestion.integrity.meta import read_meta
from ingestion.stages.integrity_file import run_integrity_file
from ingestion.stages.quality import pdf_header_at, sniff


# --- the smallest PDFs that show each thing ---------------------------------

def _pdf(producer: str = "pdfmake", created: str = "D:20250301101500+05:30",
         modified: str | None = None, body: str = "(1,00,000.00) Tj") -> bytes:
    """One revision, one page, one figure."""
    mod = modified or created
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 40>>stream\nBT " + body.encode() + b" ET\nendstream endobj\n"
        b"5 0 obj<</Producer(" + producer.encode() + b")/CreationDate(" + created.encode() + b")"
        b"/ModDate(" + mod.encode() + b")>>endobj\n"
        b"trailer<</Root 1 0 R/Info 5 0 R/ID[<AABB> <AABB>]>>\n%%EOF\n")


def _resaved(was: str = "1,00,000.00", now: str = "9,00,000.00") -> bytes:
    """Two revisions: the second redefines the page's content with a new figure,
    and the first is still in the bytes."""
    first = _pdf(body=f"({was}) Tj")
    second = (b"4 0 obj<</Length 40>>stream\nBT (" + now.encode() + b") Tj ET\nendstream endobj\n"
              b"trailer<</Root 1 0 R/Info 5 0 R/ID[<AABB> <CCDD>]>>\n%%EOF\n")
    return first + second


# --- the sniff, which is what let the e-filing portal's files through --------

def test_sniff_finds_a_pdf_behind_a_wrapper():
    """Every income tax return from the e-filing portal carries 247 bytes of a
    Java object stream before %PDF-; both readers tolerate it, so the sniff must."""
    wrapped = b"\xac\xed\x00\x05ur\x00\x13[Ljava.lang.Object;" + b"\x00" * 200 + _pdf()
    assert sniff(wrapped) == "pdf"
    assert pdf_header_at(wrapped) == len(wrapped) - len(_pdf())


def test_sniff_still_refuses_a_file_that_merely_mentions_the_header():
    assert sniff(b"the string %PDF- appears in this text file") is None
    assert sniff(b"") is None
    assert sniff(b"\x89PNG\r\n\x1a\n") == "png"


# --- the bytes --------------------------------------------------------------

def test_one_revision_is_not_a_signal(cfg):
    r = run_integrity_file(_pdf(), "pdf", cfg.integrity)
    assert r.recommendation["code"] == "no_notable_issue"
    by = {f.code: f for f in r.findings}
    assert by["PDF_INCREMENTAL_UPDATE"].status == "pass"
    assert by["PDF_PRIOR_VALUE_RECOVERABLE"].status == "not_applicable"


def test_an_earlier_figure_left_in_the_file_is_recovered(cfg):
    r = run_integrity_file(_resaved(), "pdf", cfg.integrity)
    found = next(f for f in r.findings if f.code == "PDF_PRIOR_VALUE_RECOVERABLE")
    assert found.status == "review_required"
    assert "1,00,000.00" in found.finding and "9,00,000.00" in found.finding
    assert r.recommendation["code"] in ("needs_review_priority", "high_risk_indicators")


def test_a_changed_identifier_is_listed_but_never_routes(cfg):
    r = run_integrity_file(_resaved(), "pdf", cfg.integrity)
    found = next(f for f in r.findings if f.code == "PDF_ID_PAIR_DIFFERS")
    assert found.status == "warning"
    assert found.context is True
    assert "PDF_ID_PAIR_DIFFERS" not in [s["code"] for s in r.recommendation["signals"]]


def test_signing_accounts_for_its_own_revision(cfg):
    """Applying a signature appends a revision. Counting it would call every
    properly signed document into question."""
    signed = _pdf() + (b"6 0 obj<</Type/Sig/Contents<00>>>endobj\n"
                       b"trailer<</Root 1 0 R/ID[<AABB> <CCDD>]>>\n%%EOF\n")
    f = examine(signed)
    assert f.revision_count == 2 and f.signature_count == 1 and f.unexplained_revisions == 0
    found = next(x for x in run_integrity_file(signed, "pdf", cfg.integrity).findings
                 if x.code == "PDF_INCREMENTAL_UPDATE")
    assert found.status == "pass"


def test_padding_after_the_last_eof_is_not_a_revision():
    """Signing tools pad a file out to a block size with NULs. Counted as
    content, that padding becomes a phantom revision."""
    assert examine(_pdf() + b"\x00" * 118).revision_count == 1


# --- what the file says about itself ----------------------------------------

def test_a_modified_date_before_the_created_date_is_a_signal(cfg):
    impossible = _pdf(created="D:20250301101500+05:30", modified="D:20250101090000+05:30")
    found = next(f for f in run_integrity_file(impossible, "pdf", cfg.integrity).findings
                 if f.code == "METADATA_DATE_ORDER")
    assert found.status == "warning"


def test_an_editing_tool_is_listed_but_never_routes(cfg):
    r = run_integrity_file(_pdf(producer="Canva"), "pdf", cfg.integrity)
    found = next(f for f in r.findings if f.code == "PDF_WRITTEN_BY_EDITING_TOOL")
    assert found.status == "warning" and found.context is True
    assert "Canva" in found.finding
    assert r.recommendation["code"] == "no_notable_issue"


def test_printing_again_explains_the_extra_revision(cfg):
    """Printing a document again is not an edit; it only loses what the
    original file could show."""
    reprinted = _pdf(producer="Microsoft: Print To PDF") + b"trailer<</Root 1 0 R>>\n%%EOF\n"
    found = next(f for f in run_integrity_file(reprinted, "pdf", cfg.integrity).findings
                 if f.code == "PDF_INCREMENTAL_UPDATE")
    assert found.status == "pass"


@pytest.mark.parametrize("doc_type,expected", [("gstr_3b", "pass"), ("income_tax_return", "warning")])
def test_the_producing_program_is_checked_against_the_type(cfg, doc_type, expected):
    found = next(f for f in run_integrity_file(_pdf(producer="pdfmake"), "pdf", cfg.integrity, doc_type).findings
                 if f.code == "METADATA_PRODUCER_EXPECTED")
    assert found.status == expected


def test_every_configured_check_produces_a_result(cfg):
    """Nothing is dropped silently: a check in the configuration that no code
    runs would be invisible, and a reader would never learn it was not run."""
    from ingestion.stages.integrity_page import run_integrity_page

    data = _pdf()
    whole = run_integrity_page(data, "pdf", run_integrity_file(data, "pdf", cfg.integrity), cfg.integrity,
                               None, set())
    produced = {f.code for f in whole.findings}
    assert len(produced) == len(whole.findings), "a check answered twice"
    assert produced == set(cfg.integrity.checks), (
        f"configured but never produced: {set(cfg.integrity.checks) - produced}; "
        f"produced but not configured: {produced - set(cfg.integrity.checks)}")


def test_a_type_that_skips_a_check_says_why(cfg):
    """`skip_for_type` is empty in this version; when it is filled, a skipped
    check must still appear, as not_applicable, with the reason."""
    policy = cfg.integrity.model_dump(mode="python")
    policy["skip_for_type"] = {"METADATA_DATE_ORDER": {"company_pan": "an identity document states no dates"}}
    from ingestion.integrity import file_checks
    found = next(f for f in file_checks(_pdf(), policy, "company_pan") if f.code == "METADATA_DATE_ORDER")
    assert found.status == "not_applicable"
    assert found.skipped_for_type == "company_pan"
    assert "an identity document states no dates" in found.finding


# --- the shape --------------------------------------------------------------

def test_a_file_that_is_not_a_pdf_says_so_rather_than_passing(cfg):
    r = run_integrity_file(b"\x89PNG\r\n\x1a\n", "png", cfg.integrity)
    assert r.findings == []
    assert r.recommendation["code"] == "not_applicable"


def test_every_finding_names_what_it_measured_and_the_limit(cfg):
    for f in run_integrity_file(_resaved(), "pdf", cfg.integrity).findings:
        assert f.finding and f.finding[0].isupper() and f.finding.endswith(".")
        assert f.method["policy_version"] == cfg.integrity.version
        for e in f.evidence:
            assert e.observed and e.threshold


def test_no_finding_uses_a_word_the_screens_may_not_say(cfg):
    """A finding is an indicator for a person, never a verdict."""
    banned = ("fraud", "forged", "fake", "tampered", "tamper")
    for data in (_pdf(), _resaved(), _pdf(producer="Canva")):
        for f in run_integrity_file(data, "pdf", cfg.integrity).findings:
            assert not any(w in f.finding.lower() for w in banned), f.finding


def test_the_metadata_reader_never_invents_a_date():
    meta = read_meta(_pdf(created="not a date at all"))
    assert meta.created is None


# --- what integrity does to the pipeline's decision --------------------------

class _Rec:
    """Just enough of the stage's result for the decision rule."""

    def __init__(self, code: str):
        self.recommendation = {"code": code, "why": "measured here"}


@pytest.mark.parametrize("code,escalates,recorded", [
    ("no_notable_issue", False, False),
    ("not_applicable", False, False),
    ("needs_review", False, True),
    ("needs_review_priority", True, True),
    ("high_risk_indicators", True, True),
])
def test_what_each_recommendation_does_to_a_document(code, escalates, recorded):
    """A single low-impact observation is written down so a reader sees it, but
    it does not hold up a document: a bank's own system saves a file again."""
    from ingestion.pipeline import INTEGRITY_ESCALATES, _integrity_reason

    reasons: list[dict] = []
    got = _integrity_reason(_Rec(code), reasons)
    assert (got in INTEGRITY_ESCALATES) is escalates
    assert bool(reasons) is recorded
    if recorded:
        assert reasons[0] == {"kind": "integrity", "code": code, "detail": "measured here"}


def test_integrity_never_rejects_a_document():
    """Extraction always runs. A wrong figure that is extracted and flagged is
    more use to a credit officer than a document that disappeared."""
    from ingestion.pipeline import INTEGRITY_ESCALATES

    assert "reject" not in INTEGRITY_ESCALATES


def _real_pdf_resaved() -> bytes:
    """A readable PDF with a revision appended, as an editor that saves
    incrementally leaves one. Built from a fixture so `read` can open it."""
    from tests.conftest import FIXTURE_DOCS

    base = next(FIXTURE_DOCS.glob("*.pdf")).read_bytes()
    return base + (b"\n4 0 obj<</Length 24>>stream\nBT (9,99,999.00) Tj ET\nendstream endobj\n"
                   b"trailer<</Root 1 0 R/ID[<AA> <BB>]>>\n%%EOF\n")


def test_the_stage_runs_before_the_file_is_read(cfg):
    """The point of reading the bytes first is that it costs no OCR: a re-saved
    file is flagged before a page is rendered."""
    import hashlib

    import pytest as _pytest

    from ingestion.contracts import FileSpec
    from ingestion.pipeline import Ingestor
    from ingestion.store import Store

    try:
        data = _real_pdf_resaved()
    except StopIteration:
        _pytest.skip("no PDF fixture to append a revision to")
    spec = FileSpec(file_id="F-ORDER", sha256=hashlib.sha256(data).hexdigest(),
                    original_name="x.pdf", content_type="application/pdf")
    r = Ingestor(cfg, Store(), None, None).process_file("CASE-ORDER", spec, data)
    stages = [e.stage for e in r.trace]
    assert stages.index("integrity_file") < stages.index("read")
    assert r.integrity_recommendation in ("needs_review", "needs_review_priority")
    assert any(x.get("kind") == "integrity" for x in r.review_reasons)


def test_a_file_that_cannot_be_read_keeps_what_integrity_already_found(cfg):
    """Integrity reads the bytes before the file is read at all. A file that
    cannot be read is exactly one worth saying that about, so a later crash
    must not throw the findings away."""
    import hashlib

    from ingestion.contracts import FileSpec
    from ingestion.pipeline import Ingestor
    from ingestion.store import Store

    data = _resaved()  # pypdfium2 opens it; pdfplumber will not
    spec = FileSpec(file_id="F-CRASH", sha256=hashlib.sha256(data).hexdigest(),
                    original_name="x.pdf", content_type="application/pdf")
    r = Ingestor(cfg, Store(), None, None).process_file("CASE-CRASH", spec, data)
    assert r.status == "failed"
    assert r.integrity_recommendation == "needs_review_priority"
    assert any(f.code == "PDF_PRIOR_VALUE_RECOVERABLE" and f.status == "review_required"
               for f in r.integrity)


# --- where on the page a finding points ---------------------------------------

def _page(no: int, *words: tuple[str, float, float, float, float]):
    from ingestion.pageindex import Page, Word

    return Page(no=no, source="text_layer", width=600.0, height=800.0,
                words=[Word(t, x0, y0, x1, y1) for t, x0, y0, x1, y1 in words])


def _finding(locate: str | None):
    from ingestion.contracts import IntegrityEvidence, IntegrityFinding

    return IntegrityFinding(code="PDF_PRIOR_VALUE_RECOVERABLE", family="history", status="review_required",
                            finding="An earlier figure is still in the file.", tier="T1", impact="high",
                            evidence=[IntegrityEvidence(page=1, observed="was / now", threshold="t", locate=locate)])


def test_a_recovered_figure_is_placed_where_it_is_printed():
    from ingestion.integrity.locate import locate

    pages = [_page(1, ("Balance", 10, 10, 60, 20)), _page(2, ("23,27,400.00", 480, 120, 540, 130))]
    [f] = locate([_finding("23,27,400.00")], pages)
    e = f.evidence[0]
    assert e.page == 2
    assert e.rect == (0.8, 0.15, 0.9, 0.1625)


def test_a_figure_printed_with_a_rupee_sign_is_still_found():
    from ingestion.integrity.locate import locate

    [f] = locate([_finding("23,27,400.00")], [_page(1, ("₹23,27,400.00", 0, 0, 60, 8))])
    assert f.evidence[0].rect is not None


def test_a_figure_not_on_any_page_is_left_unplaced_never_guessed():
    from ingestion.integrity.locate import locate

    [f] = locate([_finding("99,99,999.00")], [_page(1, ("23,27,400.00", 0, 0, 60, 8))])
    assert f.evidence[0].rect is None


def test_evidence_about_the_file_itself_has_no_place_on_a_page():
    """A revision or a metadata record is in the file, not printed anywhere."""
    from ingestion.integrity.locate import locate

    [f] = locate([_finding(None)], [_page(1, ("23,27,400.00", 0, 0, 60, 8))])
    assert f.evidence[0].rect is None and f.evidence[0].locate is None


def test_the_recovered_figure_names_the_text_to_find(cfg):
    found = next(f for f in run_integrity_file(_resaved(), "pdf", cfg.integrity).findings
                 if f.code == "PDF_PRIOR_VALUE_RECOVERABLE")
    assert found.evidence[0].locate == "9,00,000.00"


# --- what the file says about itself, kept for a reader -------------------------

def test_the_file_facts_are_kept_for_a_reader(cfg):
    """The records every answer comes from are kept, so a reader sees what a
    verdict rests on instead of taking it on trust."""
    r = run_integrity_file(_resaved(), "pdf", cfg.integrity)
    f = r.facts
    assert f.pdf_version == "1.4" and f.header_offset == 0 and f.size_bytes == len(_resaved())
    assert f.info["Producer"] == "pdfmake"
    assert f.info_dates["CreationDate"].startswith("2025-03-01T10:15:00")
    assert [x.index for x in f.revisions] == [0, 1]
    assert f.id_original == "aabb" and f.id_current == "ccdd"
    assert [(x.was, x.now) for x in f.recovered] == [("1,00,000.00", "9,00,000.00")]


def test_a_wrapped_pdf_says_where_its_header_starts(cfg):
    wrapped = b"\xac\xed\x00\x05" + b"\x00" * 243 + _pdf()
    assert run_integrity_file(wrapped, "pdf", cfg.integrity).facts.header_offset == 247


def test_every_check_names_the_facts_it_read(cfg):
    """Touch a check and see the records behind it: every key it names is one
    the facts carry."""
    keys = {"revisions", "signatures", "recovered", "id"}
    for f in run_integrity_file(_pdf(), "pdf", cfg.integrity).findings:
        assert f.reads, f.code
        for k in f.reads:
            assert k in keys or k.split(".")[0] in ("info", "xmp"), (f.code, k)


def test_fonts_are_named_without_their_subset_prefix():
    from ingestion.integrity.forensics import examine

    data = _pdf().replace(b"5 0 obj", b"6 0 obj<</Type/Font/BaseFont/ABCDEF+Helvetica#20Bold>>endobj\n5 0 obj", 1)
    assert examine(data).fonts == ["Helvetica Bold"]


# --- what a later save wrote, and where the page draws it --------------------

def _save(prefix: bytes, objects: dict[int, bytes], trailer: bytes, prev: int | None = None) -> bytes:
    """`prefix` followed by one save: its objects, a cross-reference section for
    them, and a trailer, as a writer lays them out."""
    out, at = bytearray(prefix), {}
    for n, body in objects.items():
        at[n] = len(out)
        out += b"%d 0 obj" % n + body + b"endobj\n"
    xref = len(out)
    out += b"xref\n"
    if prev is None:
        out += b"0 1\n0000000000 65535 f \n"
    for n in sorted(at):
        out += b"%d 1\n%010d 00000 n \n" % (n, at[n])
    size = max(at) + 1
    out += (b"trailer\n<<" + trailer + b"/Size %d" % size + (b"/Prev %d" % prev if prev is not None else b"")
            + b">>\nstartxref\n%d\n%%%%EOF\n" % xref)
    return bytes(out)


def _repainted() -> bytes:
    """A printed file, then a later save that replaces the page and paints a new
    image over part of it — the shape of a figure covered by a patch."""
    image = (b"<</Type/XObject/Subtype/Image/Width 1/Height 1/ColorSpace/DeviceGray"
             b"/BitsPerComponent 8%s/Length 1>>stream\n\xff\nendstream ")
    first = _save(b"%PDF-1.4\n", {
        1: b"<</Type/Catalog/Pages 2 0 R>>",
        2: b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        3: b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R>>",
        4: b"<</Length 22>>stream\nBT (1,00,000.00) Tj ET\nendstream ",
        5: b"<</Producer(Microsoft: Print To PDF)/CreationDate(D:20250301101500+05'30')>>",
    }, b"/Root 1 0 R/Info 5 0 R")
    return _save(first, {
        3: b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 7 0 R"
           b"/Resources<</XObject<</Im0 6 0 R>>>>>>",
        6: image % b"/SMask 8 0 R",
        7: b"<</Length 31>>stream\nq 50 0 0 20 10 150 cm /Im0 Do Q\nendstream ",
        8: image % b"",
    }, b"/Root 1 0 R/Info 5 0 R", prev=first.rindex(b"xref"))


def test_each_later_save_says_what_it_replaced_and_added():
    f = examine(_repainted())
    later = f.revisions[1]
    assert [(o.number, o.kind) for o in later.replaced] == [(3, "page")]
    assert [(o.number, o.kind) for o in later.added] == [(6, "image"), (7, "stream"), (8, "mask")]
    assert (later.replaced_count, later.added_count) == (1, 3)
    assert f.revisions[0].replaced == f.revisions[0].added == ()


def test_printing_does_not_explain_a_later_save_that_repainted_the_page(cfg):
    """A printer writes a whole file in one save. A second save that changed what
    the page draws was written by something else, whatever the producer says."""
    found = {x.code: x for x in run_integrity_file(_repainted(), "pdf", cfg.integrity).findings}
    assert found["PDF_INCREMENTAL_UPDATE"].status == "warning"
    assert any("save 2: bytes" in e.observed for e in found["PDF_INCREMENTAL_UPDATE"].evidence)
    assert "saved again afterwards" in found["PDF_WRITTEN_BY_EDITING_TOOL"].finding


def test_what_a_later_save_painted_is_placed_where_the_page_draws_it(cfg):
    from ingestion.integrity.locate import WHOLE_PAGE, place_objects

    data = _repainted()
    found = place_objects(run_integrity_file(data, "pdf", cfg.integrity).findings, data)
    touched = next(x for x in found if x.code == "REVISIONS_TOUCH_CONTENT")
    spots = {e.object: (e.page, e.rect) for e in touched.evidence}
    assert spots[3] == (1, WHOLE_PAGE)  # the page it replaced, first
    assert touched.evidence[0].object == 3
    page, rect = spots[6]  # the image it painted, at its box
    assert page == 1 and rect == pytest.approx((0.05, 0.15, 0.30, 0.25), abs=0.01)
    assert 8 not in spots  # a soft mask is not something the page paints


def test_an_object_no_page_draws_is_left_unplaced():
    from ingestion.contracts import IntegrityEvidence, IntegrityFinding
    from ingestion.integrity.locate import place_objects

    finding = IntegrityFinding(code="REVISIONS_TOUCH_CONTENT", family="history", status="warning",
                               finding="x", tier="T1", impact="high", method={},
                               evidence=[IntegrityEvidence(page=1, observed="o", threshold="t", object=99)])
    placed = place_objects([finding], _repainted())
    assert placed[0].evidence[0].rect is None


# --- phase 2: what each page draws ---------------------------------------------

_FONTS = b"/Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>/F2<</Type/Font/Subtype/Type1/BaseFont/Courier>>>>"


def _drawn(content: bytes, extra: dict[int, bytes] | None = None, xobjects: bytes = b"",
          annots: bytes = b"") -> bytes:
    """One 200 × 200 pt page drawing `content`, with Helvetica (F1) and Courier (F2)."""
    return _save(b"%PDF-1.4\n", {
        1: b"<</Type/Catalog/Pages 2 0 R>>",
        2: b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        3: b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<<" + _FONTS
           + (b"/XObject<<" + xobjects + b">>" if xobjects else b"") + b">>" + annots + b">>",
        4: b"<</Length %d>>stream\n" % len(content) + content + b"\nendstream ",
        **(extra or {}),
    }, b"/Root 1 0 R")


_FIGURE = b"BT /F1 12 Tf 20 100 Td (1,00,000.00) Tj ET"
_IMAGE = (b"<</Type/XObject/Subtype/Image/Width 1/Height 1/ColorSpace/DeviceGray"
          b"/BitsPerComponent 8/Length 1>>stream\n\xff\nendstream ")


def _page_found(cfg, data: bytes, scanned: set[int] | None = None) -> dict:
    from ingestion.integrity.pagechecks import page_checks

    return {f.code: f for f in page_checks(data, cfg.integrity.model_dump(mode="python"), scanned)}


def test_a_block_painted_over_a_figure_hides_it(cfg):
    found = _page_found(cfg, _drawn(_FIGURE + b"\n0 0 0 rg 15 95 90 20 re f"))["PDF_COVERED_TEXT"]
    assert found.status == "review_required"
    page, rect = found.evidence[0].page, found.evidence[0].rect
    assert page == 1 and rect == pytest.approx((0.075, 0.425, 0.525, 0.525), abs=0.01)


def test_a_cell_background_painted_under_a_figure_hides_nothing(cfg):
    found = _page_found(cfg, _drawn(b"0.9 g 15 95 90 20 re f\n0 g " + _FIGURE))
    assert found["PDF_COVERED_TEXT"].status == "pass"


def test_a_picture_pasted_over_a_figure_is_marked_where_it_lies(cfg):
    data = _drawn(_FIGURE + b"\nq 80 15 0 0 15 98 cm /Im0 Do Q", {5: _IMAGE}, xobjects=b"/Im0 5 0 R")
    found = _page_found(cfg, data)["PDF_PICTURE_OVER_TEXT"]
    assert found.status == "warning"
    assert found.evidence[0].rect == pytest.approx((0.075, 0.435, 0.475, 0.51), abs=0.01)


def test_an_annotation_box_laid_over_a_figure_hides_it(cfg):
    annot = (b"/Annots[<</Type/Annot/Subtype/Square/Rect[15 95 105 115]/IC[1 1 1]/C[1 1 1]>>]")
    found = _page_found(cfg, _drawn(_FIGURE, annots=annot))["PDF_COVERED_TEXT"]
    assert found.status == "review_required"
    assert "annotation" in found.evidence[0].observed


def test_text_drawn_invisibly_or_too_small_to_read_is_hidden(cfg):
    invisible = _drawn(b"BT /F1 12 Tf 3 Tr 20 100 Td (9,00,000.00) Tj ET\nBT /F1 12 Tf 20 150 Td (Opening) Tj ET")
    tiny = _drawn(_FIGURE + b"\nBT /F1 1 Tf 20 60 Td (9,00,000.00) Tj ET")
    assert _page_found(cfg, invisible)["HIDDEN_TEXT"].status == "warning"
    assert _page_found(cfg, tiny)["HIDDEN_TEXT"].status == "warning"
    assert _page_found(cfg, _drawn(_FIGURE))["HIDDEN_TEXT"].status == "pass"


def test_text_placed_off_the_page_is_outside_its_visible_area(cfg):
    found = _page_found(cfg, _drawn(_FIGURE + b"\nBT /F1 12 Tf 20 300 Td (9,99,999.00) Tj ET"))
    assert found["PDF_TEXT_OUTSIDE_VISIBLE_AREA"].status == "warning"


def test_a_value_set_in_two_typefaces_stands_out(cfg):
    mixed = _drawn(b"BT /F1 12 Tf 20 100 Td (12,3) Tj /F2 12 Tf (45.00) Tj ET")
    found = _page_found(cfg, mixed)["FONT_WITHIN_VALUE"]
    assert found.status == "warning" and found.evidence[0].rect is not None
    assert _page_found(cfg, _drawn(_FIGURE))["FONT_WITHIN_VALUE"].status == "pass"


def test_a_scanned_page_is_said_to_have_no_text_of_its_own(cfg):
    found = _page_found(cfg, _drawn(_FIGURE + b"\n0 0 0 rg 15 95 90 20 re f"), scanned={1})
    assert {f.status for f in found.values()} == {"not_applicable"}
    assert "OCR" in found["PDF_COVERED_TEXT"].finding


def test_the_page_stage_adds_its_checks_and_answers_the_producer_by_type(cfg):
    """Integrity runs on the bytes before the file is classified, so the producing
    program can only be compared with the type once the type is known."""
    from ingestion.stages.integrity_page import run_integrity_page

    data = _drawn(_FIGURE + b"\n0 0 0 rg 15 95 90 20 re f")
    first = run_integrity_file(data, "pdf", cfg.integrity)
    assert next(f for f in first.findings if f.code == "METADATA_PRODUCER_EXPECTED").status == "not_applicable"
    whole = run_integrity_page(data, "pdf", first, cfg.integrity, "gstr_3b", set())
    producer = next(f for f in whole.findings if f.code == "METADATA_PRODUCER_EXPECTED")
    assert producer.status == "unable_to_determine"  # the file names no producer; a GSTR-3B is pdfmake's
    assert whole.recommendation["code"] == "needs_review_priority"
    assert any(s["code"] == "PDF_COVERED_TEXT" for s in whole.recommendation["signals"])


def _column(odd: bytes = b"/F1 12 Tf") -> bytes:
    """Five amounts right-aligned on one edge, as a column of figures is set;
    the fourth set with `odd`."""
    rows = [b"1,00,000.00", b"2,50,000.00", b"3,10,000.00", b"4,00,000.00", b"5,75,000.00"]
    content = b""
    for n, row in enumerate(rows):
        font = odd if n == 3 else b"/F1 12 Tf"
        size = float(font.split()[1])
        # Standard widths, in thousandths of an em: Helvetica digits 556 and
        # marks 278; every Courier glyph 600.
        em = (600 * len(row) if font.startswith(b"/F2") else
              sum(556 if c in b"0123456789" else 278 for c in row)) / 1000
        content += b"BT %s 1 0 0 1 %.2f %d Tm (%s) Tj ET\n" % (font, 180 - em * size, 180 - 20 * n, row)
    return _drawn(content)


def test_a_figure_set_in_another_typeface_from_its_column_stands_out(cfg):
    found = _page_found(cfg, _column(odd=b"/F2 12 Tf"))["PDF_FIGURE_TYPESET_DIFFERENTLY"]
    assert found.status == "warning" and len(found.evidence) == 1
    assert "Courier" in found.evidence[0].observed and "Helvetica" in found.evidence[0].observed
    assert found.evidence[0].rect is not None


def test_a_figure_set_in_another_size_from_its_column_stands_out(cfg):
    found = _page_found(cfg, _column(odd=b"/F1 14 Tf"))["PDF_FIGURE_TYPESET_DIFFERENTLY"]
    assert found.status == "warning"


def test_a_column_set_alike_passes(cfg):
    assert _page_found(cfg, _column())["PDF_FIGURE_TYPESET_DIFFERENTLY"].status == "pass"


def test_every_figure_read_is_kept_with_its_place_font_and_column(cfg):
    from ingestion.integrity.pagechecks import read_pages

    figures = read_pages(_column(), cfg.integrity.model_dump(mode="python")).figures
    assert [f.text for f in figures] == ["1,00,000.00", "2,50,000.00", "3,10,000.00", "4,00,000.00", "5,75,000.00"]
    assert {f.font for f in figures} == {"Helvetica"} and {f.size for f in figures} == {12.0}
    assert len({f.column for f in figures}) == 1 and figures[0].column is not None
    assert all(0 <= v <= 1 for f in figures for v in f.rect)


def test_a_writing_programs_own_invisible_credit_is_not_hidden_text(cfg):
    """TCPDF writes "Powered by TCPDF (www.tcpdf.org)" invisibly on every file it
    makes — a genuine e-PAN among them. That is the program naming itself."""
    credit = _drawn(_FIGURE + b"\nBT /F1 1 Tf 3 Tr 3 1 Td (Powered by TCPDF \\(www.tcpdf.org\\)) Tj ET")
    found = _page_found(cfg, credit)["HIDDEN_TEXT"]
    assert found.status == "pass" and "naming itself" in found.finding
    other = _drawn(_FIGURE + b"\nBT /F1 1 Tf 3 Tr 3 1 Td (9,00,000.00) Tj ET")
    assert _page_found(cfg, other)["HIDDEN_TEXT"].status == "warning"


def test_a_configuration_published_before_the_page_checks_does_not_fail_the_file(cfg):
    """A configuration names the checks that run. One published before a page
    check existed leaves that check out; it never fails the file (a missing
    setting once surfaced as the file being "corrupt")."""
    from ingestion.stages.integrity_page import run_integrity_page

    older = cfg.integrity.model_copy(update={"checks": {k: v for k, v in cfg.integrity.checks.items()
                                                        if k != "PDF_COVERED_TEXT"}})
    data = _drawn(_FIGURE + b"\n0 0 0 rg 15 95 90 20 re f")
    whole = run_integrity_page(data, "pdf", run_integrity_file(data, "pdf", older), older, None, set())
    by_code = {f.code: f for f in whole.findings}
    assert by_code["PDF_COVERED_TEXT"].method.get("not_configured") == "true"  # said not run, never passed
    assert by_code["PDF_COVERED_TEXT"].status == "unable_to_determine" and not by_code["PDF_COVERED_TEXT"].evidence
    assert by_code["HIDDEN_TEXT"].status == "pass"  # the configured page checks still ran
    assert whole.recommendation["code"] == "no_notable_issue"  # never a signal


def test_page_checks_that_crash_are_said_so_and_do_not_fail_the_file(cfg, monkeypatch):
    from ingestion.stages import integrity_page

    def boom(*_a, **_k):
        raise RuntimeError("page library")

    monkeypatch.setattr(integrity_page, "read_pages", boom)
    data = _drawn(_FIGURE)
    whole = integrity_page.run_integrity_page(data, "pdf", run_integrity_file(data, "pdf", cfg.integrity),
                                              cfg.integrity, None, set())
    page = [f for f in whole.findings if f.code == "PDF_COVERED_TEXT"]
    assert page and page[0].status == "unable_to_determine" and "RuntimeError" in page[0].finding
    assert any(f.code == "PDF_INCREMENTAL_UPDATE" for f in whole.findings)


# --- the file's two records of itself (information dictionary and XMP) -------------------

def _records(info: dict, xmp: dict):
    from ingestion.integrity.meta import FileMeta

    return FileMeta(info=info, xmp=xmp, has_xmp=True)


def _info_xmp(cfg, meta):
    from ingestion.integrity.checks import _info_xmp as check

    return check(cfg.integrity.model_dump(mode="python"), meta)


def test_a_scanner_ending_its_names_with_a_nul_is_not_a_disagreement(cfg):
    meta = _records({"Producer": "Adobe PSL 1.2e for Canon\x00", "Creator": "Canon MF240 Series\x00"},
                    {"producer": "Adobe PSL 1.2e for Canon", "creator_tool": "Canon MF240 Series"})
    assert _info_xmp(cfg, meta).status == "pass"


def test_a_template_xmp_left_by_a_form_filler_is_listed_not_counted(cfg):
    meta = _records({"Producer": "iText 5.5.6", "CreationDate": "D:20250306111526+05'30'",
                     "ModDate": "D:20250306111526+05'30'"}, {"create_date": "2022-06-29T16:36:09.135"})
    hit = _info_xmp(cfg, meta)
    assert hit.status == "warning" and hit.context and "template" in hit.finding


def test_records_that_disagree_on_the_program_still_count(cfg):
    meta = _records({"Producer": "Microsoft Word", "CreationDate": "D:20250306111526+05'30'"},
                    {"producer": "Adobe Acrobat", "create_date": "2025-03-06T11:15:26+05:30"})
    hit = _info_xmp(cfg, meta)
    assert hit.status == "warning" and not hit.context


def test_an_xmp_naming_a_change_of_its_own_still_counts(cfg):
    meta = _records({"CreationDate": "D:20250306111526+05'30'"},
                    {"create_date": "2022-06-29T16:36:09", "modify_date": "2022-07-01T10:00:00"})
    hit = _info_xmp(cfg, meta)
    assert hit.status == "warning" and not hit.context
