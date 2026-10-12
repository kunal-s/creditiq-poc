"""The workbook reader and writer behind the reference record (FRD F-25.1)."""

import io
import zipfile
from pathlib import Path

import pytest

from engine import reference, xlsx

MAIN = xlsx.MAIN


def _with_part(name: str, content: str | bytes, base: bytes | None = None, compress=zipfile.ZIP_DEFLATED) -> bytes:
    """A copy of a workbook with one part replaced or added."""
    base = base or xlsx.write_workbook({"Sheet": [["a"]]})
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as src, zipfile.ZipFile(out, "w", compress) as dst:
        for item in src.infolist():
            if item.filename != name:
                dst.writestr(item.filename, src.read(item.filename))
        dst.writestr(name, content)
    return out.getvalue()


def test_round_trip_keeps_strings_numbers_and_blanks():
    data = xlsx.write_workbook({"One": [["Name", "Value"], ["alpha & <beta>", 2.5], [None, 65000000]],
                                "Two": [["x"]]})
    sheets = xlsx.read_workbook(data)
    assert list(sheets) == ["One", "Two"]
    assert sheets["One"] == [["Name", "Value"], ["alpha & <beta>", 2.5], [None, 65000000.0]]


def test_shared_inline_and_formula_cells_and_date_serials():
    sheet = f"""<?xml version="1.0"?><worksheet xmlns="{MAIN}"><sheetData>
      <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="inlineStr"><is><t>Note</t></is></c></row>
      <row r="3"><c r="A3" t="s"><v>2</v></c><c r="B3"><v>45200</v></c><c r="C3"><f>1+1</f><v>2</v></c>
        <c r="E3" t="str"><f>"a"&amp;"b"</f><v>ab</v></c></row>
    </sheetData></worksheet>"""
    strings = f"""<?xml version="1.0"?><sst xmlns="{MAIN}"><si><t>Field</t></si><si><t>Date</t></si>
      <si><r><t>rich </t></r><r><t>text</t></r></si></sst>"""
    base = xlsx.write_workbook({"Sheet": [["placeholder"]]})
    data = _with_part("xl/worksheets/sheet1.xml", sheet, base)
    data = _with_part("xl/sharedStrings.xml", strings, data)
    rows = xlsx.read_workbook(data, {"Sheet": ["Date"]})["Sheet"]
    assert rows[0] == ["Field", "Date", "Note"]
    assert rows[1] == []
    assert rows[2] == ["rich text", "2023-10-01", 2.0, None, "ab"]
    assert xlsx.serial_date(45200.0) == "2023-10-01" and xlsx.serial_date("2026-09-30") == "2026-09-30"
    assert xlsx.serial_date("30/09/2026") is None


def test_a_phonetic_guide_is_not_part_of_the_text():
    sheet = (f'<worksheet xmlns="{MAIN}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c>'
             '<c r="B1" t="inlineStr"><is><t>Zonal</t><rPh sb="0" eb="5"><t>ZO</t></rPh></is></c></row>'
             '</sheetData></worksheet>')
    strings = (f'<sst xmlns="{MAIN}"><si><r><t>Head </t></r><r><t>Office</t></r>'
               '<rPh sb="0" eb="4"><t>HEDDO</t></rPh><phoneticPr fontId="0"/></si></sst>')
    data = _with_part("xl/sharedStrings.xml", strings, _with_part("xl/worksheets/sheet1.xml", sheet))
    assert xlsx.read_workbook(data)["Sheet"] == [["Head Office", "Zonal"]]


def test_an_iso_date_cell_reads_as_its_date():
    sheet = (f'<worksheet xmlns="{MAIN}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Date</t></is></c></row>'
             '<row r="2"><c r="A2" t="d"><v>2026-10-02T00:00:00</v></c></row></sheetData></worksheet>')
    rows = xlsx.read_workbook(_with_part("xl/worksheets/sheet1.xml", sheet), {"Sheet": ["Date"]})["Sheet"]
    assert rows[1] == ["2026-10-02"] and xlsx.serial_date(rows[1][0]) == "2026-10-02"


