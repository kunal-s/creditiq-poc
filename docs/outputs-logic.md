# Outputs: draft CAM and PD question note (simple version)

This covers the test plan's output rows:

| ID | Test | What CreditIQ does | Pass rule | Criterion | Status today |
|---|---|---|---|---|---|
| **TC-26** | Draft CAM | Drafts a Credit Approval Memo from the case's facts, every figure cited, ending in a structured summary of findings, deviations and open queries, with the recommendation left blank for credit | Reviewer rates it usable with minor edits; citations resolve | C7, C8 | Built, in an **assumed layout** until RBL's CAM template and completed examples arrive |
| **TC-27** | PD question note | Lists the questions for the personal discussion with the promoter, each tied to its finding or norm and its evidence | Reviewer confirms the questions are relevant | C8 | Built |
| **TC-28** | Comparison with RBL's record | Shows CreditIQ's deviations and approving authority beside RBL's record: Agree, Differ, New or Missed | Complete for every case | All | Built; runs once RBL's case records are imported |

Both documents are on the appraisal's **Outputs** tab, and each downloads as **Word** (editable) or **PDF**. For the details of the layout and the code, see [outputs-cam-pd.md](outputs-cam-pd.md).

---

## How the documents are written

- **From the case's facts only.** The text is put together from the extracted figures, the cross-checks, the policy assessment, the checklist and the query list. No model writes it, so the same case always gives the same memo and note.
- **Every figure is cited.** Each figure points to the document and page it came from. On screen a citation opens the page. In the downloads it is a marker such as `[3 p.4]`, numbered against a **Sources** list at the end; a run of documents cited at the same page reads as a range, such as `[13-23 p.1]` for twelve monthly GST returns. A discrepancy cites the documents on each side of the difference.
- **Dated by the data, not the clock.** The memo says it was drafted "from the data on file as of" the case's date, with the configuration version and the cross-check run it reports.
- **Says what is missing.** Where a figure or document is not on file, the memo says so. It never fills a gap with a guess.
- **Decisions are respected.** A discrepancy dismissed as not valid is left out of the summary and is not asked about. One accepted as valid is shown as such.

## The draft CAM

The layout is **assumed**: it follows a typical business-banking credit approval memo, and says so on its face. When RBL's template arrives, the section list changes (`config/cam.yaml`); the drafting stays.

| # | Section | What it says |
|---|---|---|
| 1 | Proposal at a glance | The key facts on one page: borrower, constitution, PAN, GSTIN, CIN, years in business, facilities and amount, board resolution limit, collateral, declared turnover, relationship manager, approving authority, and where the cross-checks, policy norms and documentation stand |
| 2 | Borrower profile | Who the borrower is, from its registration documents, with a pointer to any identity discrepancy |
| 3 | Promoters and management | One row per director: role, DIN, PAN, whether a KYC is on file, and the documents that name them |
| 4 | Proposal and facilities | What is asked for, the board resolution's limit (and any shortfall against the request), collateral as recorded at intake |
| 5 | Financial performance | Up to three years of revenue, profit, margins, net worth, borrowings and ratios, each set against its policy norm |
| 6 | Working-capital assessment | Turnover method or MPBF, step by step, and whether the request is within the eligible amount |
| 7 | Turnover across sources | For each year: audited, GST, income tax return, bank credits and the declared figure side by side, and which differ beyond tolerance |
| 8 | Banking and account conduct | Per account: credits, what was excluded (transfers, loan disbursals, reversals) and business credits; accounts without statements |
| 9 | Existing facilities and obligations | Per lender: what was declared, sanctioned and reported to the bureau, the instalment and the debits seen in the bank |
| 10 | Cross-verification of sources | Checks by area, then each discrepancy with its reference (XV-…), severity, detail and status |
| 11 | Compliance with policy norms | Each norm: required, actual, result; the approving authority and why |
| 12 | Documentation status | Readiness against the gate and each item still open |
| 13 | **Summary** | Findings (as a list of references and status), checks not completed and what would complete them, deviations, norms not assessed, open queries |
| 14 | **Recommendation** | **Left blank for credit:** Recommendation; Terms and conditions; Deviations recommended for approval; Decision of the approving authority; sign-off (Prepared, Recommended, Approved by) |

Each discrepancy is explained once, in section 10. The summary lists it by reference, so the memo does not repeat itself.

## The PD question note

**Where the questions come from:**

- **Each discrepancy** not dismissed. It is asked with its check's question; a check without one gets a general question ("What is the position, and what will be provided?"), so no discrepancy is left out.
- **Each policy deviation.** For example: "What explains the deviation on the working-capital cycle, and what is the outlook for the current year?"
- **Each gap.** A check that could not be completed, or a norm that could not be assessed, asks for what would complete it. For example, when GST returns and bank statements cover only part of a year, it asks whether the missing months can be provided before sanction, naming them.

**How they are arranged:**

- **By topic:** Identity and KYC; Turnover, tax and sales; Bank accounts; Existing borrowings; Policy norms. A topic with no question is left out.
- **Ranked within each topic:** serious first, then moderate, then mild. Discrepancies come before deviations, and deviations before gaps.
- **Numbered through the note.**
- **Asked once.** Discrepancies that raise the same question are asked together. For example, GST, audited and tax-return turnover all above the bank credits become one question ("Where are the rest of the sales receipts banked, or are they received in cash?"), listing every finding it covers. The checks not completed in a topic are asked together.
- **Not asked twice.** A document already on the list to collect is not asked for again as a question.

**What each question shows:**

- the question, in bold;
- **why we ask** (the finding, deviation or gap);
- the evidence;
- for a discrepancy, its status.

The note also lists:
- the people to meet;
- blank lines for the record of the discussion (date, place, who attended), and for the response and follow-up under each question;
- the documents to collect at the discussion;
- a sign-off.

## Downloads

| | Word (.docx) | PDF |
|---|---|---|
| Use | Editable: credit completes the recommendation | For circulation |
| Content | Identical text in both: title block, numbered sections, citation markers, Sources list | |
| Page | A4, running header with the borrower and case, footer with the data date and page X of Y | |
| File names | `CAM-draft-<case>.docx`, `PD-note-<case>.docx` | `CAM-draft-<case>.pdf`, `PD-note-<case>.pdf` |

Every download is recorded in the audit trail.

## What the assumed layout cannot yet carry

These need RBL's template, or inputs not captured on the case:
- **Amounts per facility.** The case records only the total. So the working-capital method, the policy norms and the approving authority use the total, including any term loan, and the memo says so. The sourcing message often gives the split. Capturing it would let the working-capital amount decide the method and the authority per product.
- **Security and collateral** details and valuation.
- **Industry and business narrative.**
- **Strengths and risks**, which are credit's judgement.
- **RBL's spread format.** The financial table uses the interim spread.
- **Promoters' consumer bureau reports.**

## Where it is set

| What | Where |
|---|---|
| Sections, titles, recommendation prompts, sign-off, wording inside the downloads | `config/cam.yaml` |
| PD questions for each check, and for checks not completed | `config/crosschecks.yaml` |
| PD questions for policy deviations and norms not assessed | `config/policy.yaml` |
| Labels on the screen | `terminology/rbl.yaml` |
