"""Bank statement builder (layout L1, grid ledger — reference/05 section C).

Reuses the generic repo's `_ca_story` table layout in spirit (bank header,
info grid, `LongTable` transaction ledger, summary page), but: parameterised
from the descriptor and the ledger this module is handed (never a
module-level singleton); no highlighting of any transaction row (finding 4:
documents must not announce their own defects — irrelevant for Case B, which
has none, and wrong in general); no self-incriminating summary sentence.
"""

from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, LongTable, PageBreak, Paragraph, Spacer, Table, TableStyle

from ..ledger import Transaction
from .common import build_auto, indian_group, styles


def _account_info_table(S, *, bank_name: str, entity_name: str, account_number: str,
                         account_type: str, branch: str, ifsc: str, period: str,
                         office: str, gstin: str) -> Table:
    info = [
        ["Account Name", entity_name, "Account Number", account_number],
        ["Account Type", account_type, "Branch / IFSC", f"{branch} / {ifsc}"],
        ["Statement Period", period, "Currency", "INR"],
        ["Registered Office", office, "GSTIN", gstin],
    ]
    tbl = Table(
        [[Paragraph(a, S["cell_b"]), Paragraph(b, S["cell"]), Paragraph(c, S["cell_b"]), Paragraph(d, S["cell"])]
         for a, b, c, d in info],
        colWidths=[28 * mm, 62 * mm, 26 * mm, 50 * mm],
    )
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9bbfd0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfe1ea")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef5f8")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef5f8")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


def _story(
    S,
    *,
    bank_name: str,
    branch: str,
    entity_name: str,
    account_number: str,
    ifsc: str,
    office: str,
    gstin: str,
    period_label: str,
    opening_date_label: str,
    closing_date_label: str,
    opening: int,
    closing: int,
    txns: list[Transaction],
) -> list:
    st = []
    st.append(Paragraph(bank_name, ParagraphStyle("bank_t", parent=S["title"], fontSize=15,
                                                    textColor=colors.HexColor("#0b4f6c"))))
    st.append(Paragraph(f"{branch} &mdash; Statement of Account", S["subtitle"]))
    st.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#0b4f6c"), spaceBefore=2, spaceAfter=8))

    st.append(_account_info_table(
        S, bank_name=bank_name, entity_name=entity_name, account_number=account_number,
        account_type="Cash Credit Account", branch=branch, ifsc=ifsc, period=period_label,
        office=office, gstin=gstin,
    ))
    st.append(Spacer(1, 8))

    header = [
        Paragraph("Date", S["cell_b"]), Paragraph("Particulars", S["cell_b"]),
        Paragraph("Reference", S["cell_b"]), Paragraph("Debit (INR)", S["cell_rb"]),
        Paragraph("Credit (INR)", S["cell_rb"]), Paragraph("Balance (INR)", S["cell_rb"]),
    ]
    data = [header]
    data.append([
        Paragraph(opening_date_label, S["cell"]), Paragraph("<b>OPENING BALANCE</b>", S["cell"]),
        Paragraph("", S["cell"]), Paragraph("", S["cell_r"]), Paragraph("", S["cell_r"]),
        Paragraph(indian_group(opening), S["cell_rb"]),
    ])
    total_dr = total_cr = 0
    for t in txns:
        total_dr += t.debit
        total_cr += t.credit
        data.append([
            Paragraph(t.txn_date.strftime("%d %b %Y"), S["cell"]),
            Paragraph(t.narration, S["cell"]),
            Paragraph(t.reference, ParagraphStyle("ref", parent=S["cell"], fontSize=7.2,
                                                   textColor=colors.HexColor("#555555"))),
            Paragraph(indian_group(t.debit) if t.debit else "", S["cell_r"]),
            Paragraph(indian_group(t.credit) if t.credit else "", S["cell_r"]),
            Paragraph(indian_group(t.balance), S["cell_r"]),
        ])

    colw = [22 * mm, 62 * mm, 28 * mm, 22 * mm, 22 * mm, 25 * mm]
    tbl = LongTable(data, colWidths=colw, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b4f6c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#999999")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f8fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    st.append(tbl)

    st.append(PageBreak())
    st.append(Paragraph("Statement Summary", S["h1"]))
    st.append(Paragraph(f"Account {account_number} &mdash; {period_label}", S["small"]))
    st.append(Spacer(1, 8))
    summ = [
        [f"Opening Balance ({opening_date_label})", indian_group(opening)],
        ["Total Credits during period", indian_group(total_cr)],
        ["Total Debits during period", indian_group(total_dr)],
        [f"Closing Balance ({closing_date_label})", indian_group(closing)],
        ["Number of transactions", str(len(txns))],
    ]
    sd = [[Paragraph("Particulars", S["cell_b"]), Paragraph("Amount (INR)", S["cell_rb"])]]
    for a, b in summ:
        sd.append([Paragraph(a, S["cell"]), Paragraph(b, S["cell_r"])])
    stb = Table(sd, colWidths=[110 * mm, 45 * mm])
    stb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b4f6c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#999999")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    st.append(stb)
    st.append(Spacer(1, 10))
    st.append(Paragraph("Computer-generated statement.", S["small"]))
    return st


def build_bank_statement(
    outdir: str,
    *,
    file_name: str,
    bank_name: str,
    branch: str,
    entity_name: str,
    account_number: str,
    ifsc: str,
    office: str,
    gstin: str,
    period_label: str,
    opening_date_label: str,
    closing_date_label: str,
    opening: int,
    closing: int,
    txns: list[Transaction],
) -> tuple[str, int]:
    S = styles()
    factory = lambda: _story(
        S, bank_name=bank_name, branch=branch, entity_name=entity_name, account_number=account_number,
        ifsc=ifsc, office=office, gstin=gstin, period_label=period_label,
        opening_date_label=opening_date_label, closing_date_label=closing_date_label,
        opening=opening, closing=closing, txns=txns,
    )
    path = os.path.join(outdir, file_name)
    n = build_auto(path, factory, title="Bank statement", author="")
    return path, n
