"""
Priority group three: the clean (satisfied) documents.
  8.  Certificate of Incorporation
  9.  Memorandum & Articles of Association (abbreviated)
  10. Entity PAN allotment intimation letter
  11. Director KYC summary sheets x2 (masked identifiers)
  12. Audited financial statements FY2024
  13. Audited financial statements FY2025
  14. ITR acknowledgements + computation summaries FY2024 & FY2025
"""
import os

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable,
)

from common import build_document, build_auto, styles, letterhead, indian_group, ENTITY, DIRECTORS
import financials as F


def g(x):
    return indian_group(x)


def _kv_table(rows, S, colw=(52 * mm, 108 * mm), shade_key=True):
    data = [[Paragraph(k, S["cell_b"]), Paragraph(v, S["cell"])] for k, v in rows]
    t = Table(data, colWidths=list(colw))
    stl = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9bbfd0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfe1ea")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if shade_key:
        stl.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef5f8")))
    t.setStyle(TableStyle(stl))
    return t


def _fin_table(rows, S, colw, header, total_rows=None, section_rows=None):
    """Financial statement table: label col + one or two amount cols."""
    data = [[Paragraph(header[0], S["cell_b"])] +
            [Paragraph(h, S["cell_rb"]) for h in header[1:]]]
    for r in rows:
        data.append([Paragraph(r[0], S["cell"])] +
                    [Paragraph(v, S["cell_r"]) for v in r[1:]])
    t = Table(data, colWidths=colw, repeatRows=1)
    stl = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20406a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d0d0")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#888888")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for r in (total_rows or []):
        stl.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#eef2f7")))
        stl.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))
    for r in (section_rows or []):
        stl.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#dbe4ef")))
        stl.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))
    t.setStyle(TableStyle(stl))
    return t


# --------------------------------------------------------------------------- #
# 8. Certificate of Incorporation
# --------------------------------------------------------------------------- #
def build_coi(outdir):
    S = styles()
    st = []
    st.append(Paragraph("Government of India", ParagraphStyle(
        "coi_g", parent=S["subtitle"], fontSize=11, spaceAfter=0)))
    st.append(Paragraph("Ministry of Corporate Affairs", S["subtitle"]))
    st.append(Paragraph("Office of the Registrar of Companies, Coimbatore, Tamil Nadu",
                        S["small"]))
    st.append(Spacer(1, 6))
    st.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#20406a"),
                         spaceBefore=2, spaceAfter=8))
    st.append(Paragraph("CERTIFICATE OF INCORPORATION",
                        ParagraphStyle("coi_t", parent=S["title"], fontSize=16)))
    st.append(Paragraph("[Pursuant to sub-section (2) of section 7 of the Companies Act, 2013 "
                        "and rule 18 of the Companies (Incorporation) Rules, 2014]", S["small"]))
    st.append(Spacer(1, 12))
    st.append(Paragraph(
        "I hereby certify that <b>SOUTHGATE TEXTILES PRIVATE LIMITED</b> is incorporated on this "
        "<b>Eighteenth day of March Two Thousand Sixteen</b> under the Companies Act, 2013 "
        "(18 of 2013) and that the company is limited by shares.", S["body"]))
    st.append(Spacer(1, 8))
    st.append(Paragraph(
        "The Corporate Identity Number of the company is <b>" + ENTITY["cin"] + "</b>.", S["body"]))
    st.append(Paragraph(
        "The Permanent Account Number (PAN) of the company is <b>" + ENTITY["pan"] +
        "</b> and the Tax Deduction and Collection Account Number (TAN) is <b>CMBS12345F</b>.",
        S["body"]))
    st.append(Spacer(1, 10))
    st.append(_kv_table([
        ("Name of Company", ENTITY["name"]),
        ("Corporate Identity Number (CIN)", ENTITY["cin"]),
        ("Permanent Account Number (PAN)", ENTITY["pan"]),
        ("Date of Incorporation", ENTITY["incorp"]),
        ("Registered Office", ENTITY["office"]),
        ("Company Category", "Company limited by shares"),
        ("Company Sub-Category", "Non-government company, Private"),
    ], S))
    st.append(Spacer(1, 18))
    st.append(Paragraph("Given under my hand at Coimbatore this Eighteenth day of March "
                        "Two Thousand Sixteen.", S["body"]))
    st.append(Spacer(1, 24))
    st.append(Paragraph("_____________________________<br/>Registrar of Companies<br/>"
                        "Coimbatore, Tamil Nadu", S["body_l"]))
    st.append(Spacer(1, 10))
    st.append(Paragraph(
        "Note: The corresponding entity is a specimen created for demonstration only. "
        "This certificate does not reproduce any official seal, emblem or security feature.",
        S["small"]))
    path = os.path.join(outdir, "Southgate_Certificate_of_Incorporation.pdf")
    return path, build_document(path, st, page_labels=["Page 1 of 1"],
                                title="Certificate of Incorporation (Specimen)")


