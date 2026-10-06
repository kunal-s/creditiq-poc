from ingestion.pipeline import Ingestor
from ingestion.store import Store

from .conftest import fixture_doc, spec

FS = "Southgate_Audited_FS_FY2025.pdf"


def test_identity_is_read_for_party_attribution(results):
    kyc = results["Southgate_Director_KYC_Iyer_x2.pdf"].documents
    assert kyc[0].identity == {"name": "Lakshmi Iyer", "pan": "AXXXX1683M", "din": "07421683", "dob": "1979-07-12"}
    assert results["Southgate_Entity_PAN.pdf"].documents[0].identity == {"name": "Southgate Textiles Private Limited", "pan": "AAHCS6612M"}
    assert results["Southgate_GSTR3B_Dec2025_Jul2026.pdf"].documents[0].identity["gstin"] == "33AAHCS6612M1ZQ"


def test_an_unsigned_draft_carries_the_defect(results):
    d = results["Southgate_Board_Resolution_draft.pdf"].documents[0]
    assert [x.code for x in d.defects] == ["unsigned"] and d.defects[0].pages == [1]
    assert results["Southgate_Entity_PAN.pdf"].documents[0].defects == []


def test_key_fields_below_threshold_are_flagged_for_review(results):
    d = results["Southgate_GSTR3B_Dec2025_Jul2026.pdf"].documents[0]
    assert d.fields["gstin"].needs_review and not d.fields["legal_name"].needs_review


def test_a_persons_assignment_skips_classification(cfg):
    b = fixture_doc("Southgate_Provisional_FY2026.pdf")
    s = spec("p.pdf", b).model_copy(update={"assigned_type": "audited_financial_statements"})
    r = Ingestor(cfg, Store(), None, None).process_file("C", s, b)
    assert r.classification.tier == "person" and r.classification.type == "audited_financial_statements" and r.classification.confidence == 1.0
    assert len(r.documents) == 1 and r.documents[0].document_type == "audited_financial_statements"


def test_an_assignment_to_an_unknown_type_is_refused(cfg):
    b = fixture_doc(FS)
    r = Ingestor(cfg, Store(), None, None).process_file("C", spec("p.pdf", b).model_copy(update={"assigned_type": "nope"}), b)
    assert r.status == "rejected" and r.reject.code == "bad_assignment"
