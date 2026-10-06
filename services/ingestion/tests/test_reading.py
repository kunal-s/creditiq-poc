import io

from ingestion.stages.quality import run_gate
from ingestion.stages.read import document_grade, read_document

from .conftest import IN_SCOPE, OUT_OF_SCOPE, fixture_doc


def test_every_sample_is_accepted_and_grade_a(cfg):
    pages = 0
    for n in [*IN_SCOPE, *OUT_OF_SCOPE]:
        g = run_gate(fixture_doc(n), n, "application/pdf", cfg.quality, cfg.routing)
        assert g.status == "accepted" and g.kind == "pdf", n
        ps = read_document(fixture_doc(n), "pdf", cfg.quality, cfg.routing, None)
        assert document_grade(ps) == "A" and all(p.source == "text_layer" for p in ps), n
        pages += len(ps)
    assert pages == 63  # the manifest's total


def test_rotated_watermark_is_not_page_content(cfg):
    n = "Southgate_Certificate_of_Incorporation.pdf"
    text = read_document(fixture_doc(n), "pdf", cfg.quality, cfg.routing, None)[0].text()
    assert "SPECIMEN" not in text.upper().replace("SPECIMEN CREATED", "")
    assert "CERTIFICATE OF INCORPORATION" in text and "ME\nNT" not in text
    off = cfg.model_copy(deep=True)
    off.routing.reading.drop_rotated_text = False
    noisy = read_document(fixture_doc(n), "pdf", off.quality, off.routing, None)[0]
    assert len(noisy.words) > len(read_document(fixture_doc(n), "pdf", cfg.quality, cfg.routing, None)[0].words)


def test_footer_is_boilerplate_not_content(cfg):
    p = read_document(fixture_doc("Southgate_Entity_PAN.pdf"), "pdf", cfg.quality, cfg.routing, None)[0]
    assert any(l.boilerplate and "Page 1 of 1" in l.text for l in p.lines)
    assert "Page 1 of 1" not in p.text()


def test_gate_rejections_have_reasons_and_rescan_text(cfg):
    q, r = cfg.quality, cfg.routing
    pdf = fixture_doc("Southgate_Entity_PAN.pdf")
    cases = {
        "empty": run_gate(b"", "a.pdf", "application/pdf", q, r),
        "unsupported": run_gate(b"hello \x00 world", "a.bin", "application/octet-stream", q, r),
        "legacy_xls": run_gate(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 50, "a.xls", "application/vnd.ms-excel", q, r),
        "corrupt": run_gate(pdf[: len(pdf) // 3], "a.pdf", "application/pdf", q, r),
    }
    for code, g in cases.items():
        assert g.status == "rejected" and g.reason == code, (code, g)
        assert g.rescan_request


def test_size_and_page_limits_come_from_config(cfg):
    small = cfg.model_copy(deep=True)
    small.quality.max_file_bytes = 100
    assert run_gate(fixture_doc("Southgate_Entity_PAN.pdf"), "a.pdf", "application/pdf", small.quality, small.routing).reason == "too_large"
    few = cfg.model_copy(deep=True)
    few.quality.max_pages = 2
    assert run_gate(fixture_doc("Southgate_MOA_AOA.pdf"), "a.pdf", "application/pdf", few.quality, few.routing).reason == "too_many_pages"


def test_a_corrupt_file_flows_through_as_rejected_not_crashed(ingestor):
    from .conftest import spec
    b = fixture_doc("Southgate_Entity_PAN.pdf")[:500]
    r = ingestor.process_file("C", spec("x.pdf", b), b)
    assert r.status == "rejected" and r.reject.code == "corrupt" and r.decision == "reject"


def test_sha_mismatch_is_refused(ingestor):
    from .conftest import spec
    b = fixture_doc("Southgate_Entity_PAN.pdf")
    s = spec("x.pdf", b).model_copy(update={"sha256": "0" * 64})
    r = ingestor.process_file("C", s, b)
    assert r.status == "rejected" and r.reject.code == "sha_mismatch"
