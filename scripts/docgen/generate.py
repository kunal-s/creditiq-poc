"""
Orchestrator: build the full Southgate specimen set, write manifest.json, and
print a summary table.

Run:  python3 generate.py
Output folder: <repo>/docready-southgate-documents
"""
import json
import os
import re
import sys

import pymupdf

import build_group1 as g1
import build_group2 as g2
import build_group3 as g3

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTDIR = os.path.join(REPO, "docready-southgate-documents")


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def locate(path, snippet):
    """Return the 1-based page number where `snippet` first appears (whitespace
    normalised). Raise if not found -- evidence snippets must be genuinely present."""
    target = _norm(snippet)
    doc = pymupdf.open(path)
    for i in range(doc.page_count):
        if target in _norm(doc[i].get_text()):
            return i + 1
    raise ValueError("snippet not found in %s: %r" % (os.path.basename(path), snippet))


def main():
    os.makedirs(OUTDIR, exist_ok=True)

    # Build everything (priority order: group 1 first).
    builders = [
        g1.build_title_deed, g1.build_nil_declaration, g1.build_ca_statement,
        g2.build_stock_bookdebt, g2.build_gstr3b, g2.build_provisional_fy2026,
        g2.build_board_resolution,
        g3.build_coi, g3.build_moa_aoa, g3.build_pan_letter, g3.build_director_kyc,
        g3.build_audited_fy2024, g3.build_audited_fy2025, g3.build_itr,
    ]
    built = {}
    for fn in builders:
        path, pages = fn(OUTDIR)
        built[os.path.basename(path)] = dict(path=path, pages=pages)

    # ---- Document metadata / verdicts ------------------------------------- #
    def ev(filename, snippet):
        p = built[filename]["path"]
        return dict(page=locate(p, snippet), snippet=snippet)

    docs = []

    # 1. Title Deed
    fn = "Southgate_Title_Deed_Coimbatore_Unit.pdf"
    docs.append(dict(
        filename=fn, title="Registered Sale Deed - Coimbatore Industrial Unit (Plot 47)",
        requirement="Clear title to collateral property, free of prior encumbrance",
        verdict="insufficient", defect_type="inconsistent",
        reason="Page 3 records a subsisting equitable mortgage of the collateral in favour of "
               "Meridian Bank, contradicting the borrower's declaration of unencumbered security.",
        page_count=built[fn]["pages"],
        evidence=[
            ev(fn, "MORTGAGE BY DEPOSIT OF TITLE DEEDS"),
            ev(fn, "MERIDIAN BANK, Coimbatore Branch"),
            ev(fn, "Rs. 1,75,00,000 (Rupees One Crore Seventy-Five Lakh only)"),
            ev(fn, "14 March 2024"),
        ],
        contradicts=[
            "Southgate_Nil_Facilities_Declaration.pdf",
            "Southgate_CCB_CA_Statements_12m.pdf",
        ]))

    # 2. Nil Facilities Declaration
    fn = "Southgate_Nil_Facilities_Declaration.pdf"
    docs.append(dict(
        filename=fn, title="Declaration of Nil Existing Facilities and Unencumbered Security",
        requirement="Borrower declaration of existing borrowings and charges",
        verdict="insufficient", defect_type="inconsistent",
        reason="Declares no existing facilities and unencumbered collateral, directly "
               "contradicted by the Meridian mortgage on the title deed and the Meridian EMI "
               "outflows in the bank statement.",
        page_count=built[fn]["pages"],
        evidence=[
            ev(fn, "does not have any existing credit facilities"),
            ev(fn, "free from any encumbrance, mortgage, charge or prior claim"),
        ]))

    # 3. CCB Current Account Statement (12m)
    fn = "Southgate_CCB_CA_Statements_12m.pdf"
    docs.append(dict(
        filename=fn, title="Continental Commercial Bank - 12-Month Current Account Statement",
        requirement="Statements for all bank accounts (12 months)",
        verdict="insufficient", defect_type="incomplete",
        reason="Only one account is covered; a recurring monthly 'MERIDIAN BANK EMI DR' of "
               "2,18,750 evidences a second banking relationship whose statement was never "
               "provided.",
        page_count=built[fn]["pages"],
        evidence=[
            ev(fn, "MERIDIAN BANK EMI DR"),
            ev(fn, "This statement pertains to current account 914020055831447 only"),
        ]))

    # 4. Stock & Book-Debt statement (stale)
    fn = "Southgate_Stock_BookDebt_30Jun2026.pdf"
    docs.append(dict(
        filename=fn, title="Stock and Book-Debt Statement as at 30 June 2026",
        requirement="Current stock and book-debt statement for drawing power",
        verdict="insufficient", defect_type="stale",
        reason="Position stated as at 30 June 2026 and signed 04 July 2026 - 52 days old as at "
               "the reference date of 21 August 2026; a current statement is required.",
        page_count=built[fn]["pages"],
        evidence=[
            ev(fn, "AS AT 30 JUNE 2026"),
            ev(fn, "Date of signing: 04 July 2026"),
        ]))

    # 5. GSTR-3B set (incomplete - four-month gap)
    fn = "Southgate_GSTR3B_Dec2025_Jul2026.pdf"
    docs.append(dict(
        filename=fn, title="GSTR-3B Returns Compilation (December 2025 - July 2026)",
        requirement="Twelve months of GST returns",
        verdict="insufficient", defect_type="incomplete",
        reason="Only eight periods (Dec 2025 - Jul 2026) are enclosed; the returns for August, "
               "September, October and November 2025 are absent from the file.",
        page_count=built[fn]["pages"],
        evidence=[
            ev(fn, "August 2025, September 2025, October 2025 and November 2025 are not enclosed"),
            ev(fn, "Returns enclosed in this compilation (eight periods)"),
        ]))

    # 6. Provisional FY2026 (incomplete - balance sheet absent)
    fn = "Southgate_Provisional_FY2026.pdf"
    docs.append(dict(
        filename=fn, title="Provisional Financial Statements - 9M ended 31 December 2025",
        requirement="Provisional financial statements (P&L and balance sheet)",
        verdict="insufficient", defect_type="incomplete",
        reason="The balance sheet is absent - page numbering jumps from 'Page 2 of 7' to "
               "'Page 6 of 7', so pages 3 to 5 carrying the balance sheet are missing.",
        page_count=built[fn]["pages"],
        evidence=[
            ev(fn, "Page 6 of 7"),
            ev(fn, "The Balance Sheet as at 31 December 2025, together with its supporting "
                   "schedules, is set out on pages 3 to 5"),
        ]))

    # 7. Board resolution draft (plain paper + unsigned)
    fn = "Southgate_Board_Resolution_draft.pdf"
    docs.append(dict(
        filename=fn, title="Board Resolution - Borrowing Authority (Draft)",
        requirement="Certified board resolution authorising borrowing (Sec 179(3)(d))",
        verdict="insufficient", defect_type="incomplete",
        reason="On plain paper with no company letterhead, and the signature block is blank - "
               "no name, designation, signature or date - so the resolution is unexecuted.",
        page_count=built[fn]["pages"],
        evidence=[
            ev(fn, "to be signed by the Chairman / Company Secretary"),
            ev(fn, "Section 179(3)(d)"),
        ]))

    # ---- Clean / satisfied documents -------------------------------------- #
    clean = [
        ("Southgate_Certificate_of_Incorporation.pdf",
         "Certificate of Incorporation",
         "Certificate of incorporation with CIN",
         "Valid certificate of incorporation dated 18 March 2016 with CIN "
         "U17291TZ2016PTC027431 and PAN AAHCS6612M."),
        ("Southgate_MOA_AOA.pdf",
         "Memorandum and Articles of Association",
         "Constitutional documents with objects and borrowing powers",
         "Objects clause covers manufacture and sale of textiles and the articles confer "
         "borrowing powers (Article 84 / Section 179(3)(d))."),
        ("Southgate_Entity_PAN.pdf",
         "Entity PAN Allotment Intimation",
         "Company PAN proof",
         "PAN AAHCS6612M allotted to Southgate Textiles Private Limited, matching all other "
         "documents in the set."),
        ("Southgate_Director_KYC_Iyer_x2.pdf",
         "Director KYC Summary Sheets (x2)",
         "KYC for each director",
         "KYC summary for both directors with DIN, date of birth and address; personal "
         "identifiers are shown masked."),
        ("Southgate_Audited_FS_FY2024.pdf",
         "Audited Financial Statements FY2024",
         "Audited financial statements (latest two years)",
         "Audited statements to 31 March 2024 with clean auditor's opinion; revenue "
         "18,42,67,400, EBITDA 2,21,12,088, PAT 87,34,210, net worth 4,62,18,750."),
        ("Southgate_Audited_FS_FY2025.pdf",
         "Audited Financial Statements FY2025",
         "Audited financial statements (latest two years)",
         "Audited statements to 31 March 2025 with FY2024 comparatives; revenue "
         "23,17,84,900, EBITDA 2,89,73,113, PAT 1,14,62,880, net worth 5,76,81,630."),
        ("Southgate_ITR_FY2024_FY2025.pdf",
         "Income Tax Return Acknowledgements FY2024 & FY2025",
         "Income tax returns (latest two years)",
         "ITR-6 acknowledgements and computations for AY 2024-25 and AY 2025-26, reconciling "
         "to the audited profits."),
    ]
    for fname, title, req, reason in clean:
        docs.append(dict(
            filename=fname, title=title, requirement=req,
            verdict="satisfied", defect_type=None, reason=reason,
            page_count=built[fname]["pages"], evidence=[]))

    # ---- Requirement with no document provided (missing) ------------------ #
    missing = [dict(
        filename=None,
        title="Meridian Bank account statement (second banking relationship)",
        requirement="Statements for all bank accounts (12 months)",
        verdict="missing", defect_type=None,
        reason="A second banking relationship with Meridian Bank (account ending 8830) is "
               "evidenced by the monthly EMI in the Continental Commercial Bank statement and by "
               "the Meridian mortgage on the title deed, but no statement for that account was "
               "submitted.",
        page_count=0, evidence=[],
        related_documents=[
            "Southgate_CCB_CA_Statements_12m.pdf",
            "Southgate_Title_Deed_Coimbatore_Unit.pdf",
        ])]

    manifest = dict(
        set_name="docready-southgate-documents",
        generated_for="Banking working-capital loan application demo (prototype document viewer)",
        disclaimer="Every document in this set is a SYNTHETIC specimen created for demonstration. "
                   "Not a real instrument. All identifiers are fictional.",
        reference_date="21 August 2026",
        application=dict(
            received="04 August 2026",
            cash_credit="INR 2,85,00,000", term_loan="INR 1,40,00,000",
            total="INR 4,25,00,000",
            applicant="Southgate Textiles Private Limited",
            cin="U17291TZ2016PTC027431", pan="AAHCS6612M", gstin="33AAHCS6612M1ZQ",
            primary_bank="Continental Commercial Bank, Coimbatore SME Branch",
            primary_account="914020055831447"),
        verdict_legend=dict(
            satisfied="Requirement met by a well-formed document.",
            insufficient="Document present but defective (see defect_type).",
            missing="Required document not provided."),
        defect_legend=dict(
            stale="Position is out of date as at the reference date.",
            incomplete="Document or series is missing pages/periods/execution.",
            inconsistent="Content conflicts with another document in the set."),
        document_count=len(built),
        total_pages=sum(v["pages"] for v in built.values()),
        documents=docs,
        missing_requirements=missing,
    )

    with open(os.path.join(OUTDIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # ---- Summary table ---------------------------------------------------- #
    verdict_by_file = {d["filename"]: (d["verdict"], d.get("defect_type"))
                       for d in docs}
    ordered_files = list(built.keys())  # insertion order == build order
    total_size = 0
    print("\n%-46s %6s %10s  %-12s %s" % ("FILE", "PAGES", "SIZE", "VERDICT", "DEFECT"))
    print("-" * 92)
    for fname in ordered_files:
        info = built[fname]
        size = os.path.getsize(info["path"])
        total_size += size
        v, d = verdict_by_file.get(fname, ("satisfied", None))
        print("%-46s %6d %9.1fK  %-12s %s" %
              (fname, info["pages"], size / 1024.0, v, d or "-"))
    mpath = os.path.join(OUTDIR, "manifest.json")
    msize = os.path.getsize(mpath)
    total_size += msize
    print("%-46s %6s %9.1fK  %-12s %s" % ("manifest.json", "-", msize / 1024.0, "-", "-"))
    print("-" * 92)
    print("%-46s %6d %9.1fK" % ("TOTAL (%d files)" % (len(built) + 1),
                                manifest["total_pages"], total_size / 1024.0))
    print("\nVerdicts: %d satisfied, %d insufficient, %d missing-requirement" % (
        sum(1 for d in docs if d["verdict"] == "satisfied"),
        sum(1 for d in docs if d["verdict"] == "insufficient"),
        len(missing)))
    print("Output: %s" % OUTDIR)


if __name__ == "__main__":
    main()
