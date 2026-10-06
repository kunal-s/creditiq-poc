"""TC-03 (F-05): upload of single files, several files and ZIP archives.
Every file ends in a visible state; archives keep their paths; traversal
and decompression bombs are refused with a reason; the true type comes from
the content; duplicates are linked, not processed. Also F-05.6 page images.
"""

import io
import os
import stat
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, uploads
from tests.conftest import ANALYST, MANAGER, RM, fixture_file, make_case, run_jobs, sign_in, upload
from tests.fixtures.pdfgen import make_pdf

STATES = {"registered", "duplicate", "ignored", "rejected", "exception"}


def _zip(entries: list[tuple[str, bytes]], *, encrypted: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    data = bytearray(buf.getvalue())
    if encrypted:
        # Mark every entry as encrypted (general-purpose flag bit 0) in the
        # local headers and the central directory, as a password-protected
        # archive would; zipfile cannot write real encryption.
        for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            pos = data.find(signature)
            while pos >= 0:
                data[pos + flag_offset] |= 0x1
                pos = data.find(signature, pos + 4)
    return bytes(data)


def _by_path(result: dict) -> dict[str, dict]:
    return {f["archive_path"] or f["original_name"]: f for f in result["files"]}


def test_tc03_zip_with_folders_junk_nested_zip_unsupported_and_duplicate(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Heronbay Polymers Pvt Ltd")
    kyc = fixture_file("Tarun Velankar PAN.pdf")
    inner = _zip([("scan_0412.pdf", fixture_file("scan_0412.pdf"))])
    archive = _zip(
        [
            ("case/KYC/Tarun Velankar PAN.pdf", kyc),
            ("case/Financials/bank statement apr-mar.pdf", fixture_file("bank statement apr-mar.pdf")),
            ("case/.DS_Store", b"\x00\x00\x00\x01Bud1"),
            ("__MACOSX/case/._bank.pdf", b"\x00\x05\x16\x07"),
            ("case/Thumbs.db", b"\xd0\xcf\x11\xe0junk"),
            ("case/statement.numbers", b"\x07\x13 not a document format \x00\x01\x02"),
            ("case/copy/Tarun Velankar PAN.pdf", kyc),
            ("case/inner.zip", inner),
        ]
    )
    response = upload(client, rm, case_id, [("case-file.zip", archive), ("Sunil Karve PAN.pdf",
                                                                      fixture_file("Sunil Karve PAN.pdf"))])
    assert response.status_code == 202, response.text
    result = response.json()
    files = _by_path(result)
    assert {f["status"] for f in result["files"]} <= STATES
    first = files["case-file.zip/case/KYC/Tarun Velankar PAN.pdf"]
    assert first["status"] == "registered" and first["content_type"] == "application/pdf"
    assert first["original_name"] == "Tarun Velankar PAN.pdf"
    assert first["label_hint"] == "case / kyc / tarun velankar pan"
    assert files["case-file.zip/case/.DS_Store"]["status"] == "ignored"
    assert files["case-file.zip/__MACOSX/case/._bank.pdf"]["status"] == "ignored"
    assert files["case-file.zip/case/Thumbs.db"]["status"] == "ignored"
    unsupported = files["case-file.zip/case/statement.numbers"]
    assert unsupported["status"] == "rejected" and "Unsupported" in unsupported["reason"]
    dup = files["case-file.zip/case/copy/Tarun Velankar PAN.pdf"]
    assert dup["status"] == "duplicate" and dup["duplicate_of"] == first["id"]
    nested = files["case-file.zip/case/inner.zip/scan_0412.pdf"]
    assert nested["status"] == "registered"
    assert files["Sunil Karve PAN.pdf"]["status"] == "registered"
    assert result["job_id"]

    assert run_jobs(published_data_root) == 1
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    registered = {f["id"] for f in result["files"] if f["status"] == "registered"}
    assert {d["file_id"] for d in docs} == registered  # duplicates are not processed
    stage = client.get(f"/api/cases/{case_id}", headers=rm).json()["stage"]
    assert stage != "Intake"
    assert stage == client.get(f"/api/cases/{case_id}/progress", headers=rm).json()["stage"]


def test_tc03_same_case_as_multiple_files_identifies_the_duplicate(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Heronbay Polymers Pvt Ltd")
    names = ["bank statement apr-mar.pdf", "Tarun Velankar PAN.pdf", "Sunil Karve PAN.pdf"]
    parts = [(n, fixture_file(n)) for n in names] + [("copy of kyc.pdf", fixture_file("Tarun Velankar PAN.pdf"))]
    result = upload(client, rm, case_id, parts).json()
    statuses = [f["status"] for f in result["files"]]
    assert statuses == ["registered", "registered", "registered", "duplicate"]
    assert result["files"][3]["duplicate_of"] == result["files"][1]["id"]


def test_tc03_zip_slip_is_refused_with_a_reason(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    archive = _zip([
        ("../../evil.pdf", fixture_file("Sunil Karve PAN.pdf")),
        ("/etc/cron.d/evil", b"x"),
        ("ok/scan_0412.pdf", fixture_file("scan_0412.pdf")),
    ])
    files = _by_path(upload(client, rm, case_id, [("bundle.zip", archive)]).json())
    for path in ("bundle.zip/../../evil.pdf", "bundle.zip//etc/cron.d/evil"):
        assert files[path]["status"] == "rejected"
        assert "outside the archive" in files[path]["reason"]
    assert files["bundle.zip/ok/scan_0412.pdf"]["status"] == "registered"
    # Nothing was written outside the case's own directory.
    assert not (published_data_root / "evil.pdf").exists()
    assert not (published_data_root.parent / "evil.pdf").exists()


def test_tc03_decompression_bomb_is_refused(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    bomb = _zip([("zeros.pdf", b"\x00" * (20 * 1024 * 1024)), ("scan_0412.pdf", fixture_file("scan_0412.pdf"))])
    result = upload(client, rm, case_id, [("bomb.zip", bomb)]).json()
    assert len(result["files"]) == 1
    refused = result["files"][0]
    assert refused["status"] == "rejected" and "decompression bomb" in refused["reason"]
    assert result["job_id"] is None


def test_tc03_archive_expanding_beyond_the_limit_is_refused(client, published_data_root, monkeypatch):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    small = uploads.limits()
    small.max_archive = 64 * 1024
    monkeypatch.setattr(uploads, "limits", lambda: small)
    # Each member compresses about 20 times (below the bomb ratio); together
    # they expand beyond the archive limit.
    archive = _zip([(f"part{i}.pdf", os.urandom(1024) * 20) for i in range(5)])
    assert len(archive) < small.max_archive
    refused = upload(client, rm, case_id, [("big.zip", archive)]).json()["files"]
    assert refused[0]["status"] == "rejected" and "beyond" in refused[0]["reason"]


def test_tc03_nesting_deeper_than_configured_is_refused(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    level = _zip([("scan_0412.pdf", fixture_file("scan_0412.pdf"))])
    for i in range(3):
        level = _zip([(f"level{i}.zip", level)])
    files = upload(client, rm, case_id, [("outer.zip", level)]).json()["files"]
    assert len(files) == 1 and files[0]["status"] == "rejected"
    assert "nested more than 3" in files[0]["reason"]


def test_f05_true_type_from_content_and_preflight(client: TestClient, published_data_root: Path):
    from PIL import Image

    rm = sign_in(client, RM)
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, rm, published_data_root)
    png = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(png, format="PNG")
    docx = _zip([("[Content_Types].xml", b"<Types/>"), ("word/document.xml", b"<w:document/>")])
    xlsx = _zip([("[Content_Types].xml", b"<Types/>"), ("xl/workbook.xml", b"<workbook/>")])
    parts = [
        ("really-a-pdf.jpg", fixture_file("scan_0412.pdf")),
        ("photo.bin", png.getvalue()),
        ("letter.docx", docx),
        ("sheet.xlsx", xlsx),
        ("figures.txt", b"month,credits,debits\n2026-01,100,90\n2026-02,120,80\n"),
        ("notes.pdf", b"just some plain words, not a document format\nsecond line\n"),
        ("old.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600),
        ("locked.pdf", make_pdf(["secret"], extra_trailer="/Encrypt 9 0 R ")),
        ("broken.pdf", b"%PDF-1.4\n this is not really a pdf"),
        ("empty.pdf", b""),
        ("locked.zip", _zip([("inside.pdf", fixture_file("scan_0412.pdf"))], encrypted=True)),
    ]
    files = _by_path(upload(client, rm, case_id, parts).json())
    assert files["really-a-pdf.jpg"]["content_type"] == "application/pdf"
    assert files["photo.bin"]["content_type"] == "image/png" and files["photo.bin"]["status"] == "registered"
    assert files["letter.docx"]["content_type"].endswith("wordprocessingml.document")
    assert files["sheet.xlsx"]["content_type"].endswith("spreadsheetml.sheet")
    assert files["figures.txt"]["content_type"] == "text/csv"
    assert files["notes.pdf"]["status"] == "rejected"
    assert files["old.xls"]["status"] == "rejected"
    assert files["locked.pdf"]["status"] == "exception" and "password" in files["locked.pdf"]["reason"]
    assert files["broken.pdf"]["status"] == "exception"
    assert files["empty.pdf"]["status"] == "exception" and "empty" in files["empty.pdf"]["reason"]
    assert files["locked.zip/inside.pdf"]["status"] == "exception"
    # Exceptions go to review as quality items, and onto the query list.
    quality = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
               if i["kind"] == "quality"]
    assert len(quality) == 4
    queries = client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
    assert any("password-protected" in q["text"] for q in queries if q["source_kind"] == "quality")


def test_f05_size_limit_applies_while_streaming(client, published_data_root, monkeypatch):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    small = uploads.limits()
    small.max_file = 1000
    monkeypatch.setattr(uploads, "limits", lambda: small)
    big = fixture_file("kestrel gst returns.pdf")
    assert len(big) > 1000
    files = upload(client, rm, case_id, [("kestrel gst returns.pdf", big)]).json()["files"]
    assert files[0]["status"] == "rejected" and "limit" in files[0]["reason"]


def test_f05_resubmission_is_idempotent(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Kestrel Fabricators Pvt Ltd")
    data = fixture_file("kestrel itr.pdf")
    first = upload(client, rm, case_id, [("kestrel itr.pdf", data)]).json()
    assert run_jobs(published_data_root) == 1
    docs_before = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    again = upload(client, rm, case_id, [("kestrel itr (1).pdf", data)]).json()
    assert again["files"][0]["status"] == "duplicate"
    assert again["files"][0]["duplicate_of"] == first["files"][0]["id"]
    assert again["job_id"] is None
    assert run_jobs(published_data_root) == 0
    assert client.get(f"/api/cases/{case_id}/documents", headers=rm).json() == docs_before


def test_f05_files_stored_by_hash_under_a_private_directory(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    result = upload(client, rm, case_id, [("Sunil Karve PAN.pdf", fixture_file("Sunil Karve PAN.pdf"))]).json()
    sha = result["files"][0]["sha256"]
    files_dir = published_data_root / "cases" / case_id / "files"
    assert [p.name for p in files_dir.iterdir()] == [sha]
    for d in (files_dir, files_dir.parent):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE((files_dir / sha).stat().st_mode) == 0o600
    conn = db.connect(published_data_root)
    try:
        actions = [r["action"] for r in conn.execute("SELECT action FROM decision_log WHERE case_id = ?", (case_id,))]
    finally:
        conn.close()
    assert "files.uploaded" in actions


def test_f05_page_images(client: TestClient, published_data_root: Path):
    from PIL import Image

    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Heronbay Polymers Pvt Ltd")
    upload(client, rm, case_id, [("heronbay gst returns.pdf", fixture_file("heronbay gst returns.pdf"))])
    run_jobs(published_data_root)
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    third = next(d for d in docs if d["page_from"] == 3)
    response = client.get(f"/api/cases/{case_id}/documents/{third['id']}/pages/3", headers=rm)
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    image = Image.open(io.BytesIO(response.content))
    assert image.size[0] < image.size[1]  # A4 portrait, the page's own coordinate space
    cached = list((published_data_root / "cases" / case_id / "pages").iterdir())
    assert len(cached) == 1
    assert client.get(f"/api/cases/{case_id}/documents/{third['id']}/pages/99", headers=rm).status_code == 404
    assert client.get(f"/api/cases/{case_id}/documents/nope/pages/1", headers=rm).status_code == 404


@pytest.mark.parametrize("who,expected", [(None, 401), (MANAGER, 403)])
def test_f05_upload_permissions(client: TestClient, published_data_root: Path, who, expected):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    headers = sign_in(client, who) if who else {}
    assert upload(client, headers, case_id, [("a.pdf", b"%PDF-1.4")]).status_code == expected


def test_f05_rm_cannot_upload_to_another_rms_case(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    rm = sign_in(client, RM)
    assert upload(client, rm, case_id, [("a.pdf", b"%PDF-1.4")]).status_code == 404