def _sheet(rows_xml: str) -> bytes:
    return _with_part("xl/worksheets/sheet1.xml",
                      f'<worksheet xmlns="{MAIN}"><sheetData>{rows_xml}</sheetData></worksheet>')


def _corrupt(data: bytes, member: str) -> bytes:
    """Flip a byte inside one member's compressed data (its local header and directory intact)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        info = z.getinfo(member)
    out = bytearray(data)
    start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    out[start + 2] ^= 0xFF
    return bytes(out)


def _encrypted(data: bytes) -> bytes:
    """Set the encrypted flag on every member."""
    out = bytearray(data)
    for marker in (b"PK\x03\x04", b"PK\x01\x02"):
        offset = 0
        while (i := out.find(marker, offset)) != -1:
            flag = i + (6 if marker == b"PK\x03\x04" else 8)
            out[flag] |= 0x01
            offset = i + 4
    return bytes(out)


def _repeated_sheets() -> bytes:
    base = xlsx.write_workbook({"One": [["a"]]})
    workbook = (f'<?xml version="1.0"?><workbook xmlns="{MAIN}" xmlns:r="{xlsx.REL}"><sheets>'
                '<sheet name="One" sheetId="1" r:id="rId1"/><sheet name="Two" sheetId="2" r:id="rId1"/>'
                '</sheets></workbook>')
    return _with_part("xl/workbook.xml", workbook, base)


def _many_sheets() -> bytes:
    return xlsx.write_workbook({f"S{i}": [["a"]] for i in range(xlsx.MAX_SHEETS + 1)})


def _expanded() -> bytes:
    data = xlsx.write_workbook({"Sheet": [["a"]]})
    for i in range(51):
        data = _with_part(f"xl/media/blank{i}.bin", b"\0" * (1024 * 1024), data)
    return data


@pytest.mark.parametrize("data,message", [
    ("not_zip", "not a zip file"),
    ("no_workbook", "no xl/workbook.xml"),
    ("doctype", "document type declarations"),
    ("doctype_utf16", "document type declarations"),
    ("ratio", "compression ratio"),
    ("rows", "more than 2000 rows"),
    ("big", "over 5 MB"),
    ("expanded", "expands to over 50 MB"),
    ("far_column", "bad cell reference"),
    ("past_column_limit", "beyond column"),
    ("row_not_a_number", "bad row number"),
    ("row_zero", "out of order"),
    ("row_overwrites", "out of order"),
    ("cell_out_of_order", "out of order"),
    ("shared_index_not_integer", "bad shared string index"),
    ("corrupt_member", "cannot be read"),
    ("encrypted_member", "cannot be read"),
    ("repeated_part", "repeats another sheet's part"),
    ("too_many_sheets", "more than 50 sheets"),
])
def test_hostile_workbooks_are_refused(data, message):
    if data == "not_zip":
        data = b"not a zip at all"
    elif data == "doctype_utf16":
        data = _with_part("xl/sharedStrings.xml",
                          ('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE sst [<!ENTITY e "x">]>'
                           f'<sst xmlns="{MAIN}"><si><t>&e;</t></si></sst>').encode("utf-16"))
    elif data == "expanded":
        data = _expanded()
    elif data == "far_column":
        data = _sheet('<row r="1"><c r="AAAAAAA1"><v>1</v></c></row>')
    elif data == "past_column_limit":
        data = _sheet('<row r="1"><c r="IW1"><v>1</v></c></row>')
    elif data == "row_not_a_number":
        data = _sheet('<row r="abc"><c r="A1"><v>1</v></c></row>')
    elif data == "row_zero":
        data = _sheet('<row r="0"><c r="A1"><v>1</v></c></row>')
    elif data == "row_overwrites":
        data = _sheet('<row r="1"><c r="A1"><v>1</v></c></row><row r="2"><c r="A2"><v>2</v></c></row>'
                      '<row r="1"><c r="A1"><v>3</v></c></row>')
    elif data == "cell_out_of_order":
        data = _sheet('<row r="1"><c r="C1"><v>1</v></c><c r="A1"><v>2</v></c></row>')
    elif data == "shared_index_not_integer":
        data = _sheet('<row r="1"><c r="A1" t="s"><v>1.5</v></c></row>')
    elif data == "corrupt_member":
        data = _corrupt(xlsx.write_workbook({"Sheet": [["a" * 400]]}), "xl/worksheets/sheet1.xml")
    elif data == "encrypted_member":
        data = _encrypted(xlsx.write_workbook({"Sheet": [["a"]]}))
    elif data == "repeated_part":
        data = _repeated_sheets()
    elif data == "too_many_sheets":
        data = _many_sheets()
    elif data == "big":
        data = b"PK" + b"\0" * (5 * 1024 * 1024)
    elif data == "no_workbook":
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
        data = out.getvalue()
    elif data == "doctype":
        data = _with_part("xl/sharedStrings.xml", '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><sst/>')
    elif data == "ratio":
        data = _with_part("xl/media/blank.bin", b"\0" * (3 * 1024 * 1024))
    elif data == "rows":
        rows = "".join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c></row>' for i in range(1, 2002))
        data = _with_part("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{MAIN}"><sheetData>{rows}</sheetData></worksheet>')
    with pytest.raises(xlsx.WorkbookError, match=message):
        xlsx.read_workbook(data)


def test_template_round_trip(published_data_root: Path):
    from engine.configstore import reader

    sheets = xlsx.read_workbook(reference.template(published_data_root))
    assert list(sheets) == [reference.CASE, reference.DEVIATIONS, reference.AUTHORITY, reference.LISTS,
                            *reference.OTHER_SHEETS]
    assert sheets[reference.DEVIATIONS][0] == reference.DEVIATION_COLUMNS
    assert sheets[reference.AUTHORITY][0] == reference.AUTHORITY_COLUMNS
    lists = sheets[reference.LISTS]
    norm_ids = {r[0] for r in lists[1:] if r and r[0]}
    assert norm_ids == {n.id for n in reader.load_policy(published_data_root).norms}
    authorities = {r[7] for r in lists[1:] if len(r) > 7 and r[7]}
    assert authorities == {a.key for a in reader.load_approval_matrix(published_data_root).authorities} | {"not_in_matrix"}
    case = {r[0]: r[1] if len(r) > 1 else None for r in sheets[reference.CASE][1:]}
    assert case["Template version"] == reader.published_version(published_data_root)["version"]


def test_a_number_shown_as_a_percentage_reads_as_typed():
    styles = (f'<?xml version="1.0"?><styleSheet xmlns="{MAIN}">'
              '<numFmts count="1"><numFmt numFmtId="164" formatCode="0.0&quot;%&quot;;0.0%"/></numFmts>'
              '<cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="0"/><xf numFmtId="9"/><xf numFmtId="164"/></cellXfs>'
              '</styleSheet>')
    data = _with_part("xl/styles.xml", styles, _sheet(
        '<row r="1"><c r="A1" s="2"><v>0.339</v></c><c r="B1" s="3"><v>0.5</v></c><c r="C1"><v>0.339</v></c></row>'))
    assert xlsx.read_workbook(data)["Sheet"][0] == ["33.9%", "50%", 0.339]


def test_text_columns_are_formatted_as_text():
    data = xlsx.write_workbook({"Sheet": [["Value", "Date"]]}, text_columns={"Sheet": [0]})
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert '<col min="1" max="1" width="8" customWidth="1" style="2"/>' in sheet
    assert '<col min="2" max="2"' in sheet and sheet.count('style="2"') == 1