# --------------------------------------------------------------------------- #
# 9. Memorandum & Articles of Association (abbreviated)
# --------------------------------------------------------------------------- #
def build_moa_aoa(outdir):
    S = styles()

    def story():
        st = []
        st.append(Paragraph("THE COMPANIES ACT, 2013", S["subtitle"]))
        st.append(Paragraph("Company Limited by Shares", S["subtitle"]))
        st.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#20406a"),
                             spaceBefore=2, spaceAfter=8))
        st.append(Paragraph("MEMORANDUM OF ASSOCIATION OF", S["title"]))
        st.append(Paragraph("SOUTHGATE TEXTILES PRIVATE LIMITED",
                            ParagraphStyle("mt", parent=S["title"], fontSize=14)))
        st.append(Spacer(1, 10))

        st.append(Paragraph("I. NAME CLAUSE", S["h2"]))
        st.append(Paragraph("1. The name of the company is <b>Southgate Textiles Private "
                            "Limited</b>.", S["body"]))
        st.append(Paragraph("II. REGISTERED OFFICE CLAUSE", S["h2"]))
        st.append(Paragraph("2. The registered office of the company will be situated in the "
                            "State of Tamil Nadu.", S["body"]))
        st.append(Paragraph("III. OBJECTS CLAUSE", S["h2"]))
        st.append(Paragraph("3. The objects for which the company is established are:", S["body"]))
        st.append(Paragraph("(A) THE MAIN OBJECTS TO BE PURSUED BY THE COMPANY ON ITS "
                            "INCORPORATION ARE:", ParagraphStyle("ob", parent=S["body"],
                            fontName="Helvetica-Bold")))
        for i, o in enumerate([
            "To carry on in India and elsewhere the business of manufacturers, spinners, weavers, "
            "processors, dyers, printers, converters, importers, exporters, wholesalers, "
            "retailers and dealers in home textiles, furnishing fabrics, made-up textile "
            "articles, bed and bath linen, curtains, upholstery fabrics, yarn, cloth and all "
            "kinds of textile goods, whether made of cotton, silk, wool, jute, synthetic fibres "
            "or any combination thereof.",
            "To set up, establish, operate and maintain factories, weaving and processing units, "
            "dye houses, finishing plants, warehouses and showrooms, and to acquire, install and "
            "operate looms, spinning frames, dyeing and printing machinery and other plant and "
            "equipment required for the manufacture and processing of textiles.",
            "To buy, sell, prepare for market, import, export and deal in raw materials, stores, "
            "dyes, chemicals, packing materials, accessories and other articles required for or "
            "connected with the business of the company.",
        ], 1):
            st.append(Paragraph("%d. %s" % (i, o), S["body"]))

        st.append(PageBreak())
        st.append(Paragraph("(B) MATTERS WHICH ARE NECESSARY FOR FURTHERANCE OF THE OBJECTS "
                            "SPECIFIED IN CLAUSE 3(A) ARE:", ParagraphStyle(
                                "ob2", parent=S["body"], fontName="Helvetica-Bold")))
        for i, o in enumerate([
            "To purchase, take on lease or otherwise acquire and hold any lands, buildings, "
            "plant, machinery and other property, movable or immovable, necessary or convenient "
            "for the purposes of the company.",
            "<b>To borrow or raise money</b> in such manner as the company shall think fit, and "
            "in particular by the issue of debentures, and to secure the repayment of any money "
            "borrowed, raised or owing, by mortgage, charge, hypothecation, pledge or lien upon "
            "the whole or any part of the company's property or assets, whether present or "
            "future, and to guarantee and secure the obligations of the company.",
            "To open accounts with and avail credit facilities from banks and financial "
            "institutions, and to draw, make, accept, endorse, discount and negotiate cheques, "
            "bills of exchange, promissory notes and other negotiable instruments.",
            "To invest and deal with the moneys of the company not immediately required, in such "
            "manner as may from time to time be determined by the Board of Directors.",
            "To do all such other things as are incidental or conducive to the attainment of the "
            "above objects or any of them.",
        ], 1):
            st.append(Paragraph("%d. %s" % (i, o), S["body"]))

        st.append(Paragraph("IV. LIABILITY CLAUSE", S["h2"]))
        st.append(Paragraph("4. The liability of the member(s) is limited and this liability is "
                            "limited to the amount unpaid, if any, on the shares held by them.",
                            S["body"]))
        st.append(Paragraph("V. CAPITAL CLAUSE", S["h2"]))
        st.append(Paragraph(
            "5. The authorised share capital of the company is Rs. 1,50,00,000 (Rupees One Crore "
            "Fifty Lakh only) divided into 15,00,000 equity shares of Rs. 10 (Rupees Ten) each. "
            "The issued, subscribed and paid-up capital is Rs. 1,00,00,000 divided into "
            "10,00,000 equity shares of Rs. 10 each.", S["body"]))

        st.append(PageBreak())
        st.append(Paragraph("VI. SUBSCRIPTION CLAUSE", S["h2"]))
        st.append(Paragraph(
            "We, the several persons whose names and addresses are subscribed below, are "
            "desirous of being formed into a company in pursuance of this Memorandum of "
            "Association, and we respectively agree to take the number of shares in the capital "
            "of the company set opposite our respective names.", S["body"]))
        st.append(Spacer(1, 6))
        subs = [["Name, address, description and occupation of subscriber",
                 "No. of equity shares taken", "Signature"],
                ["Lakshmi Iyer, No. 9, Race Course Road, Coimbatore 641018. "
                 "Occupation: Business.", "5,10,000", "Sd/-"],
                ["Venkat Iyer, No. 9, Race Course Road, Coimbatore 641018. "
                 "Occupation: Business.", "4,90,000", "Sd/-"],
                ["Total", "10,00,000", ""]]
        t = Table([[Paragraph(c, S["cell_b"] if r == 0 else S["cell"]) for c in row]
                   for r, row in enumerate(subs)],
                  colWidths=[104 * mm, 34 * mm, 22 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20406a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#888888")),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2f7")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        st.append(t)
        st.append(Spacer(1, 6))
        st.append(Paragraph("Dated this 10th day of March 2016. Witness to the above "
                            "signatures: S. Ramanathan, Company Secretary.", S["small"]))

        st.append(PageBreak())
        # ---- Articles of Association ----
        st.append(Paragraph("ARTICLES OF ASSOCIATION OF", S["title"]))
        st.append(Paragraph("SOUTHGATE TEXTILES PRIVATE LIMITED",
                            ParagraphStyle("at", parent=S["title"], fontSize=14)))
        st.append(HRFlowable(width="100%", thickness=1.0, color=colors.HexColor("#20406a"),
                             spaceBefore=4, spaceAfter=8))
        st.append(Paragraph("PRELIMINARY", S["h2"]))
        arts = [
            ("1. Company as a Private Company",
             "The company is a private company within the meaning of Section 2(68) of the "
             "Companies Act, 2013, and accordingly (a) restricts the right to transfer its "
             "shares; (b) limits the number of its members to two hundred; and (c) prohibits any "
             "invitation to the public to subscribe for any securities of the company."),
            ("2. Table F",
             "The regulations contained in Table F in Schedule I to the Companies Act, 2013 shall "
             "apply to the company except in so far as they are excluded or modified by these "
             "Articles."),
            ("3. Share Capital",
             "The share capital of the company is as stated in the Capital Clause of the "
             "Memorandum of Association. Subject to the provisions of the Act, the shares shall "
             "be under the control of the Board who may allot or otherwise dispose of the same."),
        ]
        for h, b in arts:
            st.append(Paragraph(h, S["h2"]))
            st.append(Paragraph(b, S["body"]))

        st.append(Paragraph("BORROWING POWERS", S["h2"]))
        st.append(Paragraph(
            "84. Subject to the provisions of Sections 73 to 76, 179 and 180 of the Companies "
            "Act, 2013, the Board of Directors may from time to time, at its discretion, by a "
            "resolution passed at a meeting of the Board, <b>borrow, raise or secure the payment "
            "of any sum or sums of money</b> for the purposes of the company from any bank, "
            "financial institution or other person, and may secure the repayment thereof by "
            "mortgage, charge, hypothecation or pledge over all or any of the property or assets "
            "of the company, whether present or future.", S["body"]))
        st.append(Paragraph(
            "85. The Board may, by a resolution under Section 179(3)(d) of the Act, delegate to "
            "any director or committee the power to borrow moneys and to create such security, "
            "within the limits and on the terms authorised by the Board.", S["body"]))

        st.append(PageBreak())
        st.append(Paragraph("DIRECTORS", S["h2"]))
        for h, b in [
            ("90. Number of Directors",
             "The number of directors of the company shall not be less than two and not more "
             "than fifteen. The first directors of the company are Smt. Lakshmi Iyer and Sri. "
             "Venkat Iyer."),
            ("91. Powers of the Board",
             "The business of the company shall be managed by the Board of Directors, who may "
             "exercise all such powers of the company as are not, by the Act or these Articles, "
             "required to be exercised by the company in general meeting."),
            ("112. Winding Up",
             "Subject to the provisions of the Act, if the company shall be wound up, the assets "
             "remaining after payment of the debts and liabilities shall be distributed among "
             "the members in proportion to the capital paid up on the shares held by them."),
        ]:
            st.append(Paragraph(h, S["h2"]))
            st.append(Paragraph(b, S["body"]))

        st.append(PageBreak())
        st.append(Paragraph("TRANSFER AND TRANSMISSION OF SHARES", S["h2"]))
        for h, b in [
            ("30. Restriction on transfer",
             "The Board may, in its absolute discretion and without assigning any reason, decline "
             "to register any transfer of shares. No shares shall be transferred to a person who "
             "is not a member so long as any member is willing to purchase the same at fair "
             "value, in accordance with the pre-emption procedure set out in these Articles."),
            ("31. Transmission",
             "On the death of a member, the survivor or survivors where the member was a joint "
             "holder, and the legal representatives of the deceased where he was a sole holder, "
             "shall be the only persons recognised by the company as having any title to his "
             "interest in the shares."),
        ]:
            st.append(Paragraph(h, S["h2"]))
            st.append(Paragraph(b, S["body"]))
        st.append(Paragraph("GENERAL MEETINGS AND DIVIDENDS", S["h2"]))
        for h, b in [
            ("48. General meetings",
             "The company shall in each year hold a general meeting as its annual general meeting "
             "in addition to any other meetings in that year. Not more than fifteen months shall "
             "elapse between the date of one annual general meeting and that of the next."),
            ("70. Dividends",
             "The company in general meeting may declare dividends, but no dividend shall exceed "
             "the amount recommended by the Board. The Board may from time to time pay to the "
             "members such interim dividends as appear to it to be justified by the profits of "
             "the company."),
            ("78. Accounts and audit",
             "The Board shall cause proper books of account to be kept, and the accounts of the "
             "company shall be audited by a qualified auditor appointed in accordance with the "
             "provisions of the Companies Act, 2013."),
        ]:
            st.append(Paragraph(h, S["h2"]))
            st.append(Paragraph(b, S["body"]))

        st.append(Spacer(1, 10))
        st.append(Paragraph("We, the subscribers to the Memorandum of Association, are desirous "
                            "of being formed into a company in pursuance of these Articles of "
                            "Association.", S["body"]))
        st.append(Spacer(1, 10))
        st.append(_kv_table([
            ("Subscriber 1", "Lakshmi Iyer &mdash; Sd/-"),
            ("Subscriber 2", "Venkat Iyer &mdash; Sd/-"),
            ("Dated", "10 March 2016, Coimbatore"),
            ("Witness", "S. Ramanathan, Company Secretary"),
        ], S))
        return st

    path = os.path.join(outdir, "Southgate_MOA_AOA.pdf")
    return path, build_auto(path, story, title="Memorandum and Articles of Association (Specimen)")


# --------------------------------------------------------------------------- #
# 10. Entity PAN allotment intimation letter
# --------------------------------------------------------------------------- #
def build_pan_letter(outdir):
    S = styles()
    st = []
    st.append(Paragraph("Income Tax Department", ParagraphStyle(
        "pan_g", parent=S["subtitle"], fontSize=11, spaceAfter=0)))
    st.append(Paragraph("Government of India", S["subtitle"]))
    st.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#20406a"),
                         spaceBefore=2, spaceAfter=8))
    st.append(Paragraph("INTIMATION OF ALLOTMENT OF PERMANENT ACCOUNT NUMBER (PAN)",
                        ParagraphStyle("pan_t", parent=S["h1"], alignment=TA_CENTER)))
    st.append(Spacer(1, 4))
    st.append(Paragraph("Date: 24 March 2016 &nbsp;&nbsp;|&nbsp;&nbsp; "
                        "Ref: PAN/ALLOT/2016/TZ/00427431", S["small"]))
    st.append(Spacer(1, 8))
    st.append(Paragraph("To,<br/><b>Southgate Textiles Private Limited</b><br/>" +
                        ENTITY["office"], S["body_l"]))
    st.append(Spacer(1, 6))
    st.append(Paragraph("Sir / Madam,", S["body_l"]))
    st.append(Paragraph(
        "With reference to your application for allotment of a Permanent Account Number, this is "
        "to intimate that the following Permanent Account Number (PAN) has been allotted to you "
        "by the Income Tax Department under the Income-tax Act, 1961.", S["body"]))
    st.append(Spacer(1, 8))
    st.append(_kv_table([
        ("Permanent Account Number (PAN)", "<b>" + ENTITY["pan"] + "</b>"),
        ("Name", ENTITY["name"]),
        ("Status", "Company"),
        ("Date of Incorporation / Formation", ENTITY["incorp"]),
        ("Assessing Officer / Ward", "Circle 1(1), Coimbatore"),
        ("CIN", ENTITY["cin"]),
    ], S))
    st.append(Spacer(1, 10))
    st.append(Paragraph(
        "You are requested to quote this Permanent Account Number in all returns, correspondence "
        "and challans filed with the Income Tax Department, and in all documents pertaining to "
        "the financial transactions notified from time to time.", S["body"]))
    st.append(Spacer(1, 8))
    st.append(Paragraph("This is a computer-generated intimation letter and is issued in lieu of "
                        "a PAN card image. No signature is required.", S["small"]))
    st.append(Spacer(1, 14))
    st.append(Paragraph("For Income Tax Department", S["body_l"]))
    st.append(Spacer(1, 6))
    st.append(Paragraph("(System generated)", S["small"]))
    path = os.path.join(outdir, "Southgate_Entity_PAN.pdf")
    return path, build_document(path, st, page_labels=["Page 1 of 1"],
                                title="PAN Allotment Intimation (Specimen)")


