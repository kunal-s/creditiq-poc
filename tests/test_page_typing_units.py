"""A file the document-processing service typed page by page (Story 3.9 of the classification restructure): a page may
belong to two documents, and pages no type placed arrive as an unclassified document with their best guesses."""

from engine.contracts.ingest import IngestFileResult
from engine.pipeline import units_of


def _doc(t, pages):
    return {"instance_no": 1, "page_from": pages[0], "page_to": pages[-1], "document_type": t, "fields": {}, "tables": {},
            "validation": [], "confidence": {"document": 0.9, "decision": "auto_accept"}, "pages": pages,
            "classification": {"type": t, "confidence": 0.9, "tier": "signals", "needs_review": False,
                               "candidates": [{"type": t, "score": 0.9}]}}


def test_a_shared_page_belongs_to_both_documents_and_unplaced_pages_go_to_a_person():
    fr = IngestFileResult.model_validate({
        "file_id": "f", "sha256": "a" * 64, "name": "bundle.pdf", "status": "processed",
        "pages": [{"page": n, "source": "text_layer", "grade": "A", "reading_trust": 1.0} for n in (1, 2, 3, 4)],
        "classification": {"type": "sanction_letter", "confidence": 0.9, "tier": "signals", "needs_review": False},
        "documents": [_doc("sanction_letter", [1, 2]), _doc("commercial_bureau_report", [2, 3])],
        "unplaced": [{"pages": [4], "candidates": [{"type": "stock_statement", "score": 0.33}]}],
    })
    units = units_of(fr)
    assert [(u.classification.types, [p.n for p in u.pages]) for u in units] == [
        (["sanction_letter"], [1, 2]), (["commercial_bureau_report"], [2, 3]), ([], [4])]
    last = units[-1].classification
    assert [c.type_id for c in last.candidates] == ["stock_statement"] and last.why_unclassified == "signals_weak"


def test_a_documents_period_travels_with_it():
    d = _doc("gstr_3b", [1])
    d.update(period={"start": "2025-12-01", "end": "2025-12-31", "kind": "month", "text": "Return Period 12/2025"},
             period_status="found", period_source={"source": "body", "page": 1, "note": None}, instance_key="Dec 2025")
    fr = IngestFileResult.model_validate({
        "file_id": "f", "sha256": "b" * 64, "name": "gst.pdf", "status": "processed",
        "pages": [{"page": 1, "source": "text_layer", "grade": "A", "reading_trust": 1.0}], "documents": [d]})
    [u] = units_of(fr)
    assert u.instance_key == "Dec 2025" and u.period["status"] == "found" and u.period["range"]["end"] == "2025-12-31"
