"""A small, defensive .xlsx reader and writer (standard library only).

Used for RBL's reference record workbook (docs/functional-requirements.md F-25.1). The reader
takes cell values only (shared strings, inline strings, numbers and cached formula results)
and refuses anything that looks hostile, always with a WorkbookError naming what is wrong:
DTDs or entities in any encoding, oversized or over-compressed members (the engine/uploads.py
pattern), unreadable members, sheets beyond the row or column limit, too many sheets or one
part read as several sheets, and malformed row or cell references.
"""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from xml.etree import ElementTree
from xml.parsers import expat
from xml.sax.saxutils import escape

MAX_FILE = 5 * 1024 * 1024
MAX_EXPANDED = 50 * 1024 * 1024
RATIO_MEMBER = 1024 * 1024
MAX_RATIO = 100
MAX_ROWS = 2000
MAX_COLUMNS = 256
MAX_SHEETS = 50

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
EPOCH = date(1899, 12, 30)
PERCENT_FORMATS = {9, 10}  # Excel's built-in 0% and 0.00%

Cell = str | float | None


class WorkbookError(ValueError):
    pass


def _ns(tag: str) -> str:
    return f"{{{MAIN}}}{tag}"


def _column(ref: str) -> int:
    letters = re.fullmatch(r"([A-Za-z]{1,3})\d*", ref)
    if not letters:
        raise WorkbookError(f"bad cell reference {ref!r}")
    n = 0
    for ch in letters.group(1).upper():
        n = n * 26 + ord(ch) - 64
    if n > MAX_COLUMNS:
        raise WorkbookError(f"cell {ref} is beyond column {_letters(MAX_COLUMNS - 1)}")
    return n - 1


