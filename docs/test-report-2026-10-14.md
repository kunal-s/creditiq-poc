# Test report: cross-verification, policy checks and outputs

| | |
|---|---|
| Date | 14 October 2026 |
| Build | Branch `cross-validation-abhishek`, commit `178646c`; configuration version 13 (published 13 Oct 2026) |
| Scope | Test plan rows TC-20 to TC-23 (cross-verification), TC-24 and TC-25 (policy norms, approving authority), TC-26 to TC-28 (draft CAM, PD question note, comparison with RBL's record) |
| Environment | Windows workstation; engine tests (pytest), screen tests (Playwright, Chromium), and a functional run on a copy of the local data store (six applications) |

## 1. Summary

| Area | Automated tests | Functional run (6 applications) | Verdict |
|---|---|---|---|
| Cross-verification (TC-20 to TC-23) | 227 engine tests passed; 46 screen tests passed | 24 checks ran on every application; discrepancies, checks not completed and clean areas reported as expected | **Pass** |
| Policy norms and approving authority (TC-24, TC-25) | 234 engine tests passed; 18 screen tests passed | 12 or 13 norms applied per application; every deviation and norm not assessed named; authority determined (provisional matrix) | **Pass**, with provisional norms and matrix |
| Comparison with RBL's record (TC-28) | 41 engine tests passed; 10 screen tests passed | Both applications with a sample record compared; agree, differ, new and missed marked | **Pass** (sample records only) |
| Draft CAM and PD question note (TC-26, TC-27) | 111 engine tests passed; 18 screen tests passed | Memo and note drafted for every application; every citation resolves; downloads correct and repeatable | **Pass**, in the assumed layout |

Across the whole product, **765 engine tests passed** (2 skipped) and **148 of 149 screen tests passed**. The one screen failure, and the one engine test left out, are known to fail only on Windows (section 6).

## 2. What was run

1. **Engine test suite**, in four groups: cross-verification, policy, outputs and the rest. Each test builds its own temporary case and configuration.
2. **Screen test suite** against a mocked service: every screen of the product, including the Cross-checks board, the Policy tab, Comparison and Outputs.
3. **Build checks:** type check, lint, production build, configuration validation and the import contracts that keep case processing away from the configuration writer and from RBL's record.
4. **Functional run on a copy of the local data store.** The live store was not touched. For each of the six applications it:
   - drew the Cross-checks board, the policy assessment, the approving authority and the comparison;
   - drafted the CAM and the PD note;
   - rendered both as Word and PDF twice, and compared the files.

## 3. Automated results

### Engine tests

| Area | Test files | Passed | Failed |
|---|---|---|---|
| Cross-verification | `test_crosschecks` (16), `_areas` (30), `_facilities` (15), `_names` (19), `_switch` (7), `_tax_turnover` (13), `test_xv` (28), `test_xv_cards_identity` (36), `_numbers` (18), `_others` (17), `test_xv_highlights` (3), `test_facts` (16), `test_identifiers` (9) | 227 | 0 |
| Policy and approving authority | `test_policy` (83), `test_approval` (29), `test_comparison` (41), `test_reference` (30), `test_xlsx` (26), `test_admin_settings` (25) | 234 | 0 |
| Outputs | `test_cam` (48), `test_pd_note` (26), `test_output_exports` (30), `test_spread` (7) | 111 | 0 |
| Rest of the product | intake, uploads, checklist, completeness, review, progress, configuration and API (18 files) | 193 (2 skipped) | 0 |
| **Total** | | **765** | **0** |

### Screen tests

| Area | Specs | Passed | Failed |
|---|---|---|---|
| Cross-verification | `cross-verification-board` (43), `cross-verification` (3) | 46 | 0 |
| Policy and approving authority | `tc26-tc27-policy-authority` (18) | 18 | 0 |
| Comparison | `tc30-comparison` (10) | 10 | 0 |
| Outputs | `tc28-tc29-cam-pd-note` (18) | 18 | 0 |
| Workspace and the rest | 18 specs | 56 | 1 (`tc16-query-list`, Windows only) |
| **Total** | | **148** | **1** |

### Build checks

| Check | Result |
|---|---|
| Type check (`tsc`) | Pass |
| Lint (`eslint`) | Pass (0 errors; the 7 existing warnings) |
| Production build | Pass |
| Configuration validation (10 sections) | Pass |
| Import contracts (2) | Pass |

## 4. Functional results by application

Kestrel, Heronbay and Marigold are the test applications built for these rows. BBG-2026-000001 to -000003 are three other applications in the local store, mostly with their documents still incomplete.

### Cross-verification (TC-20 to TC-23)

24 checks ran on every application.

| Application | Identity | Turnover | Bank accounts | Existing obligations | Blocks submission |
|---|---|---|---|---|---|
| BBG-2026-000004 Kestrel (TEST) | 6 discrepancies (1 accepted as valid) | 6 discrepancies | 2 discrepancies | 2 discrepancies | Yes: 2 serious, open |
| BBG-2026-000005 Heronbay (TEST) | 9 passed | 10 passed, 1 not applicable | 2 passed | 3 passed | No: a clean file |
| BBG-2026-000006 Marigold (TEST) | 6 not completed, 3 passed | 1 discrepancy (TO-05), 4 not completed | clear | 2 not completed | No |
| BBG-2026-000001 | 1 discrepancy (decided), 5 not completed | 4 not completed | clear | 1 discrepancy, 1 not completed | No |
| BBG-2026-000002 | 2 discrepancies (decided), 4 not completed | 1 not completed | clear | 1 not completed | No |
| BBG-2026-000003 | 2 discrepancies (open), 4 not completed | 4 not completed | 1 not completed | 3 not completed | Yes |

**Against the test plan:**
- **TC-20 identity:** Kestrel shows a PAN mismatch, a GSTIN mismatch, a legal-name mismatch, a promoter without KYC, director identifiers that disagree, and a name missing its middle name.
- **TC-21 turnover:** GST, audited and tax-return turnover against bank credits (23.7% to 25.0% apart, against a 1% tolerance); the declared turnover; and profit in the books against the tax return.
- **TC-22 bank accounts:** a declared account without a statement, and accounts not declared.
- **TC-23 existing obligations:** facilities that do not reconcile, and instalments to an undeclared lender.
- **Checks not completed:** each names what would complete it.
- **Heronbay:** passes every check.

### Policy norms and approving authority (TC-24, TC-25)

| Application | Norms applied | Deviations | Not assessed | Approving authority |
|---|---|---|---|---|
| Kestrel | 12 | FR-06 working-capital cycle 90 days (at most 75); DOC-01 3 blocking items open | FR-03 DSCR (instalment not on file) | At least Head Office Credit Committee |
| Heronbay | 12 | FR-06 90 days; DOC-01 2 items | FR-03 | At least Head Office Credit Committee |
| Marigold | 13 | EL-05 request 60.5% of turnover (at most 20%); FR-06 90 days; DOC-01 7 items; DOC-02 1 year of statements (at least 2) | EL-02 bureau rank | At least Zonal Credit Committee |
| BBG-2026-000001 | 13 | EL-05 27.1%; DOC-01 7 items; DOC-02 1 year | EL-01, EL-02 | At least Zonal Credit Committee |
| BBG-2026-000002 | 12 | DOC-01 8 items; DOC-02 0 years | 10 (no financial statements on file) | At least Head Office Credit Committee |
| BBG-2026-000003 | 12 | DOC-01 9 items; DOC-02 0 years | 10 (no financial statements on file) | At least Head Office Credit Committee |

The authority reads "at least" wherever norms could not be assessed. **The norms and the approval matrix are provisional** until RBL supplies its own.

### Comparison with RBL's record (TC-28)

| Application | Deviations | Approving authority |
|---|---|---|
| Kestrel (sample record) | FR-06 Agree; DOC-01 Differ; FR-03 Missed (RBL recorded a DSCR CreditIQ could not assess); 10 norms with no deviation on either side | Agree |
| Marigold (sample record) | EL-05, FR-06, DOC-02 Agree; DOC-01 New (found by CreditIQ only); 9 norms with no deviation on either side | Differ |

The other four applications have no record, so they are not compared. The records are sample data; TC-28 is scored once RBL's records for its case set are imported.

### Draft CAM and PD question note (TC-26, TC-27)

| Application | CAM pages | Sections with content | Summary items (findings / not completed / deviations / not assessed / queries) | Sources | PD questions | Every discrepancy asked |
|---|---|---|---|---|---|---|
| Kestrel | 11 | 12 of 12 | 16 / 0 / 2 / 1 / 21 | 28 | 17 (14 findings, 2 deviations, 1 gap; 3 findings merged into one question) | Yes (16 of 16) |
| Heronbay | 7 | 12 of 12 | 0 / 0 / 2 / 1 / 4 | 27 | 3 | n/a (none) |
| Marigold | 9 | 12 of 12 | 1 / 12 / 4 / 1 / 8 | 19 | 7 | Yes (1 of 1) |
| BBG-2026-000001 | 9 | 12 of 12 | 1 / 10 / 3 / 2 / 9 | 7 | 7 | Yes |
| BBG-2026-000002 | 8 | 9 of 12* | 2 / 6 / 2 / 10 / 12 | 8 | 15 | Yes |
| BBG-2026-000003 | 9 | 9 of 12* | 2 / 12 / 2 / 10 / 11 | 8 | 15 | Yes |

\* Financial performance, banking and existing facilities have nothing to draw on (no financial statements or bank statements on file). Each says so rather than being left out.

**On every application:**
- The recommendation is blank, with its four prompts and the sign-off.
- The memo states the data date, "Version 13 (published 13 Oct 2026)" and the cross-check run.
- Every citation marker in the downloads refers to a listed source (742 markers checked across the 12 documents; none broken).
- Every word of the Word file appears in the PDF.
- Rendering the same memo or note twice gives byte-identical files (no clock in the content).
- Drafting a memo and note takes under a second. Rendering both formats takes about 1 to 2 seconds per document.

## 5. Observations

- **Kestrel's** memo shows its board resolution limit (INR 5.00 cr) against the INR 6.50 cr requested, which matters while the board-resolution check (BR-01) stays switched off.
- The memo says that **amounts per facility are not captured**: the working-capital method, the norms and the approving authority use the total of each request. Capturing the split at intake is a pending decision. On Kestrel it would put the cash credit on the turnover method and add a request-against-turnover deviation.
- **BBG-2026-000002 and -000003** have no financial statements on file, so 10 norms could not be assessed. Their PD notes ask for the figures (11 gap questions each), as intended.
- The PD notes are short where there is little to ask (Heronbay: 3 questions) and merge findings that ask the same thing (Kestrel: the three bank-credit gaps).

## 6. Known issues and limits

| Item | Effect | Status |
|---|---|---|
| `e2e/tc16-query-list.spec.ts` | Fails on Windows only: the clipboard returns Windows line endings | Known; passes on Linux |
| `tests/test_intake_upload.py::test_f05_files_stored_by_hash_under_a_private_directory` | Left out: it checks a POSIX file mode that Windows does not have | Known; passes on Linux |
| Excluded-terms check (`npm run check:terms`) | Not run: the private names list is not on this machine | To run where the list is held |
| Norms and approval matrix | Provisional; TC-25 is shown but not scored | Waiting for RBL's norms and matrix |
| CAM layout | Assumed until RBL's template and completed examples arrive | Waiting for RBL's template |
| Comparison records | Sample records for two test applications only | Waiting for RBL's records |
| Credit reviewer's assessment of the latest drafts (C8) | The independent re-review of the second round of fixes was stopped before it ran | To run |

## 7. Update later on 14 October 2026: after the credit re-review

An independent credit reviewer read the drafts of the three test applications and scored them:

| Document | Kestrel | Heronbay | Marigold |
|---|---|---|---|
| CAM | 4 | 4 | 3 |
| PD note | 3 | 3 | 2 |

The scale is 5 usable as is, 4 minor edits, 3 moderate rework. Every figure checked against the data was correct; the reviewer also confirmed the earlier round's fixes.

**What it asked for, and what changed:**
- **The board resolution's signatory and the persons authorised to borrow** are now stated apart. They had been merged.
- **The PD note now also asks about observations:** material facts the memo states that need the promoter's answer. Each is raised only where the data shows it:
  - revenue or net worth falling by a quarter or more (Marigold: revenue INR 10.03 cr to INR 4.96 cr, net worth INR 3.57 cr to INR 1.76 cr);
  - borrowings no facility explains (Heronbay: INR 1.95 cr);
  - a loan disbursal no facility matches (Kestrel: INR 50 lakh);
  - year-end bank balances against the audited balance (Kestrel, Heronbay);
  - a declared facility with no limit (Kestrel);
  - collateral with no details.
- **Questions name their subject**, for example: "Which of AAACK1234F and AAACK9999Z is the entity's PAN?".
- **Open queries for ID-03, TO-03 and TO-04.**
- **Clearer explanations:** identity explanations without nested brackets, and months not on file shown as a range.
- **Less repetition**, vintage in years and months, and source labels qualified with account, year or lender.

The reviewer's point about adding a board-resolution query is left out: the board-resolution check (BR-01) is switched off by choice. Capturing amounts per facility is still a pending decision.

**Re-run after these changes:**
- Engine tests: **802 passed**, 2 skipped (the known Windows-only `test_f05` left out).
- Screen tests: **149 of 150**; the one failure is the known Windows-only `tc16`. Five tests that timed out while the machine was loaded passed on a re-run with one worker.
- Type check, lint (the 7 existing warnings), Prettier, build, configuration validation and both import contracts pass.
- **No cross-check outcome changes:** on today's data, outcomes under the previous commit and under these changes are identical for all six applications.

**Data note:** since the first run, a GSTR-3B for another company was uploaded to BBG-2026-000001 and to Marigold (BBG-2026-000006). This adds a GSTIN and a company-name discrepancy on Marigold, and changes some identity results on BBG-2026-000001. Section 4 reflects the data before that upload.