# --------------------------------------------------------------------------- #
# 11. Director KYC summary sheets x2 (masked identifiers)
# --------------------------------------------------------------------------- #
def build_director_kyc(outdir):
    S = styles()
    st = []
    for idx, d in enumerate(DIRECTORS):
        if idx:
            st.append(PageBreak())
        st += letterhead(S, tagline=False)
        st.append(Paragraph("DIRECTOR KYC SUMMARY SHEET",
                            ParagraphStyle("kyc_t", parent=S["h1"], alignment=TA_CENTER)))
        st.append(Paragraph("Prepared for submission to Continental Commercial Bank, "
                            "Coimbatore SME Branch", S["subtitle"]))
        st.append(HRFlowable(width="100%", thickness=0.9, color=colors.HexColor("#20406a"),
                             spaceBefore=2, spaceAfter=8))
        st.append(_kv_table([
            ("Name of Director", d["name"]),
            ("Designation", d["role"]),
            ("Director Identification Number (DIN)", d["din"]),
            ("Date of Birth", d["dob"]),
            ("Residential Address", d["address"]),
            ("Nationality", "Indian"),
            ("PAN (masked)", d["pan_masked"]),
            ("Aadhaar (masked)", d["aadhaar_masked"]),
            ("Relationship with company", "Promoter and Director"),
        ], S))
        st.append(Spacer(1, 8))
        st.append(Paragraph(
            "Note: Personal identifiers are shown in masked form in accordance with data "
            "minimisation practice. Full identifiers are retained on the KYC file and are "
            "produced to the bank only on specific request under its verification procedure.",
            S["small"]))
        st.append(Spacer(1, 16))
        st.append(Paragraph("Verified by (Branch official): _____________________________",
                            S["body_l"]))
        st.append(Spacer(1, 6))
        st.append(Paragraph("Date of verification: ____ / ____ / 2026", S["body_l"]))
    path = os.path.join(outdir, "Southgate_Director_KYC_Iyer_x2.pdf")
    labels = ["Page 1 of 2", "Page 2 of 2"]
    return path, build_document(path, st, page_labels=labels,
                                title="Director KYC Summary (Specimen)")


