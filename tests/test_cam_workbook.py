"""The draft CAM as an Excel workbook (F-23.5): a sheet a section, the memo's words and figures, the
figures a person overrode in their cells, the sources each sheet cites, the same file every time, and
the download logged like the Word and PDF files."""

import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi.testclient import TestClient

from engine import db, exports
from engine.contracts import Cam, CamOverride
from engine.exports.xlsx import SHEET_NAME, figure_key, sheet_name
from tests.test_output_exports import _download, _memo, _processed_case

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _book(data: bytes) -> dict[str, dict]:
    """Each sheet by name: its cells' text by reference ("B7"), its merged ranges and its notes."""
    z = zipfile.ZipFile(io.BytesIO(data))
    strings = ["".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t"))
               for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    names = re.findall(r'<sheet name="([^"]+)"', z.read("xl/workbook.xml").decode())
    out = {}
    for i, name in enumerate(names, start=1):
        root = ElementTree.fromstring(z.read(f"xl/worksheets/sheet{i}.xml"))
        cells = {}
        for c in root.iter(f"{{{NS['m']}}}c"):
            v = c.find("m:v", NS)
            assert c.get("t") in (None, "s"), f"{c.get('r')} is not text"  # never a formula
            assert c.find("m:f", NS) is None
            if v is not None and c.get("t") == "s":
                cells[c.get("r")] = strings[int(v.text)]
        notes = {}
        comments = f"xl/comments{i}.xml"
        if comments in z.namelist():
            for comment in ElementTree.fromstring(z.read(comments)).iter(f"{{{NS['m']}}}comment"):
                notes[comment.get("ref")] = "".join(t.text or "" for t in comment.iter(f"{{{NS['m']}}}t"))
        out[name.replace("&amp;", "&")] = {"cells": cells, "notes": notes,
                                            "merged": [m.get("ref") for m in root.iter(f"{{{NS['m']}}}mergeCell")]}
    return out


def _row_of(sheet: dict, text: str) -> int:
    ref = next(r for r, v in sheet["cells"].items() if v == text)
    return int(re.sub(r"[A-Z]", "", ref))


def test_a_sheet_a_section_named_within_excels_limit():
    book = _book(exports.cam_workbook(_memo()))
    assert list(book) == ["1. Proposal at a glance", "2. Financial performance", "3. Banking and account conduct",
                          "4. Summary of findings, deviat…", "5. Recommendation"]
    assert all(len(n) <= SHEET_NAME for n in book)


def test_sheet_names_shorten_and_stay_unique():
    taken: set[str] = set()
    assert sheet_name(2, "Facility Requested and Purpose", taken) == "2. Facility Requested & Purpose"
    assert sheet_name(9, "Notes [draft]: a/b", taken) == "9. Notes draft ab"
    long = "A title far longer than any sheet may carry"
    first, second = sheet_name(1, long, taken), sheet_name(1, long, taken)
    assert first != second and len(first) <= SHEET_NAME and len(second) <= SHEET_NAME


def test_each_sheet_heads_with_the_memo_and_holds_its_section():
    book = _book(exports.cam_workbook(_memo(labels={"bank": "The bank"})))
    glance = book["1. Proposal at a glance"]
    assert glance["cells"]["A1"] == "The bank"
    assert glance["cells"]["A2"] == "Credit Approval Memo · Kestrel Fabricators Pvt Ltd"
    assert "Case ID: BBG-2026-000004" in glance["cells"]["A3"] and "Version 7 (published 29 Sep 2026)" in glance[
        "cells"]["A3"]
    assert glance["cells"]["A4"] == "Interim layout"
    assert "1. Proposal at a glance" in glance["cells"].values()
    # Key facts as Field | Value | Source.
    row = _row_of(glance, "Borrower")
    assert glance["cells"][f"B{row}"] == "Kestrel Fabricators Pvt Ltd" and glance["cells"][f"C{row}"] == "[1\u00a0p.1]"
    # A table keeps its columns; a paragraph is one merged row across the sheet.
    finance = book["2. Financial performance"]
    row = _row_of(finance, "Revenue from operations")
    assert finance["cells"][f"C{row}"] == "INR 45.92 cr [2\u00a0pp.4-5]"
    paragraph = next(r for r, v in finance["cells"].items() if v.startswith("Revenue from operations grew"))
    assert any(m.startswith(paragraph + ":") for m in finance["merged"])
    # A section with nothing on file says so.
    assert "Nothing on file yet." in book["3. Banking and account conduct"]["cells"].values()


def test_each_sheet_lists_the_sources_it_cites():
    book = _book(exports.cam_workbook(_memo()))
    finance = book["2. Financial performance"]
    start = _row_of(finance, "Sources cited in this section")
    listed = [finance["cells"][f"B{r}"] for r in range(start + 2, start + 10) if f"B{r}" in finance["cells"]]
    assert listed == ["Audited financial statements · FY 2025-26", "GSTR-3B · Sep 2025"]


def test_an_overridden_figure_shows_its_new_value_noted_with_the_one_drafted():
    memo = _memo()
    at = "2026-10-19T10:00:00+00:00"
    memo.sections[0].review.overrides = [
        CamOverride(id="OV-1", figure="Amount requested", original="INR 4.00 cr", value="INR 3.50 cr",
                    reason="Revised ask", by="ananya-krishnan", by_name="Ananya Krishnan", at=at)]
    memo.sections[1].review.overrides = [
        CamOverride(id="OV-2", figure=figure_key("Financial performance", "Current ratio", "FY 2025-26 (audited)"),
                    original="1.19x", value="1.21x", reason="Restated", by="ananya-krishnan",
                    by_name="Ananya Krishnan", at=at)]
    book = _book(exports.cam_workbook(memo))
    glance = book["1. Proposal at a glance"]
    row = _row_of(glance, "Amount requested")
    assert glance["cells"][f"B{row}"] == "INR 3.50 cr"
    assert glance["notes"][f"B{row}"] == ("As drafted: INR 4.00 cr\n"
                                          "Overridden by Ananya Krishnan, 19 Oct 2026: Revised ask")
    finance = book["2. Financial performance"]
    row = _row_of(finance, "Current ratio")
    assert finance["cells"][f"C{row}"] == "1.21x [2\u00a0p.3]" and f"C{row}" in finance["notes"]


def test_the_same_memo_gives_the_same_file():
    assert exports.cam_workbook(_memo()) == exports.cam_workbook(_memo())


def test_a_figure_that_reads_as_a_formula_is_written_as_text():
    memo = _memo()
    memo.sections[0].blocks[0].facts[1].value.text = "=HYPERLINK(\"http://x\",\"y\")"
    book = _book(exports.cam_workbook(memo))  # _book refuses any formula cell
    assert "=HYPERLINK(\"http://x\",\"y\")" in book["1. Proposal at a glance"]["cells"].values()


def test_the_logo_heads_every_sheet():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 12), (120, 120, 120)).save(buf, "PNG")
    z = zipfile.ZipFile(io.BytesIO(exports.cam_workbook(_memo(), buf.getvalue())))
    assert len([n for n in z.namelist() if n.startswith("xl/media/")]) >= 1
    assert len([n for n in z.namelist() if re.match(r"xl/drawings/drawing\d+\.xml$", n)]) == 5


