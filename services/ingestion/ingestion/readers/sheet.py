"""Spreadsheets read cell by cell (FRD F-07.1). A sheet is a page; a cell is a word."""

from __future__ import annotations

import csv
import datetime as dt
import io

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from ..pageindex import Word

COL_W, ROW_H = 100.0, 20.0


class SheetError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dt.datetime, dt.date)):
        return (v.date() if isinstance(v, dt.datetime) else v).isoformat()
    return str(v).strip()


CELL_W = COL_W * 0.5  # a cell's text occupies the left half of its column slot, so cells never touch


def _words(rows: list[list]) -> list[list[Word]]:
    """One Word per token, all tokens of a cell inside the cell's box and tagged with its address."""
    out: list[list[Word]] = []
    for r, row in enumerate(rows):
        ws = []
        for c, v in enumerate(row):
            t = _fmt(v)
            toks = t.split()
            if not toks:
                continue
            total = sum(len(x) for x in toks) + len(toks) - 1
            pos, addr = 0, f"{get_column_letter(c + 1)}{r + 1}"
            for tok in toks:
                a = c * COL_W + CELL_W * pos / total
                b = c * COL_W + CELL_W * (pos + len(tok)) / total
                ws.append(Word(tok, a, r * ROW_H, b, r * ROW_H + ROW_H * 0.5, 1.0, addr))
                pos += len(tok) + 1
        out.append(ws)
    return out


def read_xlsx(data: bytes, max_cells: int) -> list[tuple[str, list[list[Word]]]]:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:
        raise SheetError("corrupt", str(e)) from e
    sheets, cells = [], 0
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        cells += sum(len(r) for r in rows)
        if cells > max_cells:
            raise SheetError("too_large", f"more than {max_cells} cells")
        sheets.append((ws.title, _words(rows)))
    wb.close()
    return sheets


def decode_csv(data: bytes) -> str | None:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def read_csv(data: bytes, max_cells: int) -> list[tuple[str, list[list[Word]]]]:
    text = decode_csv(data)
    if text is None:
        raise SheetError("corrupt", "not readable text")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect)]
    if sum(len(r) for r in rows) > max_cells:
        raise SheetError("too_large", f"more than {max_cells} cells")
    return [("csv", _words(rows))]
