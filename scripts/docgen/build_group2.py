"""
Priority group two: the remaining defective documents.
  4. Stock & Book-Debt statement as at 30 June 2026 (stale)
  5. GSTR-3B set Dec 2025 - Jul 2026 (four-month gap: Aug-Nov 2025 absent)
  6. Provisional FY2026 with page numbering 1,2,6,7 (balance sheet pages absent)
  7. Board resolution draft on plain paper with an empty signature block
"""
import os

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable,
)

from common import build_document, build_auto, styles, letterhead, indian_group, ENTITY
import financials as F


def _money_table(rows, colw, S, total_rows=None, header=None):
    data = []
    if header:
        data.append([Paragraph(h, S["cell_rb"] if i else S["cell_b"])
                     for i, h in enumerate(header)])
    for r in rows:
        cells = [Paragraph(r[0], S["cell"])]
        for v in r[1:]:
            cells.append(Paragraph(v, S["cell_r"]))
        data.append(cells)
    t = Table(data, colWidths=colw)
    stl = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#888888")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        stl += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20406a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    for r in (total_rows or []):
        stl.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#eef2f7")))
        stl.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))
    t.setStyle(TableStyle(stl))
    return t


# --------------------------------------------------------------------------- #
# 4. Stock and Book-Debt statement as at 30 June 2026
# --------------------------------------------------------------------------- #
def build_stock_bookdebt(outdir):
    S = styles()

    def story():
        st = letterhead(S, tagline=False)
        st.append(Paragraph("STOCK AND BOOK-DEBT STATEMENT",
                            ParagraphStyle("sb_t", parent=S["h1"], alignment=TA_CENTER)))
        # Prominent "as at" so the 52-day staleness is visible on screen.
        st.append(Paragraph("AS AT 30 JUNE 2026",
                            ParagraphStyle("sb_asat", parent=S["h1"], alignment=TA_CENTER,
                                           fontSize=14, textColor=colors.HexColor("#8a1c1c"),
                                           spaceBefore=0, spaceAfter=2)))
        st.append(HRFlowable(width="60%", thickness=0.8, color=colors.HexColor("#8a1c1c"),
                             spaceBefore=2, spaceAfter=8))
        st.append(Paragraph(
            "To,<br/>The Branch Manager, Continental Commercial Bank, Coimbatore SME Branch.<br/>"
            "Statement submitted in respect of Cash Credit facility against hypothecation of "
            "stock and book debts, for the position <b>as at 30 June 2026</b>.", S["body_l"]))
        st.append(Spacer(1, 6))

        # -- Stock --
        st.append(Paragraph("A. Value of Stock (at cost or market value, whichever is lower)",
                            S["h2"]))
        rm, wip, fg = 18642300, 7180850, 18069000
        assert rm + wip + fg == F.STOCK_30JUN2026
        stock_rows = [
            ["Raw material (yarn, grey fabric, dyes and chemicals)", indian_group(rm)],
            ["Work in progress (weaving, dyeing and processing)", indian_group(wip)],
            ["Finished goods (made-ups, furnishing fabrics, packed)", indian_group(fg)],
            ["Total closing stock", indian_group(F.STOCK_30JUN2026)],
        ]
        st.append(_money_table(stock_rows, [120 * mm, 40 * mm], S, total_rows=[3],
                               header=["Particulars", "Amount (INR)"]))
        st.append(Spacer(1, 8))

        # -- Book debts / ageing --
        st.append(Paragraph("B. Book Debts (Sundry Debtors) with ageing", S["h2"]))
        over90 = F.BOOKDEBT_OVER90
        upto90 = F.BOOKDEBT_30JUN2026 - over90
        b0_30, b31_60, b61_90 = 16056600, 6942080, 4066000
        assert b0_30 + b31_60 + b61_90 == upto90
        bd_rows = [
            ["0 - 30 days", indian_group(b0_30)],
            ["31 - 60 days", indian_group(b31_60)],
            ["61 - 90 days", indian_group(b61_90)],
            ["Sub-total (within 90 days) &mdash; eligible", indian_group(upto90)],
            ["Over 90 days &mdash; not eligible for drawing power", indian_group(over90)],
            ["Total book debts", indian_group(F.BOOKDEBT_30JUN2026)],
        ]
        st.append(_money_table(bd_rows, [120 * mm, 40 * mm], S, total_rows=[3, 5],
                               header=["Ageing bucket", "Amount (INR)"]))
        st.append(Spacer(1, 8))

        # -- Drawing power computation --
        st.append(Paragraph("C. Drawing Power Computation", S["h2"]))
        stock_margin = round(F.STOCK_30JUN2026 * 0.25)
        stock_dp = F.STOCK_30JUN2026 - stock_margin
        bd_margin = round(upto90 * 0.40)
        bd_dp = upto90 - bd_margin
        creditors = 14500000
        dp = stock_dp + bd_dp - creditors
        dp_rows = [
            ["Value of paid stock", indian_group(F.STOCK_30JUN2026)],
            ["Less: margin at 25%", indian_group(stock_margin)],
            ["Advance value of stock", indian_group(stock_dp)],
            ["Eligible book debts (within 90 days)", indian_group(upto90)],
            ["Less: margin at 40%", indian_group(bd_margin)],
            ["Advance value of book debts", indian_group(bd_dp)],
            ["Less: sundry creditors for purchases", indian_group(creditors)],
            ["Drawing Power", indian_group(dp)],
        ]
        st.append(_money_table(dp_rows, [120 * mm, 40 * mm], S, total_rows=[2, 5, 7],
                               header=["Particulars", "Amount (INR)"]))
        st.append(Spacer(1, 6))
        st.append(Paragraph(
            "Note: Sanctioned Cash Credit limit applied for is Rs. 2,85,00,000. Drawing power "
            "shall be restricted to the lower of the computed drawing power and the sanctioned "
            "limit. Stock is fully paid for and is not subject to any prior charge.", S["small"]))

        st.append(Spacer(1, 18))
        st.append(Paragraph("Certified that the above particulars are true and correct and "
                            "reflect the position of stock and book debts as at 30 June 2026.",
                            S["body_l"]))
        st.append(Spacer(1, 20))
        st.append(Paragraph("For Southgate Textiles Private Limited", S["body_l"]))
        st.append(Spacer(1, 22))
        st.append(Paragraph("_____________________________<br/><b>Lakshmi Iyer</b><br/>"
                            "Managing Director (DIN 07421683)", S["body_l"]))
        st.append(Spacer(1, 4))
        st.append(Paragraph("Place: Coimbatore &nbsp;&nbsp;|&nbsp;&nbsp; "
                            "Date of signing: <b>04 July 2026</b>", S["small"]))
        return st

    path = os.path.join(outdir, "Southgate_Stock_BookDebt_30Jun2026.pdf")
    return path, build_auto(path, story, title="Stock and Book-Debt Statement (Specimen)")


