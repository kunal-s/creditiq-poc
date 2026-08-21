"""
Priority group one: the three documents that together form the contradiction.
  1. Title Deed (with the Meridian mortgage memorandum on page 3)
  2. Nil Facilities Declaration
  3. Continental Commercial Bank 12-month current account statement
"""
import os
import random

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether,
    LongTable,
)

from common import (
    build_document, build_auto, styles, letterhead, inr, rs, indian_group, ENTITY, DIRECTORS,
)


# --------------------------------------------------------------------------- #
# 1. Title Deed  (4 pages; Meridian mortgage memorandum on page 3)
# --------------------------------------------------------------------------- #
def build_title_deed(outdir):
    S = styles()
    st = []

    hdr = ParagraphStyle("td_hdr", parent=S["title"], fontSize=14)
    st.append(Paragraph("DEED OF SALE", hdr))
    st.append(Paragraph("(Registered)", S["subtitle"]))
    st.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#20406a"),
                         spaceBefore=2, spaceAfter=8))

    st.append(Paragraph(
        "Document No. 2841 of 2016 &nbsp;&nbsp;|&nbsp;&nbsp; Book 1 &nbsp;&nbsp;|&nbsp;&nbsp; "
        "Office of the Sub-Registrar, Kurichi, Coimbatore District, Tamil Nadu",
        ParagraphStyle("td_reg", parent=S["small"], alignment=TA_CENTER)))
    st.append(Spacer(1, 8))

    st.append(Paragraph(
        "THIS DEED OF SALE is made and executed on this <b>22nd day of July 2016</b> "
        "(Twenty-second day of July Two Thousand Sixteen).", S["body"]))

    st.append(Paragraph("BETWEEN", S["h2"]))
    st.append(Paragraph(
        "<b>M/s. Palani Chettiar Industrial Holdings</b>, a partnership firm having its office "
        "at No. 14, Trichy Road, Singanallur, Coimbatore 641005, represented by its managing "
        "partner Sri. R. Palani Chettiar, hereinafter called the <b>VENDOR</b> (which expression "
        "shall, where the context so admits, include its successors and assigns) of the ONE PART;",
        S["body"]))
    st.append(Paragraph("AND", S["h2"]))
    st.append(Paragraph(
        "<b>Southgate Textiles Private Limited</b>, a company incorporated under the Companies "
        "Act, 2013, bearing CIN " + ENTITY["cin"] + ", having its registered office at " +
        ENTITY["office"] + ", represented by its Director Smt. Lakshmi Iyer, hereinafter called "
        "the <b>PURCHASER</b> (which expression shall, where the context so admits, include its "
        "successors and assigns) of the OTHER PART.", S["body"]))

    st.append(Paragraph("WHEREAS:", S["h2"]))
    for w in [
        "The Vendor is the absolute owner, seized and possessed of and otherwise well and "
        "sufficiently entitled to the industrial plot and building more particularly described "
        "in the Schedule hereunder written (hereinafter the 'Scheduled Property'), having "
        "acquired the same by a registered Sale Deed dated 09 February 2009, Document No. 1176 "
        "of 2009, registered at the Office of the Sub-Registrar, Kurichi.",
        "The Vendor has agreed to sell and the Purchaser has agreed to purchase the Scheduled "
        "Property free from all encumbrances, charges, liens and attachments for a total sale "
        "consideration of Rs. 1,15,00,000 (Rupees One Crore Fifteen Lakh only).",
        "The Purchaser has, prior to the execution of these presents, satisfied itself as to the "
        "title of the Vendor to the Scheduled Property.",
    ]:
        st.append(Paragraph(w, S["body"]))

    st.append(PageBreak())

    # -- Page 2: operative clauses --
    st.append(Paragraph("NOW THIS DEED WITNESSETH AS FOLLOWS:", S["h2"]))
    clauses = [
        "In consideration of the sum of Rs. 1,15,00,000 (Rupees One Crore Fifteen Lakh only) "
        "paid by the Purchaser to the Vendor, the receipt whereof the Vendor hereby acknowledges, "
        "the Vendor doth hereby grant, convey, sell, transfer and assure unto the Purchaser the "
        "Scheduled Property TO HAVE AND TO HOLD the same absolutely and forever.",
        "The Vendor hereby covenants with the Purchaser that the Vendor has a clear, absolute "
        "and marketable title to the Scheduled Property and that the same is free from all "
        "encumbrances, prior sales, gifts, mortgages, attachments, court injunctions, and "
        "acquisition proceedings whatsoever as on the date of execution of these presents.",
        "The Vendor has this day delivered vacant physical possession of the Scheduled Property "
        "to the Purchaser.",
        "The Vendor hereby covenants that the Purchaser shall hereafter peacefully and quietly "
        "hold, possess and enjoy the Scheduled Property and receive the rents and profits "
        "thereof without any interruption, claim or demand from the Vendor or any person "
        "claiming under or in trust for the Vendor.",
        "All statutory outgoings, taxes, cesses and assessments in respect of the Scheduled "
        "Property up to the date of these presents have been duly paid by the Vendor.",
        "The Vendor shall, at the request and cost of the Purchaser, execute and do all such "
        "acts, deeds and things as may be reasonably required for more perfectly assuring the "
        "Scheduled Property unto the Purchaser.",
    ]
    for i, c in enumerate(clauses, 1):
        st.append(Paragraph("%d.&nbsp;&nbsp;%s" % (i, c), S["body"]))

    st.append(Spacer(1, 8))
    st.append(Paragraph("SCHEDULE OF PROPERTY", S["h2"]))
    st.append(Paragraph(
        "All that piece and parcel of industrial land bearing <b>Plot No. 47</b>, SIDCO "
        "Industrial Estate, Kurichi Village, Coimbatore South Taluk, Coimbatore District, "
        "Tamil Nadu, admeasuring 1,858 square metres, together with the RCC factory building "
        "of built-up area 1,240 square metres constructed thereon, bounded as follows:",
        S["body"]))
    sched = [
        ["North by", "Plot No. 46, SIDCO Industrial Estate"],
        ["South by", "Plot No. 48, SIDCO Industrial Estate"],
        ["East by", "SIDCO Internal Road No. 3"],
        ["West by", "Storm-water drain and compound wall"],
    ]
    t = Table([[Paragraph(a, S["cell_b"]), Paragraph(b, S["cell"])] for a, b in sched],
              colWidths=[35 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    st.append(t)

    st.append(PageBreak())

    # -- Page 3: ENCUMBRANCE / MORTGAGE MEMORANDUM (the critical page) --
    st.append(Paragraph("MEMORANDUM OF ENCUMBRANCE", S["h1"]))
    st.append(Paragraph(
        "Endorsement recorded against the Scheduled Property subsequent to the registration "
        "of this Deed of Sale, as reflected in the Encumbrance Certificate issued by the Office "
        "of the Sub-Registrar, Kurichi.", S["small"]))
    st.append(Spacer(1, 10))

    # Make this box impossible to miss and easy to read.
    box_title = Paragraph(
        "SUBSISTING CHARGE &mdash; MORTGAGE BY DEPOSIT OF TITLE DEEDS",
        ParagraphStyle("box_t", parent=S["h2"], alignment=TA_CENTER,
                       textColor=colors.white, fontSize=11.5, spaceBefore=0, spaceAfter=0))
    rows = [
        ["Nature of charge",
         "Mortgage by deposit of title deeds (equitable mortgage)"],
        ["Created in favour of",
         "<b>MERIDIAN BANK, Coimbatore Branch</b>"],
        ["Date of creation",
         "<b>14 March 2024</b>"],
        ["Amount secured",
         "<b>Rs. 1,75,00,000 (Rupees One Crore Seventy-Five Lakh only)</b>"],
        ["Property charged",
         "Plot No. 47, SIDCO Industrial Estate, Kurichi, Coimbatore 641021"],
        ["Facilities secured",
         "Credit facilities granted by Meridian Bank to Southgate Textiles Private Limited"],
        ["Status",
         "Subsisting and not discharged as on the date of this endorsement"],
    ]
    data = [[box_title, ""]]
    for k, v in rows:
        data.append([Paragraph(k, S["cell_b"]),
                     Paragraph(v, ParagraphStyle("box_v", parent=S["cell"], fontSize=9.4,
                                                 leading=12))])
    tbl = Table(data, colWidths=[46 * mm, 109 * mm])
    tbl.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#8a1c1c")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fbf2f2")),
        ("BOX", (0, 0), (-1, -1), 1.4, colors.HexColor("#8a1c1c")),
        ("INNERGRID", (0, 1), (-1, -1), 0.5, colors.HexColor("#d9b3b3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    st.append(tbl)
    st.append(Spacer(1, 10))
    st.append(Paragraph(
        "The above charge was created by deposit of the original title deeds of the Scheduled "
        "Property with Meridian Bank, Coimbatore Branch, on 14 March 2024, as security for the "
        "credit facilities availed by Southgate Textiles Private Limited from the said bank, and "
        "the same remains subsisting on record. This memorandum is recorded for the information "
        "of all persons dealing with the Scheduled Property.", S["body"]))
    st.append(Spacer(1, 8))
    st.append(Paragraph(
        "Encumbrance Certificate reference: EC/KUR/2026/03187, period 01 January 2016 to "
        "31 July 2026.", S["small"]))

    st.append(PageBreak())

    # -- Page 4: execution / signatures / registration --
    st.append(Paragraph(
        "IN WITNESS WHEREOF the Vendor and the Purchaser have hereunto set their respective "
        "hands on the day, month and year first above written.", S["body"]))
    st.append(Spacer(1, 22))

    sig = Table([
        [Paragraph("For M/s. Palani Chettiar Industrial Holdings<br/><br/><br/>"
                   "_____________________________<br/>(VENDOR)", S["cell"]),
         Paragraph("For Southgate Textiles Private Limited<br/><br/><br/>"
                   "_____________________________<br/>Lakshmi Iyer, Director (PURCHASER)", S["cell"])],
    ], colWidths=[77 * mm, 78 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    st.append(sig)
    st.append(Spacer(1, 20))
    st.append(Paragraph("WITNESSES:", S["h2"]))
    st.append(Paragraph("1.&nbsp;&nbsp;S. Ramanathan, No. 5, Bharathi Street, Coimbatore 641002.",
                        S["body"]))
    st.append(Paragraph("2.&nbsp;&nbsp;K. Meenakshi, No. 22, Gandhipuram, Coimbatore 641012.",
                        S["body"]))
    st.append(Spacer(1, 16))
    st.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#888888"),
                         spaceBefore=2, spaceAfter=6))
    st.append(Paragraph("REGISTRATION ENDORSEMENT", S["h2"]))
    st.append(Paragraph(
        "Registered as Document No. 2841 of 2016, Book 1, Volume 218, Pages 44 to 51, in the "
        "Office of the Sub-Registrar, Kurichi, Coimbatore District, on 22 July 2016. Stamp duty "
        "of Rs. 8,05,000 and registration fee of Rs. 1,15,000 paid.", S["body"]))
    st.append(Paragraph(
        "Title chain verified clear from the registered Sale Deed of 2009 through to the present "
        "conveyance of 2016; no prior subsisting encumbrance was recorded at the date of "
        "registration. The Meridian Bank charge noted at page 3 was created subsequently, on "
        "14 March 2024.", S["small"]))

    path = os.path.join(outdir, "Southgate_Title_Deed_Coimbatore_Unit.pdf")
    labels = ["Page 1 of 4", "Page 2 of 4", "Page 3 of 4", "Page 4 of 4"]
    return path, build_document(path, st, page_labels=labels, title="Deed of Sale (Specimen)")


# --------------------------------------------------------------------------- #
# 2. Nil Facilities Declaration  (1 page)
# --------------------------------------------------------------------------- #
def build_nil_declaration(outdir):
    S = styles()
    st = letterhead(S)

    st.append(Paragraph("DECLARATION OF NIL EXISTING FACILITIES AND UNENCUMBERED SECURITY",
                        ParagraphStyle("nd_t", parent=S["h1"], alignment=TA_CENTER)))
    st.append(Spacer(1, 4))
    st.append(Paragraph("Date: 06 August 2026", S["body_l"]))
    st.append(Paragraph("To,<br/>The Branch Manager<br/>Continental Commercial Bank<br/>"
                        "Coimbatore SME Branch", S["body_l"]))
    st.append(Spacer(1, 6))
    st.append(Paragraph("Dear Sir/Madam,", S["body_l"]))
    st.append(Paragraph(
        "Sub: Declaration in support of application for working capital and term loan facilities.",
        ParagraphStyle("nd_sub", parent=S["body_l"], fontName="Helvetica-Bold")))

    st.append(Paragraph(
        "I, <b>Lakshmi Iyer</b>, Managing Director of <b>Southgate Textiles Private Limited</b> "
        "(CIN " + ENTITY["cin"] + "), having its registered office at " + ENTITY["office"] +
        ", being duly authorised in this behalf, do hereby solemnly declare and affirm as "
        "follows:", S["body"]))

    decls = [
        "That the Company does <b>not have any existing credit facilities, borrowings, loans, "
        "overdrafts, cash credit, bill discounting or other financial accommodation</b> of any "
        "nature whatsoever with any bank, non-banking financial company, or other financial "
        "institution as on the date of this declaration.",
        "That there are <b>no charges, mortgages, hypothecations, liens or encumbrances</b> "
        "created or subsisting over any of the assets of the Company in favour of any bank or "
        "financial institution.",
        "That the immovable property offered as collateral security, namely the industrial unit "
        "at Plot No. 47, SIDCO Industrial Estate, Kurichi, Coimbatore 641021, is owned "
        "absolutely by the Company and is <b>free from any encumbrance, mortgage, charge or "
        "prior claim</b> of any kind.",
        "That the Company maintains its banking relationship solely with Continental Commercial "
        "Bank, Coimbatore SME Branch, and has not availed of any facility from, nor deposited "
        "title deeds with, any other bank or institution.",
        "That the statements made herein are true and correct to the best of my knowledge and "
        "belief, and nothing material has been concealed therefrom. I am aware that this "
        "declaration is being relied upon by the Bank for the purpose of sanctioning credit "
        "facilities.",
    ]
    for i, d in enumerate(decls, 1):
        st.append(Paragraph("%d.&nbsp;&nbsp;%s" % (i, d), S["body"]))

    st.append(Spacer(1, 22))
    st.append(Paragraph("For Southgate Textiles Private Limited", S["body_l"]))
    st.append(Spacer(1, 26))
    st.append(Paragraph(
        "_____________________________<br/><b>Lakshmi Iyer</b><br/>Managing Director "
        "(DIN 07421683)", S["body_l"]))
    st.append(Spacer(1, 6))
    st.append(Paragraph("Place: Coimbatore &nbsp;&nbsp;|&nbsp;&nbsp; Date: 06 August 2026",
                        S["small"]))

    path = os.path.join(outdir, "Southgate_Nil_Facilities_Declaration.pdf")
    return path, build_document(path, st, page_labels=["Page 1 of 1"],
                                title="Nil Facilities Declaration (Specimen)")


# --------------------------------------------------------------------------- #
# 3. Continental Commercial Bank 12-month current account statement
# --------------------------------------------------------------------------- #
_MONTHS = [
    ("Aug", 2025, 31), ("Sep", 2025, 30), ("Oct", 2025, 31), ("Nov", 2025, 30),
    ("Dec", 2025, 31), ("Jan", 2026, 31), ("Feb", 2026, 28), ("Mar", 2026, 31),
    ("Apr", 2026, 30), ("May", 2026, 31), ("Jun", 2026, 30), ("Jul", 2026, 31),
]
_MONTH_FULL = {"Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
               "May": "May", "Jun": "June", "Jul": "July", "Aug": "August",
               "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December"}


def _gen_transactions():
    rng = random.Random(20260821)

    customers = ["RELIANCE RETAIL LTD", "TRENT LTD", "FABINDIA OVERSEAS",
                 "HOME CENTRE FZE", "ARVIND LIFESTYLE", "MAX FASHION",
                 "DELHIVERY B2B", "WELSPUN DISTRIB", "TEXPORT SYNDICATE",
                 "SOUTH INDIA MALLS", "URBAN LADDER PVT", "SPACES BY WELSPUN"]
    suppliers = ["SRI YARN TRADERS", "KPR SPINNING MILLS", "COIMBATORE DYES",
                 "PONNI CHEMICALS", "ANNAI PACKAGING", "TEXFAB ACCESSORIES",
                 "LOOM SPARES CO", "NANDINI LOGISTICS", "SAKTHI COTTON MILLS",
                 "VELAN THREADS PVT"]

    # First pass: build the ordered event list with signed deltas (no balance yet),
    # so we can choose an opening balance that keeps every running balance positive.
    events = []  # (mon, yr, day, part, ref, debit, credit)
    for mon, yr, ndays in _MONTHS:
        me = []
        # Undisclosed Meridian servicing: exact EMI on the 5th of every month.
        me.append((5, "MERIDIAN BANK EMI DR", "ACH/MERIDIAN/EMI", 218750, 0))

        # Customer collections -- a manufacturer of this scale collects frequently.
        for _ in range(rng.randint(10, 13)):
            day = rng.randint(1, ndays)
            amt = rng.randrange(500000, 1900000, 1000)
            cust = rng.choice(customers)
            mode = rng.choice(["NEFT", "RTGS", "IMPS"])
            me.append((day, "%s CR %s" % (mode, cust),
                       "%s/%08d" % (mode, rng.randint(10000000, 99999999)), 0, amt))
        # One or two large receipts.
        for _ in range(rng.randint(1, 2)):
            day = rng.randint(6, ndays)
            amt = rng.randrange(2200000, 3600000, 5000)
            me.append((day, "RTGS CR " + rng.choice(customers),
                       "RTGS/%08d" % rng.randint(10000000, 99999999), 0, amt))

        # Supplier payments -- yarn and dyes dominate cost.
        for _ in range(rng.randint(10, 13)):
            day = rng.randint(1, ndays)
            amt = rng.randrange(450000, 1750000, 1000)
            sup = rng.choice(suppliers)
            me.append((day, "RTGS DR " + sup,
                       "RTGS/%08d" % rng.randint(10000000, 99999999), amt, 0))

        # Salary run (~46 staff) in the last week.
        sal_day = min(ndays, rng.randint(28, 30))
        me.append((sal_day, "SALARY BULK NEFT - STAFF", "BULK/SAL/%s%d" % (mon, yr),
                   rng.randrange(1385000, 1560000, 500), 0))
        # GST payment ~ 20th.
        me.append((20, "GST PMT GSTR-3B " + mon.upper(),
                   "GST/CHALLAN/%08d" % rng.randint(10000000, 99999999),
                   rng.randrange(1650000, 2450000, 1000), 0))
        # Electricity (TNEB).
        me.append((rng.randint(10, 16), "TNEB ELECTRICITY CHG", "ECS/TNEB/%s" % mon,
                   rng.randrange(285000, 420000, 100), 0))
        # EPF / ESI remittance.
        me.append((15, "EPF ESI REMITTANCE", "EPFO/%s%d" % (mon, yr),
                   rng.randrange(168000, 214000, 100), 0))
        # Bank charges most months.
        if rng.random() < 0.7:
            me.append((rng.randint(1, ndays), "BANK CHARGES + GST", "CHG/MISC",
                       rng.randrange(1200, 4800, 50), 0))

        me.sort(key=lambda e: e[0])
        for day, part, ref, dr, cr in me:
            events.append((mon, yr, day, part, ref, dr, cr))

    # Choose opening balance so the minimum running balance is comfortably positive.
    run = 0
    lowest = 0
    for _, _, _, _, _, dr, cr in events:
        run += cr - dr
        lowest = min(lowest, run)
    opening = (-lowest) + 4200000
    opening = int(round(opening / 1000.0) * 1000)

    bal = opening
    total_dr = total_cr = 0
    txns = []
    for mon, yr, day, part, ref, dr, cr in events:
        bal = bal - dr + cr
        total_dr += dr
        total_cr += cr
        txns.append(("%02d %s %d" % (day, mon, yr), part, ref, dr, cr, bal))

    return opening, bal, total_dr, total_cr, txns


def _ca_story(S, opening, closing, total_dr, total_cr, txns):
    st = []
    # Bank header
    st.append(Paragraph("Continental Commercial Bank",
                        ParagraphStyle("cb_t", parent=S["title"], fontSize=15,
                                       textColor=colors.HexColor("#0b4f6c"))))
    st.append(Paragraph("Coimbatore SME Branch &mdash; Statement of Account", S["subtitle"]))
    st.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#0b4f6c"),
                         spaceBefore=2, spaceAfter=8))

    info = [
        ["Account Name", ENTITY["name"], "Account Number", ENTITY["account"]],
        ["Account Type", "Current Account", "Branch / IFSC", "Coimbatore SME / CCBL0004821"],
        ["Statement Period", "01 August 2025 to 31 July 2026", "Currency", "INR"],
        ["Registered Office", ENTITY["office"], "GSTIN", ENTITY["gstin"]],
    ]
    it = Table([[Paragraph(a, S["cell_b"]), Paragraph(b, S["cell"]),
                 Paragraph(c, S["cell_b"]), Paragraph(d, S["cell"])] for a, b, c, d in info],
               colWidths=[28 * mm, 62 * mm, 26 * mm, 50 * mm])
    it.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9bbfd0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfe1ea")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef5f8")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef5f8")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    st.append(it)
    st.append(Spacer(1, 8))

    # Transaction ledger
    header = [Paragraph("Date", S["cell_b"]), Paragraph("Particulars", S["cell_b"]),
              Paragraph("Reference", S["cell_b"]), Paragraph("Debit (INR)", S["cell_rb"]),
              Paragraph("Credit (INR)", S["cell_rb"]), Paragraph("Balance (INR)", S["cell_rb"])]
    data = [header]
    # opening balance row
    data.append([Paragraph("01 Aug 2025", S["cell"]),
                 Paragraph("<b>OPENING BALANCE</b>", S["cell"]),
                 Paragraph("", S["cell"]), Paragraph("", S["cell_r"]),
                 Paragraph("", S["cell_r"]),
                 Paragraph(indian_group(opening), S["cell_rb"])])
    meridian_rows = []
    for i, (datestr, part, ref, dr, cr, bal) in enumerate(txns):
        row = [
            Paragraph(datestr, S["cell"]),
            Paragraph(part, S["cell"]),
            Paragraph(ref, ParagraphStyle("ref", parent=S["cell"], fontSize=7.2,
                                          textColor=colors.HexColor("#555555"))),
            Paragraph(indian_group(dr) if dr else "", S["cell_r"]),
            Paragraph(indian_group(cr) if cr else "", S["cell_r"]),
            Paragraph(indian_group(bal), S["cell_r"]),
        ]
        data.append(row)
        if "MERIDIAN" in part:
            meridian_rows.append(len(data) - 1)

    colw = [22 * mm, 58 * mm, 30 * mm, 22 * mm, 22 * mm, 25 * mm]
    tbl = LongTable(data, colWidths=colw, repeatRows=1)
    tstyle = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b4f6c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#999999")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f8fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    # Highlight the Meridian EMI rows so the undisclosed servicing is visible.
    for r in meridian_rows:
        tstyle.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#fff3d6")))
        tstyle.append(("TEXTCOLOR", (1, r), (1, r), colors.HexColor("#8a5b00")))
        tstyle.append(("FONTNAME", (1, r), (1, r), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(tstyle))
    st.append(tbl)

    # Summary page
    st.append(PageBreak())
    st.append(Paragraph("Statement Summary", S["h1"]))
    st.append(Paragraph("Account " + ENTITY["account"] + " &mdash; 01 August 2025 to 31 July 2026",
                        S["small"]))
    st.append(Spacer(1, 8))
    meridian_total = 218750 * 12
    summ = [
        ["Opening Balance (01 Aug 2025)", indian_group(opening)],
        ["Total Credits during period", indian_group(total_cr)],
        ["Total Debits during period", indian_group(total_dr)],
        ["Closing Balance (31 Jul 2026)", indian_group(closing)],
        ["Number of transactions", str(len(txns))],
        ["Of which: MERIDIAN BANK EMI DR (12 x 2,18,750)", indian_group(meridian_total)],
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
        ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#fff3d6")),
    ]))
    st.append(stb)
    st.append(Spacer(1, 10))
    st.append(Paragraph(
        "This statement pertains to current account " + ENTITY["account"] + " only. No other "
        "account of the constituent is maintained at or reported by this branch.", S["small"]))
    st.append(Paragraph(
        "Computer-generated statement. Reconciled to the general ledger of Continental Commercial "
        "Bank, Coimbatore SME Branch.", S["small"]))

    return st


def build_ca_statement(outdir):
    S = styles()
    opening, closing, total_dr, total_cr, txns = _gen_transactions()
    factory = lambda: _ca_story(S, opening, closing, total_dr, total_cr, txns)
    path = os.path.join(outdir, "Southgate_CCB_CA_Statements_12m.pdf")
    n = build_auto(path, factory, title="Current Account Statement (Specimen)")
    return path, n
