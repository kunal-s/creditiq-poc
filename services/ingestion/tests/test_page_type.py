"""Story 7.2: one page of a file read as the type a person gave it, and a document read again without that page."""

from ingestion.contracts import FileSpec
from ingestion.pipeline import Ingestor
from ingestion.store import Store

from .conftest import fixture_doc
from ingestion.util import sha256_hex

AFS = "Southgate_Audited_FS_FY2025.pdf"


def read(cfg, **kw):
    data = fixture_doc(AFS)
    spec = FileSpec(file_id="f1", sha256=sha256_hex(data), original_name=AFS, content_type="application/pdf", **kw)
    return Ingestor(cfg, Store(), None, None).process_file("C", spec, data)


def test_one_page_is_read_as_the_type_a_person_gave_it(cfg):
    r = read(cfg, assigned_type="audited_financial_statements", pages=[6])
    assert r.status == "processed"
    (d,) = r.documents
    assert d.document_type == "audited_financial_statements" and (d.page_from, d.page_to) == (6, 6)
    assert [p.page for p in r.pages] == [6]


def test_pages_the_file_does_not_have_are_refused(cfg):
    r = read(cfg, assigned_type="audited_financial_statements", pages=[99])
    assert r.status == "rejected" and r.reject.code == "no_such_pages"


def test_a_file_a_person_gives_a_type_is_split_by_period_like_any_other(cfg):
    """Every page typed as the type the person gave; the returns of two years stay two documents (F-09.5)."""
    data = fixture_doc("Southgate_ITR_FY2024_FY2025.pdf")
    name = "Southgate_ITR_FY2024_FY2025.pdf"
    own = Ingestor(cfg, Store(), None, None).process_file(
        "C", FileSpec(file_id="f1", sha256=sha256_hex(data), original_name=name, content_type="application/pdf"), data)
    given = Ingestor(cfg, Store(), None, None).process_file(
        "C", FileSpec(file_id="f1", sha256=sha256_hex(data), original_name=name, content_type="application/pdf",
                      assigned_type="income_tax_return"), data)
    assert given.classification.tier == "person"
    keys = lambda r: sorted(d.instance_key or "" for d in r.documents if d.document_type == "income_tax_return")
    assert len(keys(given)) == 2 and keys(given) == keys(own)
