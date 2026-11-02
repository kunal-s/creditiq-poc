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
    produced = {f.code for f in run_integrity_file(_pdf(), "pdf", cfg.integrity).findings}
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