def test_the_workbook_downloads_and_the_download_is_logged(client: TestClient, published_data_root: Path):
    analyst, case_id = _processed_case(client, published_data_root)
    memo = Cam.model_validate(client.get(f"/api/cases/{case_id}/cam", headers=analyst).json())
    response = _download(client, analyst, case_id, "cam", "xlsx")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == XLSX
    assert response.headers["content-disposition"] == f'attachment; filename="CAM-draft-{case_id}.xlsx"'
    book = _book(response.content)
    assert len(book) == len(memo.sections) + 2
    conn = db.connect(published_data_root)
    try:
        logged = [json.loads(r["detail"]) for r in conn.execute(
            "SELECT detail FROM decision_log WHERE case_id = ? AND action = 'output.downloaded'", (case_id,))]
    finally:
        conn.close()
    assert {"output": "cam", "format": "xlsx"} in logged
    # The PD note is not a workbook.
    assert _download(client, analyst, case_id, "pd-note", "xlsx").status_code == 422


def test_an_override_made_on_the_screen_is_in_the_downloaded_cell(client: TestClient, published_data_root: Path):
    analyst, case_id = _processed_case(client, published_data_root)
    memo = Cam.model_validate(client.get(f"/api/cases/{case_id}/cam", headers=analyst).json())
    section = next(s for s in memo.sections if any(b.facts for b in s.blocks))
    fact = next(f for b in section.blocks for f in b.facts)
    response = client.post(f"/api/cases/{case_id}/cam/sections/{section.id}/overrides", headers=analyst,
                           json={"figure": fact.label, "original": fact.value.text, "value": "Changed value",
                                 "reason": "Checked against the original"})
    assert response.status_code == 200, response.text
    book = _book(_download(client, analyst, case_id, "cam", "xlsx").content)
    sheet = next(v for k, v in book.items() if k.startswith(f"{section.number}. "))
    row = _row_of(sheet, fact.label)
    assert sheet["cells"][f"B{row}"] == "Changed value" and "Checked against the original" in sheet["notes"][f"B{row}"]

