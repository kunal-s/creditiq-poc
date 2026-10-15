# Draft CAM and PD question note (TC-26, TC-27)

| | |
|---|---|
| Date | 13 October 2026 |
| Test plan rows | TC-26 Draft CAM (C7, C8), TC-27 PD question note (C8); TC-28 comparison is unchanged |
| FRD | F-23 (draft CAM), F-24 (PD question note); decision C.4-5 revised |
| Where | Appraisal → **Outputs** tab → **Draft CAM** and **PD question note**, each with **Download Word** and **Download PDF** |

RBL's CAM template has not been received. Both documents use an **assumed layout**, modelled on a business-banking credit approval memo. The memo says so on its face ("Draft — layout assumed until RBL's CAM template is received"). When the template arrives, the section list in `config/cam.yaml` is replaced to follow it; the drafting and the downloads stay.

## 1. How the documents are produced

- **From the case's facts only.** The text is composed from the extracted figures, the cross-checks, the policy assessment, the checklist and the query list, not written by a model. The same case always gives the same memo and note (F-23.6).
- **Every figure is cited.** On screen, a citation opens the source page. In the downloads, it is a marker such as `[3 p.4]` that refers to a numbered **Sources** list at the end: document, file and pages. Three or more consecutive sources cited at the same pages print as a range, such as `[13-23 p.1]` for twelve monthly returns. Sources are numbered in the order they are first cited, and the screen, the Word file and the PDF number them the same way. A finding cites the documents on each side of the difference, for example the KYC of the director concerned.
- **No date of drafting.** The memo states the date the case's data is read as of ("Drafted from the data on file as of …"), the configuration version ("Version 15 (published 13 Oct 2026)") and the cross-check run (XR-…), so it records what was on file rather than when it was printed.
- **Downloads in two formats with the same text:**
  - Word (`.docx`), editable, for credit to complete the recommendation;
  - PDF, for circulation.

  File names are `CAM-draft-<case>.docx|pdf` and `PD-note-<case>.docx|pdf`. Each download is recorded in the audit trail (`output.downloaded`).

## 2. The assumed CAM layout

| # | Section | What it shows | Drawn from |
|---|---|---|---|
| | Title block | Credit Approval Memo, borrower, case, data as of, configuration version, cross-check run, the assumed-layout note | Case, published configuration, latest run |
| 1 | Proposal at a glance | Key facts: borrower, constitution, PAN, GSTIN, CIN, incorporation and vintage, facilities and amount, collateral offered, declared turnover, relationship manager, approving authority, cross-checks, policy norms, documentation readiness | Case, facts, approval matrix, cross-checks, policy, checklist |
| 2 | Borrower profile | Who the borrower is; legal name, CIN, incorporation date and company type, PAN, GSTIN; a pointer to any identity discrepancy | Certificate of incorporation, PAN, GST returns, findings |
| 3 | Promoters and management | One row per person: role, DIN, PAN, KYC on file, the documents that name them; gaps such as a director without KYC | KYC, memorandum, bureau report, sourcing message |
| 4 | Proposal and facilities | Facilities proposed and their product group, total amount, declared turnover, collateral (as recorded at intake), the board resolution's date, lender, limit and signatories, and any shortfall against the request | Sourcing message, board resolution, approval matrix |
| 5 | Financial performance | Up to three years: revenue and growth, EBITDA and margin, profit after tax and margin, net worth, borrowings, current ratio, TOL/TNW, debt/equity, interest coverage, DSCR, working-capital cycle; comments tied to the policy norms | Spread (audited statements) |
| 6 | Assessment of working-capital requirement | Turnover method or MPBF, step by step, and whether the request is within the eligible amount | Spread, policy configuration |
| 7 | Turnover across sources | Per financial year: audited, GST (GSTR-3B), income tax return, business credits in the bank, declared; each variance beyond tolerance with its reference; GST and income tax filings on file | Turnover facts, TO-/TX- checks |
| 8 | Banking and account conduct | Per account: months, gross credits, exclusions, business credits, monthly average; accounts without statements | Bank statements, account facts |
| 9 | Existing facilities and obligations | Per lender: facility, declared, sanction letter and bureau amounts, instalment, debits seen in the bank; overdues; undeclared lenders | Declaration, sanction letters, bureau report, bank debits |
| 10 | Cross-verification of sources | Checks by area (run, discrepancies, accepted, open, could not be completed), then each discrepancy in board order: reference (XV-…), severity, finding, detail, status (Accepted, Not valid, Escalated, Open), blocking | Cross-checks board |
| 11 | Compliance with policy norms | Each applicable norm: required, actual, result, category; deviations and norms not assessed; the approving authority (amount authority, deviation steps, required authority, whether it could rise) | Policy assessment, approval matrix |
| 12 | Documentation status | Readiness against the gate, blocking items, each open item and what is missing | Checklist |
| 13 | Summary of findings, deviations and open queries | Findings not dismissed, as a register (reference, severity, title, status, blocking); checks not completed and what would complete them; deviations; norms not assessed; open queries by query-list group | F-19, F-20, F-14 |
| 14 | Recommendation | **Left blank for credit:** Recommendation; Terms and conditions; Deviations recommended for approval; Decision of the approving authority; sign-off (Prepared by, Recommended by, Approved by) | — |