# --------------------------------------------------------------------------- #
# 12 & 13. Audited financial statements
# --------------------------------------------------------------------------- #
def _audited_fs(outdir, filename, cur, prev, pl_cur, pl_prev, bs_cur, bs_prev, cf,
                sign_date, ay_note):
    S = styles()
    curlabel = cur["year_end"]
    prevlabel = prev["year_end"]

    def story():
        st = []
        # ---- Title page ----
        st += letterhead(S, tagline=False)
        st.append(Spacer(1, 20))
        st.append(Paragraph("AUDITED FINANCIAL STATEMENTS",
                            ParagraphStyle("fs_t", parent=S["title"], fontSize=17)))
        st.append(Paragraph("For the year ended " + curlabel,
                            ParagraphStyle("fs_st", parent=S["subtitle"], fontSize=12)))
        st.append(Spacer(1, 24))
        st.append(_kv_table([
            ("Company", ENTITY["name"]),
            ("CIN", ENTITY["cin"]),
            ("PAN", ENTITY["pan"]),
            ("Financial Year", cur["label"] + " (ended " + curlabel + ")"),
            ("Comparative Year", prev["label"] + " (ended " + prevlabel + ")"),
            ("Statutory Auditors", "M/s. Rangaswamy & Associates, Chartered Accountants"),
            ("Firm Registration No.", "004512S"),
        ], S))
        st.append(Spacer(1, 20))
        st.append(Paragraph("Contents: Independent Auditor's Report; Balance Sheet; Statement "
                            "of Profit and Loss; Cash Flow Statement; Notes to the Financial "
                            "Statements.", S["small"]))

        # ---- Independent Auditor's Report ----
        st.append(PageBreak())
        st.append(Paragraph("INDEPENDENT AUDITOR'S REPORT", S["h1"]))
        st.append(Paragraph("To the Members of Southgate Textiles Private Limited", S["h2"]))
        st.append(Paragraph("Report on the Audit of the Financial Statements", S["h2"]))
        st.append(Paragraph("Opinion", S["h2"]))
        st.append(Paragraph(
            "We have audited the accompanying financial statements of Southgate Textiles Private "
            "Limited (\"the Company\"), which comprise the Balance Sheet as at " + curlabel +
            ", the Statement of Profit and Loss and the Cash Flow Statement for the year then "
            "ended, and notes to the financial statements, including a summary of significant "
            "accounting policies and other explanatory information.", S["body"]))
        st.append(Paragraph(
            "In our opinion and to the best of our information and according to the explanations "
            "given to us, the aforesaid financial statements give the information required by the "
            "Companies Act, 2013 in the manner so required and give a true and fair view in "
            "conformity with the accounting principles generally accepted in India, of the state "
            "of affairs of the Company as at " + curlabel + ", and its profit and its cash flows "
            "for the year ended on that date.", S["body"]))
        st.append(Paragraph("Basis for Opinion", S["h2"]))
        st.append(Paragraph(
            "We conducted our audit in accordance with the Standards on Auditing (SAs) specified "
            "under section 143(10) of the Companies Act, 2013. Our responsibilities under those "
            "Standards are further described in the Auditor's Responsibilities section of our "
            "report. We are independent of the Company in accordance with the Code of Ethics "
            "issued by the Institute of Chartered Accountants of India, and we have fulfilled "
            "our other ethical responsibilities in accordance therewith. We believe that the "
            "audit evidence we have obtained is sufficient and appropriate to provide a basis "
            "for our opinion.", S["body"]))
        st.append(Paragraph("Management's Responsibility for the Financial Statements", S["h2"]))
        st.append(Paragraph(
            "The Company's Board of Directors is responsible for the matters stated in section "
            "134(5) of the Companies Act, 2013 with respect to the preparation of these financial "
            "statements that give a true and fair view of the financial position, financial "
            "performance and cash flows of the Company in accordance with the accounting "
            "principles generally accepted in India.", S["body"]))
        st.append(PageBreak())
        st.append(Paragraph("Auditor's Responsibilities for the Audit of the Financial "
                            "Statements", S["h2"]))
        st.append(Paragraph(
            "Our objectives are to obtain reasonable assurance about whether the financial "
            "statements as a whole are free from material misstatement, whether due to fraud or "
            "error, and to issue an auditor's report that includes our opinion. Reasonable "
            "assurance is a high level of assurance, but is not a guarantee that an audit "
            "conducted in accordance with SAs will always detect a material misstatement when it "
            "exists.", S["body"]))
        st.append(Paragraph("Report on Other Legal and Regulatory Requirements", S["h2"]))
        st.append(Paragraph(
            "As required by the Companies (Auditor's Report) Order, 2020 (\"the Order\"), issued "
            "by the Central Government in terms of section 143(11) of the Act, we give in the "
            "Annexure a statement on the matters specified in paragraphs 3 and 4 of the Order, to "
            "the extent applicable. In our opinion, proper books of account as required by law "
            "have been kept by the Company, and the Balance Sheet, the Statement of Profit and "
            "Loss and the Cash Flow Statement dealt with by this report are in agreement with the "
            "books of account.", S["body"]))
        st.append(Spacer(1, 20))
        st.append(Paragraph("For M/s. Rangaswamy & Associates<br/>Chartered Accountants<br/>"
                            "Firm Registration No. 004512S", S["body_l"]))
        st.append(Spacer(1, 18))
        st.append(Paragraph("Sd/-<br/>CA. S. Rangaswamy (Partner)<br/>Membership No. 214536<br/>"
                            "Place: Coimbatore &nbsp;|&nbsp; Date: " + sign_date, S["body_l"]))

        # ---- CARO 2020 Annexure ----
        st.append(PageBreak())
        st.append(Paragraph("ANNEXURE 'A' TO THE INDEPENDENT AUDITOR'S REPORT", S["h1"]))
        st.append(Paragraph("Referred to in our report of even date, on the matters specified in "
                            "the Companies (Auditor's Report) Order, 2020", S["small"]))
        for h, b in [
            ("(i) Property, plant and equipment",
             "The Company has maintained proper records showing full particulars, including "
             "quantitative details and situation, of property, plant and equipment. The assets "
             "have been physically verified by the management at reasonable intervals and no "
             "material discrepancies were noticed. The title deeds of immovable property are held "
             "in the name of the Company."),
            ("(ii) Inventory",
             "The inventory has been physically verified by the management at reasonable intervals "
             "and the discrepancies noticed on verification, which were not material, have been "
             "properly dealt with in the books of account."),
            ("(iii) Loans and investments",
             "The Company has not made any investments in, or granted any loans or advances in the "
             "nature of loans, secured or unsecured, to companies, firms, limited liability "
             "partnerships or other parties requiring reporting under this clause."),
            ("(vii) Statutory dues",
             "The Company is regular in depositing undisputed statutory dues including goods and "
             "services tax, provident fund, employees' state insurance, income-tax and other "
             "material statutory dues with the appropriate authorities. There are no undisputed "
             "amounts payable in arrears as at the balance sheet date for a period of more than "
             "six months from the date they became payable."),
            ("(ix) Repayment of borrowings",
             "In our opinion and according to the information and explanations given to us, the "
             "Company has not defaulted in the repayment of loans or borrowings to any lender."),
        ]:
            st.append(Paragraph(h, S["h2"]))
            st.append(Paragraph(b, S["body"]))
        st.append(Spacer(1, 14))
        st.append(Paragraph("For M/s. Rangaswamy & Associates, Chartered Accountants "
                            "(FRN 004512S) &mdash; Sd/- CA. S. Rangaswamy (Partner), M.No. 214536. "
                            "Place: Coimbatore, Date: " + sign_date, S["small"]))

        # ---- Balance Sheet ----
        st.append(PageBreak())
        st.append(Paragraph("BALANCE SHEET AS AT " + curlabel.upper(), S["h1"]))
        st.append(Paragraph("(All amounts in Indian Rupees)", S["small"]))
        c, p = bs_cur, bs_prev
        header = ["Particulars", "As at " + curlabel, "As at " + prevlabel]
        rows = [
            ["I. EQUITY AND LIABILITIES", "", ""],
            ["(1) Shareholders' funds", "", ""],
            ["      (a) Share capital", g(c["share_capital"]), g(p["share_capital"])],
            ["      (b) Reserves and surplus", g(c["reserves"]), g(p["reserves"])],
            ["(2) Non-current liabilities", "", ""],
            ["      (a) Long-term borrowings", g(c["borrowings_lt"]), g(p["borrowings_lt"])],
            ["      (b) Deferred tax liabilities (net)", g(c["dtl"]), g(p["dtl"])],
            ["(3) Current liabilities", "", ""],
            ["      (a) Short-term borrowings", g(c["borrowings_st"]), g(p["borrowings_st"])],
            ["      (b) Trade payables", g(c["trade_payables"]), g(p["trade_payables"])],
            ["      (c) Other current liabilities", g(c["other_cl"]), g(p["other_cl"])],
            ["      (d) Short-term provisions", g(c["provisions"]), g(p["provisions"])],
            ["      TOTAL", g(c["total"]), g(p["total"])],
            ["II. ASSETS", "", ""],
            ["(1) Non-current assets", "", ""],
            ["      (a) Property, plant and equipment", g(c["ppe"]), g(p["ppe"])],
            ["      (b) Intangible assets", g(c["intangibles"]), g(p["intangibles"])],
            ["      (c) Long-term loans and advances", g(c["lt_loans"]), g(p["lt_loans"])],
            ["(2) Current assets", "", ""],
            ["      (a) Inventories", g(c["inventories"]), g(p["inventories"])],
            ["      (b) Trade receivables", g(c["receivables"]), g(p["receivables"])],
            ["      (c) Cash and bank balances", g(c["cash"]), g(p["cash"])],
            ["      (d) Short-term loans and advances", g(c["st_loans"]), g(p["st_loans"])],
            ["      TOTAL", g(c["total"]), g(p["total"])],
        ]
        section_rows = [1, 2, 5, 8, 14, 15, 19]  # sub-headings (0-based incl header offset)
        # account for header row at index 0 -> shift by 1
        st.append(_fin_table(rows, S, [96 * mm, 32 * mm, 32 * mm], header,
                             total_rows=[13, 24],
                             section_rows=[1, 2, 5, 8, 14, 15, 19]))
        st.append(Spacer(1, 5))
        st.append(Paragraph("Net worth (share capital + reserves and surplus): Rs. " +
                            g(cur["net_worth"]) + " (previous year Rs. " + g(prev["net_worth"]) +
                            "). The notes referred to above form an integral part of the "
                            "financial statements.", S["small"]))

        # ---- Statement of P&L ----
        st.append(PageBreak())
        st.append(Paragraph("STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED " +
                            curlabel.upper(), S["h1"]))
        st.append(Paragraph("(All amounts in Indian Rupees)", S["small"]))
        tot_exp_cur = pl_cur["total_opex"] + pl_cur["finance_costs"] + pl_cur["depreciation"]
        tot_exp_prev = pl_prev["total_opex"] + pl_prev["finance_costs"] + pl_prev["depreciation"]
        plrows = [
            ["I. Revenue from operations", g(cur["revenue"]), g(prev["revenue"])],
            ["II. Other income", g(pl_cur["other_income"]), g(pl_prev["other_income"])],
            ["III. Total income (I + II)", g(pl_cur["total_income"]), g(pl_prev["total_income"])],
            ["IV. Expenses:", "", ""],
            ["      Cost of materials consumed", g(pl_cur["materials"]), g(pl_prev["materials"])],
            ["      Changes in inventories of FG and WIP", g(pl_cur["change_inv"]),
             g(pl_prev["change_inv"])],
            ["      Employee benefits expense", g(pl_cur["employee"]), g(pl_prev["employee"])],
            ["      Finance costs", g(pl_cur["finance_costs"]), g(pl_prev["finance_costs"])],
            ["      Depreciation and amortisation", g(pl_cur["depreciation"]),
             g(pl_prev["depreciation"])],
            ["      Other expenses", g(pl_cur["other_exp"]), g(pl_prev["other_exp"])],
            ["      Total expenses", g(tot_exp_cur), g(tot_exp_prev)],
            ["V. Profit before tax (III - IV)", g(pl_cur["pbt"]), g(pl_prev["pbt"])],
            ["VI. Tax expense (current and deferred)", g(pl_cur["tax"]), g(pl_prev["tax"])],
            ["VII. Profit for the year (V - VI)", g(cur["pat"]), g(prev["pat"])],
        ]
        st.append(_fin_table(plrows, S, [96 * mm, 32 * mm, 32 * mm], header=[
            "Particulars", "Year ended " + curlabel, "Year ended " + prevlabel],
            total_rows=[3, 11, 14], section_rows=[4]))
        st.append(Spacer(1, 5))
        st.append(Paragraph(
            "EBITDA (earnings before interest, tax, depreciation and amortisation) for the year: "
            "Rs. " + g(cur["ebitda"]) + " (previous year Rs. " + g(prev["ebitda"]) + "). "
            "Earnings per equity share (face value Rs. 10): Rs. " +
            ("%.2f" % (cur["pat"] / 1000000.0)) + ".", S["small"]))

        # ---- Cash Flow ----
        st.append(PageBreak())
        st.append(Paragraph("CASH FLOW STATEMENT FOR THE YEAR ENDED " + curlabel.upper(), S["h1"]))
        st.append(Paragraph("(Indirect method; all amounts in Indian Rupees)", S["small"]))
        cfrows = [
            ["A. Cash flow from operating activities", ""],
            ["      Profit before tax", g(pl_cur["pbt"])],
            ["      Adjustments: depreciation and amortisation", g(pl_cur["depreciation"])],
            ["      Adjustments: finance costs", g(pl_cur["finance_costs"])],
            ["      Operating profit before working capital changes", g(cf["op_before_wc"])],
            ["      Changes in working capital (net)", g(cf["wc_change"])],
            ["      Direct taxes paid", g(-cf["taxes_paid"])],
            ["      Net cash from operating activities (A)", g(cf["op_cash"])],
            ["B. Cash flow from investing activities", ""],
            ["      Purchase of property, plant and equipment", g(cf["capex"])],
            ["      Movement in intangibles and long-term advances",
             g(cf["d_intang"] + cf["d_ltloan"])],
            ["      Net cash used in investing activities (B)", g(cf["inv_cash"])],
            ["C. Cash flow from financing activities", ""],
            ["      Net borrowings, interest paid and other financing", g(cf["fin_cash"])],
            ["      Net cash from financing activities (C)", g(cf["fin_cash"])],
            ["Net increase / (decrease) in cash (A + B + C)", g(cf["net_change"])],
            ["Cash and cash equivalents at beginning of year", g(cf["open_cash"])],
            ["Cash and cash equivalents at end of year", g(cf["close_cash"])],
        ]
        st.append(_fin_table(cfrows, S, [128 * mm, 34 * mm],
                             header=["Particulars", "Year ended " + curlabel],
                             total_rows=[7, 11, 14, 15, 17],
                             section_rows=[0, 8, 12]))

        # ---- Notes ----
        st.append(PageBreak())
        st.append(Paragraph("NOTES TO THE FINANCIAL STATEMENTS", S["h1"]))
        st.append(Paragraph("1. Corporate information", S["h2"]))
        st.append(Paragraph(
            "Southgate Textiles Private Limited (CIN " + ENTITY["cin"] + ") is a private limited "
            "company incorporated on " + ENTITY["incorp"] + " under the Companies Act, 2013 and "
            "domiciled in India. The Company is engaged in the manufacture and sale of home "
            "textiles and furnishing fabrics. Its registered office is at " + ENTITY["office"] +
            ".", S["body"]))
        st.append(Paragraph("2. Significant accounting policies", S["h2"]))
        for pol in [
            "(a) Basis of preparation: The financial statements are prepared under the historical "
            "cost convention on the accrual basis of accounting and comply in all material "
            "respects with the applicable accounting standards.",
            "(b) Revenue recognition: Revenue from sale of goods is recognised on transfer of "
            "significant risks and rewards of ownership to the buyer, net of returns, discounts "
            "and goods and services tax.",
            "(c) Property, plant and equipment: Stated at cost less accumulated depreciation. "
            "Depreciation is provided on the written down value method over the useful lives "
            "prescribed under Schedule II to the Companies Act, 2013.",
            "(d) Inventories: Valued at the lower of cost and net realisable value, cost being "
            "determined on a weighted average basis.",
            "(e) Taxes on income: Current tax is measured at the amount expected to be paid to "
            "the tax authorities. Deferred tax is recognised on timing differences between "
            "accounting and taxable income.",
        ]:
            st.append(Paragraph(pol, S["body"]))
        st.append(Paragraph("3. Contingent liabilities and commitments", S["h2"]))
        st.append(Paragraph(
            "Estimated amount of contracts remaining to be executed on capital account (net of "
            "advances): Rs. Nil (previous year Rs. Nil). There are no contingent liabilities not "
            "provided for as at " + curlabel + ".", S["body"]))
        st.append(Paragraph("4. " + ay_note, S["body"]))

        # ---- Supporting schedules page ----
        st.append(PageBreak())
        st.append(Paragraph("NOTES TO THE FINANCIAL STATEMENTS (continued)", S["h1"]))
        c, p = bs_cur, bs_prev
        st.append(Paragraph("5. Share capital and reserves", S["h2"]))
        st.append(_fin_table([
            ["Authorised: 15,00,000 equity shares of Rs. 10 each", g(15000000), g(15000000)],
            ["Issued, subscribed and paid-up: 10,00,000 shares of Rs. 10", g(c["share_capital"]),
             g(p["share_capital"])],
            ["Reserves and surplus (surplus in statement of P&L)", g(c["reserves"]),
             g(p["reserves"])],
            ["Net worth", g(cur["net_worth"]), g(prev["net_worth"])],
        ], S, [96 * mm, 32 * mm, 32 * mm], header=["Particulars", curlabel, prevlabel],
            total_rows=[3]))
        st.append(Spacer(1, 6))
        st.append(Paragraph("6. Borrowings", S["h2"]))
        st.append(_fin_table([
            ["Long-term borrowings (secured term loans and hire purchase)",
             g(c["borrowings_lt"]), g(p["borrowings_lt"])],
            ["Short-term borrowings (working capital)", g(c["borrowings_st"]),
             g(p["borrowings_st"])],
            ["Total borrowings", g(c["borrowings_lt"] + c["borrowings_st"]),
             g(p["borrowings_lt"] + p["borrowings_st"])],
        ], S, [96 * mm, 32 * mm, 32 * mm], header=["Particulars", curlabel, prevlabel],
            total_rows=[2]))
        st.append(Spacer(1, 6))
        st.append(Paragraph("7. Property, plant and equipment (net block)", S["h2"]))
        st.append(_fin_table([
            ["Factory building", g(round(c["ppe"] * 0.45)), g(round(p["ppe"] * 0.45))],
            ["Plant and machinery (looms, dyeing and processing)",
             g(round(c["ppe"] * 0.42)), g(round(p["ppe"] * 0.42))],
            ["Furniture, fixtures, vehicles and office equipment",
             g(c["ppe"] - round(c["ppe"] * 0.45) - round(c["ppe"] * 0.42)),
             g(p["ppe"] - round(p["ppe"] * 0.45) - round(p["ppe"] * 0.42))],
            ["Net block", g(c["ppe"]), g(p["ppe"])],
        ], S, [96 * mm, 32 * mm, 32 * mm], header=["Particulars", curlabel, prevlabel],
            total_rows=[3]))
        st.append(Spacer(1, 6))
        st.append(Paragraph("8. Related party disclosures", S["h2"]))
        st.append(Paragraph(
            "Key management personnel: Smt. Lakshmi Iyer (Managing Director) and Sri. Venkat Iyer "
            "(Director). Transactions with key management personnel during the year comprised "
            "managerial remuneration paid in the ordinary course, on terms not less favourable to "
            "the Company than those available in arm's length transactions.", S["body"]))

        st.append(Spacer(1, 16))
        st.append(Paragraph("For and on behalf of the Board of Directors", S["body_l"]))
        st.append(Spacer(1, 18))
        sig = Table([
            [Paragraph("Sd/-<br/><b>Lakshmi Iyer</b><br/>Managing Director (DIN 07421683)",
                       S["cell"]),
             Paragraph("Sd/-<br/><b>Venkat Iyer</b><br/>Director (DIN 07421699)", S["cell"])],
        ], colWidths=[78 * mm, 78 * mm])
        sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        st.append(sig)
        st.append(Spacer(1, 8))
        st.append(Paragraph("Place: Coimbatore &nbsp;|&nbsp; Date: " + sign_date, S["small"]))
        return st

    path = os.path.join(outdir, filename)
    return path, build_auto(path, story, title="Audited Financial Statements (Specimen)")