# --------------------------------------------------------------------------- #
# 5. GSTR-3B set:  Dec 2025 - Jul 2026 only (Aug-Nov 2025 genuinely absent)
# --------------------------------------------------------------------------- #
def build_gstr3b(outdir):
    S = styles()

    # Eight enclosed periods and their outward taxable supplies (5% GST slab for
    # textiles). The eight monthly outward supplies sum to a figure consistent
    # with the part-year revenue scale.
    periods = [
        ("December 2025", "12/2025", 24120500, "18 January 2026"),
        ("January 2026", "01/2026", 23864000, "17 February 2026"),
        ("February 2026", "02/2026", 22705500, "18 March 2026"),
        ("March 2026", "03/2026", 27418300, "18 April 2026"),
        ("April 2026", "04/2026", 24980400, "19 May 2026"),
        ("May 2026", "05/2026", 26142600, "18 June 2026"),
        ("June 2026", "06/2026", 25873100, "17 July 2026"),
        ("July 2026", "07/2026", 23890900, "18 August 2026"),
    ]
    total_outward = sum(p[2] for p in periods)  # ~ 1.99 cr scale check

    def period_page(name, ret_period, outward, filed):
        cgst = round(outward * 0.025)
        sgst = cgst
        tax_payable = cgst + sgst
        itc_c = round(cgst * 0.86)
        itc_s = itc_c
        cash_c = cgst - itc_c
        cash_s = sgst - itc_s
        blk = []
        blk.append(Paragraph("FORM GSTR-3B", ParagraphStyle(
            "g_t", parent=S["h1"], alignment=TA_CENTER, spaceAfter=0)))
        blk.append(Paragraph("Monthly Return &mdash; Summary of outward supplies and tax",
                             S["subtitle"]))
        blk.append(HRFlowable(width="100%", thickness=1.0, color=colors.HexColor("#20406a"),
                              spaceBefore=2, spaceAfter=6))
        info = [
            ["GSTIN", ENTITY["gstin"], "Return Period", ret_period],
            ["Legal Name", ENTITY["name"], "Tax Period", name],
            ["ARN", "AA33%s%07d" % (ret_period.replace("/", ""), 1000000 + outward % 8999999),
             "Date of Filing", filed],
        ]
        it = Table([[Paragraph(a, S["cell_b"]), Paragraph(b, S["cell"]),
                     Paragraph(c, S["cell_b"]), Paragraph(d, S["cell"])]
                    for a, b, c, d in info],
                   colWidths=[24 * mm, 62 * mm, 26 * mm, 44 * mm])
        it.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9bbfd0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfe1ea")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef5f8")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef5f8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        blk.append(it)
        blk.append(Spacer(1, 8))

        blk.append(Paragraph("3.1 Details of Outward Supplies and inward supplies liable to "
                             "reverse charge", S["h2"]))
        r31 = [
            ["(a) Outward taxable supplies (other than zero rated, nil rated and exempted)",
             indian_group(outward), indian_group(0), indian_group(cgst), indian_group(sgst)],
            ["(b) Outward taxable supplies (zero rated)", "0", "0", "0", "0"],
            ["(c) Other outward supplies (nil rated, exempted)", "0", "0", "0", "0"],
            ["(d) Inward supplies (liable to reverse charge)", "0", "0", "0", "0"],
        ]
        h31 = ["Nature of Supplies", "Taxable Value", "IGST", "CGST", "SGST"]
        blk.append(_money_table(r31, [78 * mm, 26 * mm, 18 * mm, 18 * mm, 18 * mm], S,
                                header=h31))
        blk.append(Spacer(1, 6))

        blk.append(Paragraph("4. Eligible Input Tax Credit (ITC)", S["h2"]))
        r4 = [
            ["(A) ITC Available (whether in full or part)", indian_group(0),
             indian_group(itc_c), indian_group(itc_s)],
            ["(C) Net ITC Available", indian_group(0),
             indian_group(itc_c), indian_group(itc_s)],
        ]
        blk.append(_money_table(r4, [92 * mm, 22 * mm, 22 * mm, 22 * mm], S,
                                header=["Details", "IGST", "CGST", "SGST"], total_rows=[1]))
        blk.append(Spacer(1, 6))

        blk.append(Paragraph("5. / 6. Payment of Tax", S["h2"]))
        r6 = [
            ["Integrated Tax (IGST)", "0", "0", "0"],
            ["Central Tax (CGST)", indian_group(cgst), indian_group(itc_c), indian_group(cash_c)],
            ["State Tax (SGST)", indian_group(sgst), indian_group(itc_s), indian_group(cash_s)],
            ["Total", indian_group(tax_payable), indian_group(itc_c + itc_s),
             indian_group(cash_c + cash_s)],
        ]
        blk.append(_money_table(r6, [58 * mm, 34 * mm, 34 * mm, 34 * mm], S, total_rows=[3],
                                header=["Description", "Tax Payable", "Paid through ITC",
                                        "Paid in Cash"]))
        blk.append(Spacer(1, 8))
        blk.append(Paragraph(
            "Verified and filed under Section 39 of the CGST/SGST Act, 2017. Return status: "
            "Filed. Date of filing: <b>%s</b>." % filed, S["small"]))
        return blk

    def story():
        st = []
        # ---- Cover page (makes the four-month gap visible at a glance) ----
        st += letterhead(S, tagline=False)
        st.append(Paragraph("GSTR-3B RETURNS &mdash; COMPILATION FOR THE BANK",
                            ParagraphStyle("gc_t", parent=S["h1"], alignment=TA_CENTER)))
        st.append(Paragraph("GSTIN " + ENTITY["gstin"] +
                            " &nbsp;|&nbsp; Filed monthly summary returns enclosed",
                            S["subtitle"]))
        st.append(HRFlowable(width="100%", thickness=1.0, color=colors.HexColor("#20406a"),
                             spaceBefore=2, spaceAfter=8))
        st.append(Paragraph("Returns enclosed in this compilation (eight periods):", S["h2"]))
        cov = [["#", "Tax Period", "Return Period", "Outward Taxable Supplies (INR)",
                "Date of Filing"]]
        for i, (name, rp, outward, filed) in enumerate(periods, 1):
            cov.append([str(i), name, rp, indian_group(outward), filed])
        cov.append(["", "TOTAL (8 periods)", "", indian_group(total_outward), ""])
        ct = Table(cov, colWidths=[8 * mm, 40 * mm, 26 * mm, 55 * mm, 34 * mm])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20406a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#888888")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2f7")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        st.append(ct)
        st.append(Spacer(1, 10))
        # Explicit note surfacing the gap for the viewer to highlight.
        note = Paragraph(
            "Note: This compilation begins with the December 2025 tax period. The GSTR-3B "
            "returns for the tax periods <b>August 2025, September 2025, October 2025 and "
            "November 2025 are not enclosed</b> in this set.",
            ParagraphStyle("gap", parent=S["body_l"], fontName="Helvetica-Bold",
                           textColor=colors.HexColor("#8a1c1c"), backColor=colors.HexColor("#fbeaea"),
                           borderPadding=6, leading=14))
        st.append(note)
        st.append(Spacer(1, 6))
        st.append(Paragraph(
            "Aggregate outward taxable supplies across the eight enclosed periods: Rs. "
            + indian_group(total_outward) + ", consistent with the scale of the company's "
            "part-year turnover for the financial year 2025-26.", S["small"]))

        for name, rp, outward, filed in periods:
            st.append(PageBreak())
            st += period_page(name, rp, outward, filed)
        return st

    path = os.path.join(outdir, "Southgate_GSTR3B_Dec2025_Jul2026.pdf")
    return path, build_auto(path, story, title="GSTR-3B Compilation (Specimen)")