def _letters(index: int) -> str:
    out = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def _read(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        return archive.read(name)
    except (zipfile.BadZipFile, zlib.error, NotImplementedError, RuntimeError, EOFError, OSError, KeyError) as e:
        raise WorkbookError(f"{name}: cannot be read ({e})") from e


def _parse(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    data = _read(archive, name)
    # A DTD is refused whatever the part's encoding: a UTF-16 part hides the ASCII "<!DOCTYPE".
    scanner = expat.ParserCreate()

    def refuse(*_args: object) -> None:
        raise WorkbookError(f"{name}: document type declarations are not allowed")

    scanner.StartDoctypeDeclHandler = refuse
    scanner.EntityDeclHandler = refuse
    try:
        scanner.Parse(data, True)
        return ElementTree.fromstring(data)
    except (expat.ExpatError, ElementTree.ParseError) as e:
        raise WorkbookError(f"{name}: not well-formed XML ({e})") from e


def _text(element: ElementTree.Element) -> str:
    """A shared or inline string: its <t>, or the <t> of each rich-text run. A phonetic guide
    (<rPh>, a reading typed with an East Asian input method) is not the cell's text."""
    runs = [*element.findall(_ns("t")), *element.findall(f"{_ns('r')}/{_ns('t')}")]
    return "".join(t.text or "" for t in runs)


def serial_date(value: Cell) -> str | None:
    """An Excel date serial (or ISO text) as YYYY-MM-DD; None when it is neither."""
    if isinstance(value, float):
        if not 1 <= value < 2958466:
            return None
        return (EPOCH + timedelta(days=int(value))).isoformat()
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            return None
    return None


def _is_percent(code: str) -> bool:
    """A custom number format that shows a percentage: an unquoted, unescaped %."""
    return "%" in re.sub(r'"[^"]*"|\\.', "", code)


def _percent_styles(styles: ElementTree.Element) -> set[int]:
    custom = {int(f.get("numFmtId", "")): f.get("formatCode", "")
              for f in styles.iter(_ns("numFmt")) if (f.get("numFmtId") or "").isdigit()}
    xfs = styles.find(_ns("cellXfs"))
    found: set[int] = set()
    for i, xf in enumerate(xfs.findall(_ns("xf")) if xfs is not None else []):
        fmt = xf.get("numFmtId", "0")
        if fmt.isdigit() and (int(fmt) in PERCENT_FORMATS or _is_percent(custom.get(int(fmt), ""))):
            found.add(i)
    return found


def read_workbook(data: bytes, date_columns: Mapping[str, Iterable[str]] | None = None) -> dict[str, list[list[Cell]]]:
    """Every sheet's rows, by sheet name. Row i of the list is spreadsheet row i + 1; cells are
    str, float or None. A number shown as a percentage is returned as its text ("33.9%").
    date_columns: per sheet, the header names (row 1) whose serials become ISO dates."""
    if len(data) > MAX_FILE:
        raise WorkbookError(f"the workbook is over {MAX_FILE // (1024 * 1024)} MB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, EOFError) as e:
        raise WorkbookError("not an .xlsx workbook (not a zip file)") from e
    with archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names or "[Content_Types].xml" not in names:
            raise WorkbookError("not an .xlsx workbook (no xl/workbook.xml)")
        expanded = 0
        for info in archive.infolist():
            expanded += info.file_size
            if info.file_size > RATIO_MEMBER and info.file_size > MAX_RATIO * max(info.compress_size, 1):
                raise WorkbookError(f"{info.filename}: compression ratio over {MAX_RATIO}")
        if expanded > MAX_EXPANDED:
            raise WorkbookError(f"the workbook expands to over {MAX_EXPANDED // (1024 * 1024)} MB")
        _parse(archive, "[Content_Types].xml")

        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared = [_text(si) for si in _parse(archive, "xl/sharedStrings.xml").iter(_ns("si"))]
        percent = _percent_styles(_parse(archive, "xl/styles.xml")) if "xl/styles.xml" in names else set()

        targets: dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for rel in _parse(archive, "xl/_rels/workbook.xml.rels").iter(f"{{{PKG_REL}}}Relationship"):
                target = rel.get("Target", "")
                targets[rel.get("Id", "")] = target.lstrip("/") if target.startswith("/") else f"xl/{target}"

        sheets: dict[str, list[list[Cell]]] = {}
        read_parts: set[str] = set()
        entries = list(_parse(archive, "xl/workbook.xml").iter(_ns("sheet")))
        if len(entries) > MAX_SHEETS:
            raise WorkbookError(f"the workbook has more than {MAX_SHEETS} sheets")
        for sheet in entries:
            name = sheet.get("name", "")
            part = targets.get(sheet.get(f"{{{REL}}}id", ""))
            if part is None or part not in names:
                raise WorkbookError(f"sheet {name!r} has no part")
            if part in read_parts:
                raise WorkbookError(f"sheet {name!r} repeats another sheet's part")
            read_parts.add(part)
            sheets[name] = _rows(_parse(archive, part), shared, percent, name)

    for sheet_name, headers in (date_columns or {}).items():
        rows = sheets.get(sheet_name)
        if not rows:
            continue
        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        for col in [i for i, h in enumerate(header) if h in set(headers)]:
            for row in rows[1:]:
                if col < len(row) and isinstance(row[col], float):
                    row[col] = serial_date(row[col]) or row[col]
    return sheets


def _rows(root: ElementTree.Element, shared: list[str], percent: set[int], sheet: str) -> list[list[Cell]]:
    rows: list[list[Cell]] = []
    last = 0
    for count, row in enumerate(root.iter(_ns("row")), start=1):
        ref = row.get("r")
        if ref is not None and not re.fullmatch(r"\d+", ref):
            raise WorkbookError(f"sheet {sheet!r}: bad row number {ref!r}")
        number = int(ref) if ref is not None else last + 1
        if count > MAX_ROWS or number > MAX_ROWS:
            raise WorkbookError(f"sheet {sheet!r} has more than {MAX_ROWS} rows")
        if number <= last:
            raise WorkbookError(f"sheet {sheet!r}: row {number} is out of order")
        last = number
        while len(rows) < number - 1:
            rows.append([])
        cells: list[Cell] = []
        for c in row.iter(_ns("c")):
            cell = c.get("r")
            col = _column(cell) if cell else len(cells)
            if col < len(cells):
                raise WorkbookError(f"sheet {sheet!r}: cell {cell} is out of order")
            while len(cells) < col:
                cells.append(None)
            cells.append(_value(c, shared, percent))
        while cells and cells[-1] in (None, ""):
            cells.pop()
        rows.append(cells)
    return rows


def _value(c: ElementTree.Element, shared: list[str], percent: set[int]) -> Cell:
    kind = c.get("t", "n")
    if kind == "inlineStr":
        inline = c.find(_ns("is"))
        return _text(inline) if inline is not None else None
    v = c.find(_ns("v"))
    if v is None or v.text is None:
        return None
    if kind == "s":
        if not re.fullmatch(r"\d+", v.text.strip()):
            raise WorkbookError(f"cell {c.get('r')}: bad shared string index {v.text!r}")
        index = int(v.text)
        if index >= len(shared):
            raise WorkbookError(f"cell {c.get('r')}: shared string {index} out of range")
        return shared[index]
    if kind in ("str", "b"):
        return v.text
    if kind == "d":
        # An ISO 8601 date cell (some writers use it instead of a serial): its date.
        return v.text.split("T")[0].strip()
    if kind == "e":
        return None
    try:
        number = float(v.text)
    except ValueError:
        return v.text
    style = c.get("s", "")
    if style.isdigit() and int(style) in percent:
        return f"{number * 100:g}%"
    return number


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{sheets}
</Types>"""
_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
# Cell styles: 0 normal, 1 bold (the header row), 2 Text (number format 49), so that Excel keeps
# what is typed in a free-text column ("33.9%", "2.67x") instead of converting it to a number.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>
</styleSheet>"""
TEXT_STYLE = 2


def write_workbook(sheets: Mapping[str, list[list[Cell | int]]],
                   text_columns: Mapping[str, Iterable[int]] | None = None) -> bytes:
    """A workbook of the given sheets; row 1 of each is a bold header. Strings are inline.
    text_columns: per sheet, the column indexes formatted as Text, for values typed later."""
    out = io.BytesIO()
    names = list(sheets)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        overrides = "\n".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(names) + 1)
        )
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES.format(sheets=overrides))
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/styles.xml", _STYLES)
        sheet_entries = "".join(
            f'<sheet name="{escape(n[:31], {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
            for i, n in enumerate(names, start=1)
        )
        archive.writestr("xl/workbook.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>{sheet_entries}</sheets></workbook>'
        ))
        rels = "".join(
            f'<Relationship Id="rId{i}" Type="{REL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(names) + 1)
        )
        styles = len(names) + 1
        rels += f'<Relationship Id="rId{styles}" Type="{REL}/styles" Target="styles.xml"/>'
        archive.writestr("xl/_rels/workbook.xml.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{PKG_REL}">{rels}</Relationships>'
        ))
        for i, name in enumerate(names, start=1):
            text = set((text_columns or {}).get(name, ()))
            archive.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheets[name], text))
    return out.getvalue()


def _sheet_xml(rows: list[list[Cell | int]], text_columns: set[int]) -> str:
    widths: dict[int, int] = {c: 8 for c in text_columns}
    body = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            if value is None or value == "":
                continue
            ref = f"{_letters(c)}{r}"
            style = ' s="1"' if r == 1 else (f' s="{TEXT_STYLE}"' if c in text_columns else "")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"{style}><v>{value!r}</v></c>')
                text = str(value)
            else:
                text = str(value)
                cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{escape(text)}</t></is></c>')
            widths[c] = max(widths.get(c, 8), min(len(text) + 2, 60))
        body.append(f'<row r="{r}">{"".join(cells)}</row>')
    cols = "".join(
        f'<col min="{c + 1}" max="{c + 1}" width="{w}" customWidth="1"'
        f'{f" style={chr(34)}{TEXT_STYLE}{chr(34)}" if c in text_columns else ""}/>'
        for c, w in sorted(widths.items())
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{MAIN}">{f"<cols>{cols}</cols>" if cols else ""}<sheetData>{"".join(body)}</sheetData></worksheet>'
    )