def build_audited_fy2024(outdir):
    return _audited_fs(
        outdir, "Southgate_Audited_FS_FY2024.pdf",
        cur=F.FY2024, prev=F.FY2023,
        pl_cur=F.pl_fy2024(), pl_prev=F.pl_fy2023(),
        bs_cur=F.bs_fy2024(), bs_prev=F.bs_fy2023(),
        cf=F.cash_flow(F.bs_fy2024(), F.bs_fy2023(), F.pl_fy2024()),
        sign_date="27 August 2024",
        ay_note="The return of income for the assessment year 2024-25 has been filed within the "
                "prescribed due date. These statements are prepared for that year.")


def build_audited_fy2025(outdir):
    return _audited_fs(
        outdir, "Southgate_Audited_FS_FY2025.pdf",
        cur=F.FY2025, prev=F.FY2024,
        pl_cur=F.pl_fy2025(), pl_prev=F.pl_fy2024(),
        bs_cur=F.bs_fy2025(), bs_prev=F.bs_fy2024(),
        cf=F.cash_flow(F.bs_fy2025(), F.bs_fy2024(), F.pl_fy2025()),
        sign_date="29 August 2025",
        ay_note="The return of income for the assessment year 2025-26 has been filed within the "
                "prescribed due date. The comparative figures are for the year ended 31 March "
                "2024.")