# --------------------------------------------------------------------------- #
# 6. Provisional FY2026 -- page numbering runs 1, 2, 6, 7
# --------------------------------------------------------------------------- #
def build_provisional_fy2026(outdir):
    S = styles()
    d = F.pl_fy2026_9m()

    def num(x):
        return indian_group(x)

    st = []
    # ---- Physical page 1 (label "Page 1 of 7"): P&L top ----
    st += letterhead(S, tagline=False)
    st.append(Paragraph("PROVISIONAL FINANCIAL STATEMENTS",
                        ParagraphStyle("p_t", parent=S["h1"], alignment=TA_CENTER)))
    st.append(Paragraph("For the nine months ended 31 December 2025 (unaudited)", S["subtitle"]))
    st.append(HRFlowable(width="100%", thickness=1.0, color=colors.HexColor("#20406a"),
                         spaceBefore=2, spaceAfter=8))
    st.append(Paragraph("STATEMENT OF PROFIT AND LOSS", S["h2"]))
    st.append(Paragraph("(All amounts in Indian Rupees unless otherwise stated)", S["small"]))
    st.append(Spacer(1, 4))
    pl_rows_income = [
        ["I. Revenue from operations", num(d["revenue"])],
        ["II. Other income", num(d["other_income"])],
        ["III. Total income (I + II)", num(d["total_income"])],
    ]
    st.append(_money_table(pl_rows_income, [120 * mm, 40 * mm], S, total_rows=[2],
                           header=["Particulars", "9M ended 31 Dec 2025"]))
    st.append(Spacer(1, 6))
    st.append(Paragraph("IV. Expenses", S["h2"]))
    exp_rows = [
        ["Cost of materials consumed", num(d["materials"])],
        ["Changes in inventories of finished goods and WIP", num(d["change_inv"])],
        ["Employee benefits expense", num(d["employee"])],
        ["Finance costs", num(d["finance_costs"])],
        ["Depreciation and amortisation expense", num(d["depreciation"])],
        ["Other expenses", num(d["other_exp"])],
        ["Total expenses", num(d["total_opex"] + d["finance_costs"] + d["depreciation"])],
    ]
    st.append(_money_table(exp_rows, [120 * mm, 40 * mm], S, total_rows=[6],
                           header=["Particulars", "9M ended 31 Dec 2025"]))

    st.append(PageBreak())
    # ---- Physical page 2 (label "Page 2 of 7"): P&L bottom + EBITDA ----
    st.append(Paragraph("STATEMENT OF PROFIT AND LOSS (continued)", S["h2"]))
    tot_exp = d["total_opex"] + d["finance_costs"] + d["depreciation"]
    pl_rows_profit = [
        ["V. Profit before tax (III - IV)", num(d["pbt"])],
        ["VI. Tax expense (current and deferred)", num(d["tax"])],
        ["VII. Profit for the period (V - VI)", num(d["pat"])],
    ]
    st.append(_money_table(pl_rows_profit, [120 * mm, 40 * mm], S, total_rows=[2],
                           header=["Particulars", "9M ended 31 Dec 2025"]))
    st.append(Spacer(1, 8))
    memo = [
        ["Revenue from operations", num(d["revenue"])],
        ["EBITDA (earnings before interest, tax, depreciation and amortisation)", num(d["ebitda"])],
        ["Profit after tax", num(d["pat"])],
    ]
    st.append(Paragraph("Memorandum &mdash; key figures", S["h2"]))
    st.append(_money_table(memo, [120 * mm, 40 * mm], S,
                           header=["Particulars", "9M ended 31 Dec 2025"]))
    st.append(Spacer(1, 10))
    st.append(Paragraph(
        "The Balance Sheet as at 31 December 2025, together with its supporting schedules, "
        "is set out on pages 3 to 5 of these provisional statements.", S["small"]))

    st.append(PageBreak())
    # ---- Physical page 3 (label "Page 6 of 7"): notes -- BS pages 3-5 absent ----
    st.append(Paragraph("NOTES TO THE PROVISIONAL FINANCIAL STATEMENTS", S["h2"]))
    notes = [
        "1. Basis of preparation: These provisional financial statements have been prepared on "
        "the historical cost convention on an accrual basis, in accordance with the accounting "
        "principles generally accepted in India, and are unaudited. They are prepared for the "
        "limited purpose of submission to the company's bankers in connection with a credit "
        "application and are subject to year-end audit adjustments.",
        "2. Revenue recognition: Revenue from the sale of home textiles and furnishing fabrics "
        "is recognised on despatch of goods to customers, net of returns, trade discounts and "
        "goods and services tax.",
        "3. Inventories: Inventories are valued at the lower of cost and net realisable value. "
        "Cost is determined on a weighted average basis and includes an appropriate share of "
        "manufacturing overheads.",
        "4. Depreciation: Depreciation on property, plant and equipment has been provided on the "
        "written down value method at the rates prescribed under Schedule II to the Companies "
        "Act, 2013, apportioned for the nine-month period.",
        "5. Taxation: The tax charge for the period has been estimated by applying the effective "
        "rate expected for the full year to the profit before tax for the period.",
        "6. These provisional statements are unaudited and have been signed by the directors "
        "for identification.",
    ]
    for n in notes:
        st.append(Paragraph(n, S["body"]))

    st.append(PageBreak())
    # ---- Physical page 4 (label "Page 7 of 7"): signature block ----
    st.append(Paragraph("SIGNATURES", S["h2"]))
    st.append(Paragraph(
        "The provisional financial statements for the nine months ended 31 December 2025, "
        "comprising the Statement of Profit and Loss, the Balance Sheet and the notes thereto, "
        "are approved by the Board of Directors and signed on its behalf.", S["body"]))
    st.append(Spacer(1, 28))
    sig = Table([
        [Paragraph("_____________________________<br/><b>Lakshmi Iyer</b><br/>"
                   "Managing Director (DIN 07421683)", S["cell"]),
         Paragraph("_____________________________<br/><b>Venkat Iyer</b><br/>"
                   "Director (DIN 07421699)", S["cell"])],
    ], colWidths=[78 * mm, 78 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    st.append(sig)
    st.append(Spacer(1, 18))
    st.append(Paragraph("Place: Coimbatore &nbsp;&nbsp;|&nbsp;&nbsp; Date: 12 January 2026",
                        S["small"]))
    st.append(Spacer(1, 8))
    st.append(Paragraph(
        "For Southgate Textiles Private Limited &mdash; provisional and unaudited.", S["small"]))

    # Deliberate page numbering: 1, 2, 6, 7 (pages 3,4,5 -- the balance sheet -- absent).
    labels = ["Page 1 of 7", "Page 2 of 7", "Page 6 of 7", "Page 7 of 7"]
    path = os.path.join(outdir, "Southgate_Provisional_FY2026.pdf")
    return path, build_document(path, st, page_labels=labels,
                                title="Provisional Financial Statements (Specimen)")


# --------------------------------------------------------------------------- #
# 7. Board resolution draft -- PLAIN PAPER, EMPTY signature block
# --------------------------------------------------------------------------- #
def build_board_resolution(outdir):
    S = styles()
    st = []
    # NO letterhead / logo / header -- plain paper is part of the defect.
    st.append(Paragraph("CERTIFIED TRUE COPY OF THE RESOLUTION",
                        ParagraphStyle("br_t", parent=S["h1"], alignment=TA_CENTER,
                                       spaceBefore=6)))
    st.append(Paragraph(
        "Certified true copy of the resolution passed at the meeting of the Board of Directors "
        "of Southgate Textiles Private Limited (CIN " + ENTITY["cin"] + ") held at the "
        "registered office of the company at " + ENTITY["office"] + " on Monday, 03 August 2026 "
        "at 11:00 a.m.", S["body"]))
    st.append(Spacer(1, 6))
    st.append(Paragraph("RESOLVED FOR BORROWING AND CREATION OF SECURITY", S["h2"]))
    st.append(Paragraph(
        "\"<b>RESOLVED THAT</b> pursuant to the provisions of Section 179(3)(d) of the Companies "
        "Act, 2013 and the rules made thereunder, and Article 84 of the Articles of Association "
        "of the company, the consent of the Board of Directors be and is hereby accorded to "
        "borrow from Continental Commercial Bank, Coimbatore SME Branch, credit facilities by "
        "way of a Cash Credit limit of Rs. 2,85,00,000 (Rupees Two Crore Eighty-Five Lakh only) "
        "and a Term Loan of Rs. 1,40,00,000 (Rupees One Crore Forty Lakh only), aggregating to "
        "<b>Rs. 4,25,00,000 (Rupees Four Crore Twenty-Five Lakh only)</b>, on such terms and "
        "conditions as may be stipulated by the said bank.\"", S["body"]))
    st.append(Paragraph(
        "\"<b>RESOLVED FURTHER THAT</b> the company do create such security by way of "
        "hypothecation of stock and book debts, and mortgage or charge over the immovable and "
        "movable properties of the company, as may be required by the said bank for securing the "
        "aforesaid facilities.\"", S["body"]))
    st.append(Paragraph(
        "\"<b>RESOLVED FURTHER THAT</b> Smt. Lakshmi Iyer, Managing Director (DIN 07421683), and "
        "Sri. Venkat Iyer, Director (DIN 07421699), be and are hereby severally authorised to "
        "execute all such loan agreements, deeds of hypothecation, security documents and "
        "writings, and to do all such acts, deeds and things as may be necessary to give effect "
        "to the above resolution.\"", S["body"]))
    st.append(Spacer(1, 30))
    st.append(Paragraph("For and on behalf of the Board of Directors", S["body_l"]))
    st.append(Spacer(1, 40))
    # EMPTY signature block: name/designation lines present, but NO signature, NO date.
    sig = Table([
        [Paragraph("Name:", S["cell"]), Paragraph("Name:", S["cell"])],
        [Paragraph("Designation:", S["cell"]), Paragraph("Designation:", S["cell"])],
        [Paragraph("Signature:", S["cell"]), Paragraph("Signature:", S["cell"])],
        [Paragraph("Date:", S["cell"]), Paragraph("Date:", S["cell"])],
    ], colWidths=[78 * mm, 78 * mm])
    sig.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
    ]))
    st.append(sig)
    st.append(Spacer(1, 6))
    st.append(Paragraph("(Certified true copy &mdash; to be signed by the Chairman / Company "
                        "Secretary.)", S["small"]))

    path = os.path.join(outdir, "Southgate_Board_Resolution_draft.pdf")
    return path, build_document(path, st, page_labels=["Page 1 of 1"],
                                title="Board Resolution Draft (Specimen)")
