"""Positioned-text PDFs for tests: every cell is placed at its own x, so a table is read from word
positions exactly as from a printed document. Helvetica at 10 points; no dates or ids in the file,
so the bytes are deterministic. All names in the documents the tests build are fictional."""

from __future__ import annotations

from pdfminer.fontmetrics import FONT_METRICS

_WIDTHS = FONT_METRICS["Helvetica"][1]

# A cell is (x, text) or (x, text, "r"); "r" right-aligns the text so it ends at x.
Cell = tuple


def text_width(text: str, size: float) -> float:
    return sum(_WIDTHS.get(ch, 556) for ch in text) * size / 1000


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[list[Cell]]], *, size: float = 10.0, leading: float = 16.0) -> bytes:
    """`pages`: each page a list of rows from the top, each row a list of cells (an empty row is a gap)."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages))) + f"] /Count {len(pages)} >>").encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, rows in enumerate(pages):
        ops, y = [], 800.0
        for row in rows:
            for cell in row:
                x, text = float(cell[0]), str(cell[1])
                if len(cell) > 2 and cell[2] == "r":
                    x -= text_width(text, size)
                ops.append(f"BT /F1 {size:g} Tf {x:.2f} {y:.2f} Td ({_escape(text)}) Tj ET")
            y -= leading
        stream = "\n".join(ops)
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                        f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>").encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream".encode("latin-1"))
    out = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


# --- The documents ---

COMPANY = "Kestrel Fabricators Private Limited"
PAN = "AAACK1234F"
CIN = "U28999MH2015PTC123456"
GSTIN = "27AAACK1234F1Z0"


def facilities_declaration(facilities: list[tuple[str, str, str, str, str]], accounts: list[tuple[str, str, str]]) -> bytes:
    """A declaration of existing facilities: (lender, facility, limit, outstanding, emi) and (bank, number, type)."""
    rows: list[list[Cell]] = [
        [(50, "DECLARATION OF EXISTING CREDIT FACILITIES AND BANK ACCOUNTS")],
        [],
        [(50, "Name of Company"), (200, COMPANY)],
        [(50, "Date of Declaration"), (200, "15 September 2026")],
        [(50, "PAN"), (200, PAN)],
        [(50, "CIN"), (200, CIN)],
        [],
        [(50, "We hereby declare that the company has the following existing credit facilities as on this date:")],
        [],
        [(50, "Name of Lender"), (190, "Nature of Facility"), (390, "Sanctioned Limit", "r"), (470, "Outstanding", "r"), (540, "EMI", "r")],
    ]
    for lender, facility, limit, outstanding, emi in facilities:
        rows.append([(50, lender), (190, facility), (390, limit, "r"), (470, outstanding, "r"), (540, emi, "r")])
    rows += [
        [(50, "Total")],
        [],
        [(50, "We also declare that the company holds the following bank accounts:")],
        [],
        [(50, "Name of Bank"), (200, "Account Number"), (340, "Type of Account")],
    ]
    for bank, number, kind in accounts:
        rows.append([(50, bank), (200, number), (340, kind)])
    rows += [[], [(50, f"For {COMPANY}")], [(50, "Authorised Signatory")]]
    return make_pdf([rows])


def sanction_letter(lender: str, facility: str, amount: str, rate: str, tenure: str, emi: str) -> bytes:
    rows: list[list[Cell]] = [
        [(50, lender.upper())],
        [(50, "SANCTION LETTER")],
        [],
        [(50, "Reference"), (200, "TFL/SL/2024/0457")],
        [(50, "Date of Sanction"), (200, "12 April 2024")],
        [(50, "Borrower"), (200, COMPANY)],
        [(50, "Lender"), (200, lender)],
        [],
        [(50, "We are pleased to sanction the following credit facility on the terms and conditions below.")],
        [],
        [(50, "Facility"), (250, "Sanctioned Amount", "r"), (270, "Rate of Interest"), (390, "Tenure"), (540, "EMI", "r")],
        [(50, facility), (250, amount, "r"), (270, rate), (390, tenure), (540, emi, "r")],
        [],
        [(50, "Terms and conditions")],
        [(50, "1. The facility is secured by hypothecation of the plant and machinery financed.")],
        [],
        [(50, f"For {lender}")],
        [(50, "Authorised Signatory")],
    ]
    return make_pdf([rows])


def bureau_report(facilities: list[tuple[str, str, str, str, str, str]], parties: list[tuple[str, str, str]]) -> bytes:
    """(lender, facility, sanctioned, outstanding, overdue, status) and (name, relationship, pan)."""
    rows: list[list[Cell]] = [
        [(50, "COMMERCIAL CREDIT INFORMATION REPORT")],
        [],
        [(50, "Report Date"), (200, "20 September 2026")],
        [(50, "Company Name"), (200, COMPANY)],
        [(50, "PAN"), (200, PAN)],
        [(50, "CIN"), (200, CIN)],
        [(50, "GSTIN"), (200, GSTIN)],
        [(50, "Credit Rank"), (200, "4")],
        [],
        [(50, "CREDIT FACILITIES")],
        [(50, "Lender"), (190, "Facility"), (330, "Sanctioned", "r"), (410, "Outstanding", "r"), (470, "Overdue", "r"), (490, "Status")],
    ]
    for lender, facility, sanctioned, outstanding, overdue, status in facilities:
        rows.append([(50, lender), (190, facility), (330, sanctioned, "r"), (410, outstanding, "r"), (470, overdue, "r"), (490, status)])
    rows += [[], [(50, "RELATED PARTIES")], [(50, "Name"), (200, "Relationship"), (340, "PAN")]]
    for name, relationship, pan in parties:
        rows.append([(50, name), (200, relationship), (340, pan)])
    rows += [[], [(50, "END OF REPORT")]]
    return make_pdf([rows])
