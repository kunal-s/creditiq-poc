"""An identifier the document-processing service read by undoing a scan's confusion (Story 2.6 of the classification
restructure) arrives held for review, its note saying what was printed and what was read."""

from engine.contracts.ingest import IngestConfidence, IngestDocument, IngestField, IngestSource
from engine.pipeline import _flatten


def test_a_corrected_identifier_is_held_for_review_with_its_note():
    note = 'printed "AAACKI234F", read as AAACK1234F by a check on this document; please confirm'
    doc = IngestDocument(
        instance_no=1, page_from=1, page_to=1, document_type="company_pan", tables={}, validation=[],
        confidence=IngestConfidence(document=0.9, decision="auto_accept"),
        fields={"pan": IngestField(status="found", value="AAACK1234F", raw_text="AAACKI234F", method="identifier",
                                   confidence=0.9, source=IngestSource(kind="page", page=1, text="AAACKI234F"),
                                   key_field=True, needs_review=True, correction=note)})
    [row] = _flatten(doc, {1: (600.0, 800.0)})
    assert (row.value, row.raw, row.status, row.check_note) == ("AAACK1234F", "AAACKI234F", "in_review", note)