# --------------------------------------------------------------------------- #
# 14. ITR acknowledgements + computation summaries FY2024 & FY2025
# --------------------------------------------------------------------------- #
def build_itr(outdir):
    S = styles()

    def ack_page(fy, ay, ack_no, filed, pl):
        blk = []
        blk.append(Paragraph("INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT",
                            ParagraphStyle("itr_t", parent=S["h1"], alignment=TA_CENTER)))
        blk.append(Paragraph("[Where the data of the Return of Income has been filed "
                            "electronically and verified] &mdash; Form ITR-6", S["small"]))
        blk.append(HRFlowable(width="100%", thickness=1.0, color=colors.HexColor("#20406a"),
                             spaceBefore=2, spaceAfter=8))
        total_income = pl["pbt"]  # taxable income (no material adjustments)
        tax = pl["tax"]
        blk.append(_kv_table([
            ("Assessment Year", ay),
            ("Name", ENTITY["name"]),
            ("PAN", ENTITY["pan"]),
            ("Status", "Private Company (Domestic)"),
            ("Form Number", "ITR-6"),
            ("Filed u/s", "139(1) - On or before due date"),
            ("e-Filing Acknowledgement Number", ack_no),
            ("Total Income", "Rs. " + g(total_income)),
            ("Total Tax and Interest Payable", "Rs. " + g(tax)),
            ("Taxes Paid (TDS + Advance + Self-Assessment)", "Rs. " + g(tax)),
            ("Tax Payable / (Refund)", "Rs. 0"),
            ("Date of Filing", filed),
            ("Mode of Verification", "e-Verified (Aadhaar OTP of authorised signatory)"),
        ], S))
        blk.append(Spacer(1, 10))
        blk.append(Paragraph(
            "This acknowledgement pertains to the return of income filed for the " + fy +
            " (assessment year " + ay + ") and is consistent with the audited financial "
            "statements for that year.", S["small"]))
        blk.append(Spacer(1, 8))
        blk.append(Paragraph("(This is a computer-generated acknowledgement. No signature is "
                            "required.)", S["small"]))
        return blk

    def comp_page(fy, ay, cur, pl):
        blk = []
        blk.append(Paragraph("COMPUTATION OF TOTAL INCOME AND TAX &mdash; " + fy,
                            ParagraphStyle("comp_t", parent=S["h1"], alignment=TA_CENTER)))
        blk.append(Paragraph("Assessment Year " + ay + " &nbsp;|&nbsp; PAN " + ENTITY["pan"] +
                            " &nbsp;|&nbsp; " + ENTITY["name"], S["small"]))
        blk.append(HRFlowable(width="100%", thickness=0.9, color=colors.HexColor("#20406a"),
                             spaceBefore=2, spaceAfter=8))
        cess = round(pl["tax"] * 0.04 / 1.04)
        base_tax = pl["tax"] - cess
        rows = [
            ["Profits and gains of business or profession (as per P&L)", g(pl["pbt"])],
            ["Add: Inadmissible expenses / disallowances", g(0)],
            ["Less: Deductions under Chapter VI-A", g(0)],
            ["Gross Total Income", g(pl["pbt"])],
            ["Total Income (rounded off u/s 288A)", g(pl["pbt"])],
            ["Income-tax at applicable rate (25% plus surcharge)", g(base_tax)],
            ["Add: Health and Education Cess at 4%", g(cess)],
            ["Total Tax Liability", g(pl["tax"])],
            ["Less: Advance tax and TDS", g(pl["tax"])],
            ["Net Tax Payable / (Refundable)", g(0)],
        ]
        blk.append(_fin_table(rows, S, [128 * mm, 34 * mm],
                             header=["Particulars", "Amount (INR)"],
                             total_rows=[3, 4, 7, 9]))
        blk.append(Spacer(1, 6))
        blk.append(Paragraph(
            "Reconciliation: Profit after tax as per audited accounts Rs. " + g(cur["pat"]) +
            " = Profit before tax Rs. " + g(pl["pbt"]) + " less tax expense Rs. " + g(pl["tax"]) +
            ". Revenue from operations Rs. " + g(cur["revenue"]) + ".", S["small"]))
        return blk

    st = []
    st += ack_page("FY2024", "2024-25", "247100320281024", "28 October 2024", F.pl_fy2024())
    st.append(PageBreak())
    st += comp_page("FY2024", "2024-25", F.FY2024, F.pl_fy2024())
    st.append(PageBreak())
    st += ack_page("FY2025", "2025-26", "247100915271025", "27 October 2025", F.pl_fy2025())
    st.append(PageBreak())
    st += comp_page("FY2025", "2025-26", F.FY2025, F.pl_fy2025())

    labels = ["Page 1 of 4", "Page 2 of 4", "Page 3 of 4", "Page 4 of 4"]
    path = os.path.join(outdir, "Southgate_ITR_FY2024_FY2025.pdf")
    return path, build_document(path, st, page_labels=labels, title="ITR Acknowledgements (Specimen)")