## 3. The PD question note

- **Header:** borrower, case, constitution, proposal, data as of.
- **People to meet:** each promoter or director, with role, DIN and the documents that name them.
- **Record of the discussion:** blank lines for the date, place, bank officials present, and promoters or representatives present.
- **Questions:** grouped by topic (Identity and KYC; Turnover, tax and sales; Bank accounts; Existing borrowings; Policy norms) and ranked by severity within each topic, numbered through the note. Each question shows:
  - **the question**;
  - **why it is asked**: the finding with its XV reference, or the norm deviation or gap;
  - its evidence;
  - for a finding, its status (Accepted as valid, Escalated, Open).

  Findings that raise the same question are asked once, and the question lists every finding it covers ("Also covers"). Checks that could not be completed are asked about together, naming what would complete them. Every finding not dismissed has a question. The downloads leave space for the **response** and the **follow-up** under each question. A finding dismissed as not valid is not asked about.
- **Documents to collect at the discussion:** the documents still outstanding on the query list.
- **Sign-off:** who held the discussion.

## 4. What the assumed layout cannot yet carry

These need RBL's template or inputs not yet captured:
- **amounts per facility.** The case records only the total. The working-capital method, the policy norms and the approving authority therefore use the total, including any term loan, and the memo says so. The sourcing message often states the split (for example cash credit INR 4.00 cr and term loan INR 2.50 cr). Capturing it at intake would let the working-capital amount decide the method, the request-against-turnover norm and the approving authority per product;
- security and collateral details and valuation;
- industry and business narrative;
- strengths and risks, which are credit's judgement;
- RBL's spread format (the financial table uses the interim spread);
- consumer bureau reports of the promoters.

The memo does not invent these. It says what is not on file, and the recommendation is left to credit.

## 5. Code

| Part | Files |
|---|---|
| Drafting | `engine/cam.py`, `engine/pd_note.py`, `engine/output_sources.py` (source numbering and document labels), `config/cam.yaml`, `engine/configstore/schema.py` |
| Downloads | `engine/exports/` (layout, Word with python-docx, PDF with reportlab; both permissive licences), endpoints `GET /api/cases/{id}/cam/download?format=docx\|pdf` and `GET /api/cases/{id}/pd-note/download?format=docx\|pdf` |
| Contract | `engine/contracts/outputs.py` (`Cam` with numbered sections of blocks, summary references and status, recommendation prompts, sign-off and sources; `PdNote` with people, topics, numbered questions split into question and context, documents to collect, record fields, sources) |
| Screen | `src/components/case/Outputs.tsx`, `src/domain/outputs.ts`; a reference opens its finding (`?finding=` on Cross-checks) or norm (`?norm=` on Policy); labels in `terminology/rbl.yaml` |
| Wording inside the downloads | `config/cam.yaml` (`labels`, `pd_note.labels`, `pd_note.sign_off`); PD questions in `config/crosschecks.yaml` and `config/policy.yaml` |
| Dependencies | `requirements.in`, `requirements.txt` (python-docx, lxml, reportlab, charset-normalizer; hash-pinned) |
