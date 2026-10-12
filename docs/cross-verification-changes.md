# Cross-verification: change register

| | |
|---|---|
| Date | 7 October 2026, updated 8 October 2026 (section 10), 11 October 2026 (section 11) and 12 October 2026 (sections 11.11 to 11.14) |
| Branch | `cross-validation-abhishek` (not yet committed) |
| Feature | Stage 4 of the case workspace, **Cross-checks** (`/appraisals/$caseId/cross-verification`); FRD F-18, F-19, F-16.2 |
| Plan | [cross-verification-plan.md](cross-verification-plan.md) |
| Scope | The nine document types, plus the RM's sourcing message |

---

## 1. Summary

- **Rules:** 17 new cross-checks, 4 changed. 25 rules in total, in seven areas (26 since 8 October, with OB-01; section 10).
- **Screen:** the Cross-checks tab rebuilt to show at a glance where the file stands, and why.
- **Evidence:** a side-by-side evidence viewer, comparing two documents' pages at once.
- **Gating:** a check now waits for a value that is still under review, instead of relying on it.
- **Missing documents:** a check that cannot run because a document is missing names the document.
- **Since 11 October:** the tab is the cross-verification board, over four areas, and eight rules are switched off (section 11).

## 2. What users see

As built on 7 October. The board replaced this screen on 11 October (section 11.2).

| Part of the screen | What it does |
|---|---|
| Outcome tiles | Four tiles: **Discrepancies** (with blocking and to-decide counts), **Incomplete**, **Sources agree**, **Not applicable**. Clicking a tile filters the list |
| Area cards ("Where the file stands") | One card per area: Identity, Borrowing authority, Turnover, Income tax, Financial statements, Bank accounts, Obligations. Coloured red, amber or green by its worst result. Clicking a card shows only that area |
| Check list | Grouped by area. Each check shows its sources in a table; the value that disagrees is in red and tagged **Differs** |
| Line by line | A table under the check (months, people or years), with the rows that failed marked. Open by default on a failed check |
| Not on file | Tags naming the documents a check is waiting for, with a link to add them |
| Waiting for review | A tag on a value still in the review queue. It opens the value at its page to confirm or correct |
| Compare side by side | Opens the source pages of a check next to each other (F-16.2) |
| Valid / Not valid | Unchanged: confirm a discrepancy, or record why it is not valid |
| Facts panels | New: **Identifiers by document**, **Directors and promoters**, **Board resolution**, **Income tax and the books**. Existing: turnover, bank credits, obligations, bank accounts |

## 3. Cross-checks

### New

| ID | Area | Check | Blocks |
|---|---|---|---|
| ID-05 | Identity | CIN is the same on the certificate of incorporation and the memorandum | Yes |
| ID-06 | Identity | Each director's DIN on the KYC matches the memorandum; the KYC PAN is an individual's, not the company's | No |
| ID-07 | Identity | What the CIN encodes (year, company class, listing) matches the incorporation date and the case constitution | No |
| ID-08 | Identity | Directors named in the memorandum have a KYC or are named by the RM | No |
| BR-01 | Borrowing authority | The board resolution's limit covers the amount requested | Yes |
| BR-02 | Borrowing authority | Authorised signatories are directors on file | No |
| BR-03 | Borrowing authority | The resolution is in favour of this bank | No |
| BR-04 | Borrowing authority | The resolution is dated after incorporation and on or before the appraisal date | No |
| TO-05 | Turnover | GST against bank credits over the months both cover, with a month-by-month table | No |
| TX-01 | Income tax | Each audited year has its income tax return, once the return is due | No |
| TX-02 | Income tax | Profit in the return matches profit before tax in the audited statements | No |
| FS-01 | Financial statements | Previous-year figures in the latest statements match that year's own statements | No |
| FS-02 | Financial statements | Year-end bank balances are not above the audited cash and bank balance | No |
| BA-01 | Bank accounts | Accounts the RM declared have statements | No |
| BA-02 | Bank accounts | Accounts seen in transfers have statements (widened on 8 October: every account on file is declared) | No |
| OB-02 | Obligations | Monthly instalments in the statements go to lenders the RM declared | No |
| OB-03 | Obligations | Long-term borrowings in the books show up as instalments in the bank, and the reverse | No |

### Changed

| ID | Change |
|---|---|
| ID-01 Entity PAN | Also compares the PAN inside every GSTIN (characters 3 to 12). Audited statements dropped as a source, because they carry no PAN field |
| ID-03 Legal name | A bank's truncated account name (for example "KESTREL TOOLS P") counts as the same name |
| ID-04 Promoters | Now the KYC received against the RM's promoters. Board-resolution signatories no longer count as the promoter set (BR-02 checks them) |
| TO-01 to TO-03 | GST turnover now sums table 3.1 rows (a), (b) and (c): taxable, zero-rated, and nil-rated or exempt supplies |

### Unchanged

ID-02 (GSTIN), TO-02, TO-03 and TO-04 apart from the GST rows above.

### Not built

The plan's P3 checks (ID-09, TX-03, BA-03). OB-01 (declared facilities against sanction letters and bureau) was built on 8 October; see section 10.

## 4. How a check decides its outcome (new behaviour)

| Situation | Outcome |
|---|---|
| A value the check uses is still waiting for review | **Incomplete**, "Waiting for review of …"; no review item is raised until the value is confirmed (F-17.2) |
| A document the case's checklist needs is not on file | **Incomplete**, naming the document (F-19.3) |
| Nothing to compare, and nothing expected is missing | **Not applicable** |
| Sources disagree | **Fail**; the minority value is marked as differing |

The Cross-verification stage now starts only once a check has compared two sources.

## 5. Configuration changes

A new configuration version was published to the local data root, and the existing case was re-checked.

| File | Change |
|---|---|
| `config/crosschecks.yaml` | 25 rules, each with an `area`; ID-01 and ID-04 sources changed |
| `config/tolerances.yaml` | New, all provisional: `turnover_window_min_months` (3), `itr_due_days` (214), `profit_variance` (10%), `comparatives_variance` (1%), `balance_variance` (1%) |
| `config/alignment.yaml` | New `own_bank_names`, used by BR-03 |
| `config/statements.yaml` | GST rows (a), (b), (c); new `itr_lines` (profit and turnover rows of the ITR computation) |
| `engine/configstore/schema.py` | Rule `area`; new comparisons `bound` and `order`; 14 new rule variables |
| `terminology/rbl.yaml` | Labels for the tiles, areas, tables, facts panels and side-by-side viewer |

## 6. API and data changes

All additive. The TypeScript types were regenerated (`contracts/openapi.json`, `src/api/schema.gen.ts`).

| Item | Addition |
|---|---|
| `Finding` | `area`, `scope`, `detail` (line-by-line table), `missing` (documents not on file) |
| `FindingSide` | `differs`, `awaiting_review`, `field_ids` |
| `CaseFacts` | `identities.cin`; people with DIN and PAN; `incorporation`, `authority`, `tax_years`, `financial_years`, `months`, `balances`, `declared_banking`, `requested_amount`, `types_on_file` |
| Database | Migration 5 adds `area`, `scope`, `detail`, `missing` to `findings` (applied automatically) |

No new endpoints: `GET /api/cases/{id}/findings` and `/facts` return the new fields.

## 7. Code changes

| Area | Files |
|---|---|
| Rule engine | `engine/crosschecks.py` (rewritten: one evaluator per rule) |
| Facts | `engine/facts.py`, `engine/statements.py` |
| Contracts and storage | `engine/contracts/appraisal.py`, `engine/contracts/facts.py`, `engine/contracts/__init__.py`, `engine/db.py`, `engine/reads.py` |
| Elsewhere in the engine | `engine/progress.py` (stage start), `engine/cam.py` (CAM findings grouped by area), `engine/completeness.py` (checklist helper usable without documents) |
| Screen | `src/components/case/CrossVerification.tsx` (rebuilt), `src/components/docviewer/DocViewer.tsx` (side-by-side), `src/components/common/Details.tsx` (`open` option), `src/api/types.ts` |

## 8. Tests

| Test | Change |
|---|---|
| `tests/test_crosschecks_areas.py` | New: 28 tests, covering every new rule plus review gating and missing documents |
| `tests/test_crosschecks.py` | ID-04 tests rewritten for the new promoter rule |
| `tests/test_facts.py`, `tests/test_config_catalogue.py` | Updated for the GSTIN-derived PAN and the 25 rules |
| `tests/triangulation.py` | Can file a value as still under review |
| `tests/fixtures/build_fixtures.py` and two canned results | The complete sample case corrected: its two years of accounts now agree, and its bank statement has supplier payments (both were real contradictions the new checks caught) |
| `e2e/cross-verification.spec.ts` | New: 3 screen tests (area cards and filtering, differing value and side-by-side view, missing documents) |
| `e2e/fixtures/data.ts` | Mock findings carry the new fields |

Results on 7 October 2026:
- **Python:** 214 passed. One Windows-only failure: a folder-permissions test.
- **Screen tests:** 52 of 53 passed. One Windows-only failure: the clipboard line-ending test.
- **Typecheck, lint, build and import rules:** pass.

## 9. Known limits

- **Provisional tolerances.** All tolerances are provisional until RBL supplies its own.
- **FS-02 and cash-credit statements.** FS-02 adds statement balances as printed. A cash-credit statement that prints an overdrawn balance as a positive number could raise a false flag. The check is mild, does not block and asks the customer nothing.
- **The RM's message as the declaration.** OB-02 and BA-01 use the RM's sourcing message as the declaration of existing banking when no declaration of existing facilities is on file. If neither names any lender, OB-02 stays incomplete.

## 10. Changes on 8 October 2026

The gaps found when checking the test plan's TC-20 to TC-23 (FRD TC-22 to TC-25), closed.

### New document types

| Type | Read from it | Feeds |
|---|---|---|
| Declaration of existing facilities | Company name, date, PAN, CIN, GSTIN; a table of facilities (lender, facility, sanctioned limit, outstanding, EMI) and one of bank accounts. A declaration of nil facilities is this type, declaring none | OB-01, OB-02, BA-01, BA-02; ID-01, ID-02, ID-03, ID-05 |
| Sanction letter | Lender, borrower, date, reference; a table of facilities (facility, sanctioned amount, rate, tenure, EMI) | OB-01; ID-03 |
| Commercial bureau report | Company name, PAN, CIN, GSTIN, report date, credit rank; tables of credit facilities (lender, facility, sanctioned, outstanding, overdue, status) and related parties (name, relationship, PAN) | OB-01; ID-01, ID-02, ID-03, ID-04, ID-05; the party set |

- **Recognised and read without the model.** Each type has its own classification signals and read rules (`config/ingestion/signals.yaml`, `fields.yaml`, `document_types.json`). The fields these documents print need no model call, so replay mode needs no new recordings.
- **Not on the checklist.** The cross-checks reconcile these documents rather than asking the customer for them, and the bureau report is obtained by the bank.
- **Bureau directors are parties.** Directors the bureau names join the case's party set with their PAN, as memorandum directors already do, so the checklist asks for their KYC.

### Rules

| ID | Change |
|---|---|
| OB-01 (new) | Each existing facility, by lender, in the declaration (or the RM's message), the sanction letters and the bureau report. Flagged when a facility is not declared, when a declared facility appears in no other source, or when sanctioned amounts differ by more than 5% (`facility_amount_match`, provisional). Incomplete when nothing is on file to reconcile against |
| OB-02 | The declaration of existing facilities counts as a declaration; instalments against a nil declaration are undeclared. A lender abbreviated in a bank narration ("TIDEWATER FIN") matches its full name in the declaration |
| BA-01 | Accounts listed in the declaration are declared accounts |
| BA-02 | Now "Accounts on file are declared": a statement for an account nobody declared is also flagged, once the RM or a declaration declared any account |
| ID-01, ID-02, ID-03, ID-04, ID-05 | The bureau report (and, for identifiers and name, the declaration and the sanction letter) are sources |
| ID-04 | Sources are shown in the rule's order, whatever order the documents arrived in |

### Tests

| Test | What it covers |
|---|---|
| `tests/test_crosschecks.py` | A legal-name mismatch flagged with both sides' documents (a gap found when checking TC-20) |
| `tests/test_crosschecks_areas.py` | BA-02: an undeclared statement account flagged; not flagged when nothing was declared |
| `tests/test_crosschecks_facilities.py` (new, 15 tests) | OB-01 pass, undeclared, amount mismatch, unsupported declared facility, nil declaration, message as declaration, incomplete, not applicable; OB-02 against a declaration; BA-01 from a declaration; the bureau as a source of PAN, GSTIN and the promoter set; facilities in the facts and the CAM |
| `services/ingestion/tests/test_facility_types.py` (new, 7 tests) | Each type recognised by its own signals with a clear margin, and every field and table read without a model, from PDFs built in `tests/docgen.py` |
| Reference samples | The nil-facilities declaration sample now classifies as this type, with its fields checked (74 of 74 fields correct) |
| Fixtures | The complete sample case has a declaration, a sanction letter and a bureau report that agree with its bank statement; every check passes on it with no open query |

### Corrections

- **Plan traceability.** FS-02 is no longer listed under TC-24 (bank accounts): it compares balances and does not identify an account.
- **Recorded classification answers.** The four recorded classification answers for the reference samples no longer replay, because the classification prompt now lists twelve types. No automated test uses them; re-record with the live key.

## 11. The cross-verification board (9 to 11 October 2026)

The Cross-checks tab became the cross-verification board, from the redesign brief, and on 11 October it was narrowed to the test plan's four areas.

### 11.1 Summary

- **Screen:** an overview of four areas (identity consistency, turnover, bank accounts, existing obligations), then a section per area with its discrepancies ranked by credit impact, each with its sources side by side, its evidence and a decision.
- **Decisions:** accept, dismiss or escalate, always with a comment. Submission stays blocked while a blocking discrepancy is not accepted or dismissed.
- **Rules switched off:** BR-01 to BR-04, TX-01, TX-02, FS-01 and FS-02 no longer run (they stay in configuration, section 11.3). 18 rules run.
- **No rule logic or tolerance changed.** The 18 rules that run give exactly the outcomes they gave before the redesign: outcome, explanation, sides, detail and missing documents were compared for all six cases in the local store, before and after.

### 11.2 What users see

This replaces the screen in section 2.

| Part of the screen | What it does |
|---|---|
| Header | "Appraisal <case> · Cross-verification", the title "Cross-verification and discrepancy", one line summarising the discrepancies, and a line with the decided count, the run (XR-<case>-<run>), the rules and sources compared and when. Buttons: **← Spread**, **Exception queue**, **Continue to draft** (locked while a blocking discrepancy is open) |
| Blocking banner | "Submission blocked — n serious discrepancies unadjudicated", with the most important blocking discrepancy's reference and sentence. **Adjudicate now** opens it |
| Overview | Four area cards. Each shows its open discrepancies by severity, a **Blocking** badge when one blocks, how many are decided, how many checks could not run or passed, and the top finding. A click goes to the area's section |
| Area sections | The area's discrepancies ranked by credit impact (severity, then the size of the gap in rupees), the checks that could not run (each says what would complete it, with **Add to query list**), the passed checks (collapsed, with those that did not apply), and **Facts behind these checks** (collapsed) |
| Discrepancy card | Rank, severity, **Blocks submission**, the reference (XV-<case>-<nn>) and rule, the finding in plain English and its sentence. Opened: the rule line (what is compared, the tolerance, the owner); one column per source (2 to 4) with its provenance (Declared, Borrower-supplied, Independent), headline value, what it covers, **Open the evidence** and **Trace to the source**; the gap on each leg against the tolerance, or the difference in words; the evidence panel (the extracted rows with their pages: GST returns by month with filing dates, bank credits by month and account, each excluded credit on its own line); line by line; compare side by side |
| Decision | **Accept** (a valid finding; it stays on the query list), **Dismiss** (not valid) or **Escalate** (to the Credit Manager; it stays open and blocking). A comment is required. The decision is shown with who, when and the comment |
| Review queue | An escalated finding is marked **Escalated**; only the Credit Manager can decide it, with a comment |

### 11.3 Rules switched off

| ID | Area | Effect while off |
|---|---|---|
| BR-01 to BR-04 | Borrowing authority (the board resolution) | No finding, query, CAM or PD-note entry. BR-01 no longer blocks submission |
| TX-01, TX-02 | Income tax | As above |
| FS-01, FS-02 | Financial statements | As above |

- **How:** `enabled: false` on each rule in `config/crosschecks.yaml`. The rules are still validated, and their evaluators, cards and tests remain (the tests run them switched on). Removing the line and publishing switches a rule back on.
- **On the next run** a switched-off rule's open review items are withdrawn; decided ones stay as the record.
- **References:** findings keep their references, so on cases checked before 11 October the sequence has gaps where switched-off rules' findings were.

### 11.4 Decisions

| Decision | Recorded as | Effect |
|---|---|---|
| Accept | The review item confirmed, with the comment as its reason | Decided; stays on the query list, in the CAM and the PD note |
| Dismiss | The review item waived, with the comment | Decided; leaves the query list, the CAM summary and the PD note |
| Escalate | The comment, user and time on the review item; the decision log | Stays open and blocking. Only a holder of `finding.escalation` (the Credit Manager) can then accept or dismiss it, on the board or in the review queue, with a comment |

Every decision needs a comment of at least three characters. Each is kept with the user and the time, and in the decision log (`finding.escalated`, `review.decided`, `finding.query_added`).

### 11.5 References, runs and ranking

- **Reference:** XV-<case number>-<sequence>, given to a finding the first time it fails, in ranked order, and kept on every later run whatever its outcome.
- **Run:** XR-<case number>-<run number>, with the rules that ran and the document types compared.
- **Ranking:** severity, then the size of the gap in rupees (findings without an amount after those with one), then the configured order; within each area.

### 11.6 Configuration changes

| File | Change |
|---|---|
| `config/crosschecks.yaml` | `finding_title` on every rule (the finding in plain English); optional `policy_ref` (none yet); `enabled: false` on the eight rules above |
| `config/document_types.yaml` | `provenance` on every type: declared (the RM's sourcing message, the declaration of existing facilities), independent (the commercial bureau report), borrower-supplied (the rest) |
| `config/roles.yaml` | `finding.escalation` for the Credit Manager |
| `engine/configstore/schema.py` | The three rule fields and `provenance`. Publishing requires `finding_title` and `provenance`; a version published earlier still reads (as none, and every rule enabled) |

Published to the local data root on 9 October (titles and provenance; it also made the paused policy and approval-matrix configuration live) and on 11 October (the switch), each time followed by a re-run of every case.

### 11.7 API and data

| Item | Change |
|---|---|
| Endpoints | `GET /api/cases/{id}/cross-verification` (the board); `POST /api/cases/{id}/cross-verification/findings/{finding_id}/decision` (accept, dismiss, escalate); `POST /api/cases/{id}/cross-verification/findings/{finding_id}/query` (put an incomplete check's request on the query list) |
| `Finding` | The card: `ref`, `finding_title`, `compares`, `policy_ref`, `columns` (`SourceColumn`, with `EvidenceRow` rows), `gaps` (`GapLeg`), `gap_tolerance`, `mismatch`, `reference`, `amount`, `request`. `FindingSide.sources` |
| The board | `CrossVerificationView` (`run`, `areas`, `items`, `counts`, `blocked`, `first_blocking`, `top_finding_id`), `XvArea`, `XvItem`, `XvCounts`, `XvRun`, `XvDecision`, `XvDecisionRequest` |
| `ReviewItem` | `escalated` |
| Facts | `MonthFigure.gst_filed` (the return's filing date); `AccountCredits.by_month` (`AccountMonth`: credits, excluded and net by month) |
| Database | Migration 7: `findings.card`, and the tables `finding_refs`, `crosscheck_runs` and `query_additions` (applied automatically; case delete removes their rows) |

### 11.8 Code changes

| Area | Files |
|---|---|
| The board | `engine/xv.py` (new: references, runs, the view, decisions, query additions) |
| Cards | `engine/xv_cards/` (new: `identity.py`, `numbers.py`, `accounts.py`, `obligations.py`, `authority.py`). A card is built after the rule decides; a builder that fails leaves the plain sides and never stops the checks |
| Checks | `engine/crosschecks.py`: the sources on every side, the card after each outcome, only enabled rules, references and the run recorded with the findings |
| Elsewhere in the engine | `engine/facts.py` (filing dates, credits by month), `engine/queries.py` (requests from the board), `engine/review.py` (escalated findings), `engine/reads.py`, `engine/db.py`, `engine/api.py`, `engine/configstore/schema.py` |
| Screen | `src/components/case/xv/` (new), `src/domain/crossVerification.ts` (new), `src/routes/appraisals.$caseId.cross-verification.tsx`, `src/routes/review.tsx`, `src/components/review/DecisionDialog.tsx` and `src/domain/review.ts` (the escalated finding's comment), `src/components/case/CrossVerification.tsx` (now the facts panels only), `src/api/client.ts`, `src/api/types.ts`, `terminology/rbl.yaml` |

### 11.9 Tests

| Test | What it covers |
|---|---|
| `tests/test_xv.py` (new) | References and runs; the view (areas, ranks within an area, the banner's target, the first card); decisions (comments, escalation, the Credit Manager); query additions; case delete; the card stored with the finding |
| `tests/test_xv_cards_identity.py` (new) | Identity cards: one column per document or per group, the majority value and the difference in words, people and CIN particulars, same-type documents told apart |
| `tests/test_xv_cards_numbers.py` (new) | Turnover cards: GST months with filing dates, bank credits by month and account with excluded credits, totals that reconcile with the figure, gaps that agree with the outcome, requests |
| `tests/test_xv_cards_others.py` (new) | Bank-account, obligation and board-resolution cards: per-lender gaps, the difference in words, every row's page |
| `tests/test_crosschecks_switch.py` (new) | A switched-off rule leaves no finding, review item, query, CAM or PD-note entry and blocks nothing; switching it back on restores all of it; a version published before the switch reads every rule as enabled |
| Updated | `tests/conftest.py` (card errors fail tests; `all_rules_enabled` for the switched-off rules' own tests), `tests/test_api.py` (migration 7), `tests/test_config_catalogue.py` (26 rules, 18 enabled), the cross-check tests, `tests/triangulation.py` (documents filed in order past 100) |
| `e2e/cross-verification-board.spec.ts` (new) | The header and the locked Continue, the banner and Adjudicate now, the overview cards, the sections, the card (columns, evidence, trace, gaps, the difference in words), decisions with comments, escalation, query additions, passed lists, facts, 1366 and 375 px without sideways scroll |
| Updated screen tests | `e2e/cross-verification.spec.ts`, `e2e/workspace.spec.ts`, `e2e/navigation.spec.ts`, `e2e/admin.spec.ts`; the review queue's escalated finding needs a comment |

Results on 11 October 2026:
- **Python:** 533 passed, 2 skipped. One Windows-only failure: a folder-permissions test.
- **Screen tests:** 96 of 97 passed. One Windows-only failure: the clipboard line-ending test.
- **Typecheck, lint, build and import rules:** pass.
- **Outcomes:** the 18 rules that run gave the same results as before the redesign on all six local cases.

### 11.10 Known limits

- **Same-type documents without a period.** Two documents of one type on a card are told apart by the period each covers; where extraction read none (as on two of the local cases), by page or position ("· 1 of 2").
- **Owner.** Cases have no assigned analyst, so a card's owner is whoever decided or escalated it, else "not yet assigned".
- **Policy references.** None configured until RBL supplies its policy.
- **GST heading.** "3.1(a)+(b)+(c) outward supplies" is worded in the card builder; a test ties it to the configured rows.
- **Copilot panel.** Not built; the layout leaves room for it.

### 11.11 Changes on 12 October 2026

**Key figures on the overview cards.** Each area card now shows up to three lines under its counts, from its findings: open discrepancies first, then decided ones, then checks that could not run, then passed ones. On Kestrel: the PAN AAACK1234F against the bureau's AAACK9999Z (marked); GST INR 12.00 cr against bank credits INR 9.00 cr, 25.0% apart (tolerance 10%); account ·5678 declared with no statement; Ashwood Finserv declared at INR 80.00 lakh against INR 95.00 lakh sanctioned, and Tidewater Finance not declared. A clean area shows what was confirmed ("same across 18 sources"); an incomplete one, what is missing. A line opens its check. Built by the card builders (`Finding.highlights`, `XvArea.highlights`); the screen computes nothing.

**Fixes from the adversarial review** (four reviewers, each finding checked by a second agent trying to refute it):

| Fix | Before | After |
|---|---|---|
| Escalations kept | An escalation was lost when its discrepancy stopped failing for one run (a value waiting for review), and the analyst could then decide it alone | Kept with the discrepancy (rule and scope, as its reference); it returns with the review item when the check fails again. Migration 8 adds `finding_escalations` |
| A comment for every decision | The review queue accepted or dismissed a discrepancy without a comment unless it was escalated | Every decision on a discrepancy needs a comment of at least three characters, on the board and in the queue |
| The query list follows the check | A request on the query list kept its first wording after the check's need narrowed | It asks for what the check needs now, and is resolved when the check completes or only waits for a review |
| Escalation re-checked | Escalating could overwrite an escalation, or land on a discrepancy decided a moment before | Refused (409) when already escalated or decided, checked inside the write |
| Requests for future periods | A turnover check of a year still running asked for returns and statements of months not yet passed | A check of a year not yet ended asks for nothing ("the year ends on 31 Mar 2027") |
| Wording | A value a person typed on the case read "In the sourcing message"; a name ending in a full stop gave ".." | "Entered on the case"; one full stop |
| OB-01 tolerance line | "Tolerance 5% — breached on … and Tidewater Finance Limited", though Tidewater was never measured against it | Lists only the legs measured as a percentage; the undeclared lender stays in the gap row |
| Passed list | A screen-built "variance x%", without the tolerance | The engine's sentence ("Variance 1.7% within 10%.") |
| Errors | Raw HTTP text; a refused decision left the board stale | Designed messages; the board reloads after any refusal |
| Decision log | A repeated query addition logged twice; the two new actions had no wording | Logged once; worded in terminology |

**Publishing re-runs every case.** `creditiq config publish` now re-runs every case's checks after publishing, so findings, review items, queries, the CAM and the PD note follow the new configuration at once (`--no-rerun` skips it).

**Local store.** Migration 8 applied; every case re-run. The 18 rules' outcomes on the six local cases are unchanged.

Results on 12 October 2026:
- **Python:** 551 passed, 2 skipped. One Windows-only failure: a folder-permissions test.
- **Screen tests:** 106 of 107 passed. One Windows-only failure: the clipboard line-ending test.
- **Typecheck, lint, build and import rules:** pass.

### 11.12 Later on 12 October 2026: the tax return, and the turnover figures

**The income tax return's turnover against the other sources.** Three new rules, under Turnover:

| ID | Check | Tolerance | Severity |
|---|---|---|---|
| TX-03 | Turnover in the income tax return against audited revenue | `turnover_variance` 10% | Moderate |
| TX-04 | Turnover in the income tax return against GST outward supplies (all 12 returns needed) | 10% | Moderate |
| TX-05 | Turnover in the income tax return against cleansed bank credits (all 12 months needed) | 10% | Moderate |

- **How:** the turnover the return's computation shows (`config/statements.yaml` `itr_lines`) becomes a fifth turnover figure (`itr`) for the year the return covers, and each rule compares it with one other figure for that year exactly as TO-01 to TO-04 compare theirs.
- **The returns set the years:** a return is filed after its year ends, so the latest year's figures usually have no return yet.
- **Nothing to compare:** a return that shows no turnover, or another source that does not reach the return's year, is not applicable. A missing return is asked for only when the checklist expects one. Today no live case's return shows its turnover, so these rules are not applicable on them.

**TX-01 and TX-02 back on**, shown under Turnover (`area: turnover`), so the board keeps its four areas. 29 rules are configured and 23 run; BR-01 to BR-04, FS-01 and FS-02 stay off.

**Turnover figures stand out.** A closed card with amounts (the turnover checks, a lender's sanctioned amounts) shows its figures large under its title, the lower one in red, with how far apart they are; the overview cards show amounts larger.

**Data and code.** `TurnoverSource` gains `itr` (contracts regenerated). `engine/facts.py` (the return's turnover figure), `engine/crosschecks.py` (`_itr_turnover`; the year comparison shared with TO-01 to TO-04, unchanged), `engine/configstore/schema.py` (three variables), `engine/xv_cards/numbers.py` (the return's column and key figures, and key figures for TX-01 and TX-02), `config/crosschecks.yaml`. Published to the local data root; every case re-ran.

**Test applications.** The seed script now files an FY 2025-26 return showing its turnover for Kestrel (INR 11.90 cr: TX-03 and TX-04 pass, TX-05 fails at 24.4% against INR 9.00 cr banked) and Heronbay (matching figures: all pass); both were filed into the live applications. The rules that ran before give the same outcomes on all six cases; on Heronbay the identity checks count the new return as one more source.

Results:
- **Python:** 599 passed, 2 skipped. One Windows-only failure: a folder-permissions test.
- **Screen tests:** 118 of 119 passed. One Windows-only failure: the clipboard line-ending test.
- **New tests:** `tests/test_crosschecks_tax_turnover.py` (13): each new rule against its source, pass and fail; a part year incomplete; a return without turnover and a source not reaching its year not applicable; a missing return asked for; each year on its own; the card and its key figure; TX-01 and TX-02 under Turnover. Rule-count, area and switch tests updated (26/18 to 29/23).

### 11.13 Later on 12 October 2026: names of people in full (ID-09)

**Why.** The identity checks match people by similarity, so a name missing a part passes: "Tarun S. Velankar" and "Tarun Velankar" are about 93% alike, above `name_match` (0.85). That stays as it is. A new check shows the parts.

| ID | Check | Documents | Severity |
|---|---|---|---|
| ID-09 | Names of people agree in full across documents | Director KYC, memorandum and articles, commercial bureau report | Mild, does not block |

- **How:** each person named in two or more of those documents (grouped as ID-04 groups them, or by the same surname with the same first name or its initial) has each document's name split into first, middle and last name. Each split is compared with the fullest form of the name. A part is same, missing, only an initial, or different; the order of the words is not a difference, and honorifics are ignored. Any part not the same fails, and the query asks for each person's full name as on their PAN. The sourcing message is left out, as RMs often shorten names.
- **People only.** Company names stay with ID-03.
- **On the board:** the card shows each document's people split into first, middle and last name. The overview line names the person and what differs. In the line-by-line table, the part that differs is marked in red, and a part neither name has is a plain dash.
- **ID-04, ID-06 and ID-08 are unchanged.** 30 rules are configured and 24 run (identity 9).
- **ID-09 in the plan** was the state of registration (CoI address against the GSTIN state code). That was never built, and the ID is now this check.

**Data and code.**
- `engine/names.py` (`name_parts`, `compare_name_parts`, `same_by_parts`)
- `engine/crosschecks.py` (`_person_names`; `_rows` takes the cells a row is flagged for)
- `engine/contracts/appraisal.py`: `FindingDetailRow.flagged_cells`, default empty. Contracts were regenerated.
- `engine/configstore/schema.py`: the variable `person_names`.
- `engine/xv_cards/identity.py`: the card and the overview line.
- `src/components/case/xv/LineByLine.tsx`: a flagged cell in red.
- `config/crosschecks.yaml`.

Published to the local data root; every case re-ran.

**Test applications.** The seed script now has Kestrel's bureau report name its first director "Tarun S. Velankar"; the live application was changed the same way. ID-09 fails on Kestrel ("middle name missing in KYC received and Memorandum and articles of association") and passes on Heronbay. The other rules give the same outcomes on all six cases; on Kestrel, ID-04's bureau column shows the name as written.

Results:
- **Python:** 609 passed, 2 skipped (the full suite less the known Windows-only `test_f05` cases).
- **Screen tests:** 119 of 120 passed; the one failure is the known Windows-only `e2e/tc16-query-list.spec.ts`.
- **New tests:** `tests/test_crosschecks_names.py` (17): name parts compared one by one (missing, initial, different, words in another order, honorifics), a middle name missing, an initial found where similarity misses it, a surname spelt differently, the sourcing message left out, a person in one document only, nine identity rules. A screen test marks the differing part in the table. Rule-count tests updated (29/23 to 30/24).

### 11.14 Later on 12 October 2026: tighter tolerances

| Tolerance | Before | Now | Rules |
|---|---|---|---|
| `turnover_variance` | 10% | 1% | TO-01, TO-02, TO-03, TO-05, TX-03, TX-04, TX-05 |
| `declared_turnover_variance` | 20% | 2% | TO-04 |
| `name_match` | 0.85 | 0.90 | Every name comparison, who a document belongs to, and the borrower on RBL's record |

`profit_variance` (TX-02) stays at 10%. All values remain provisional (`config/tolerances.yaml`). Published to the local data root; every case re-ran.

**On the test applications.**
- **Kestrel:** TO-01 now fails (audited INR 11.80 cr against GST INR 12.00 cr, 1.7% apart), 16 discrepancies.
- **Marigold:** TO-05 now fails (GST INR 5.04 cr against INR 4.80 cr banked over Sep 2025 to Aug 2026, 4.8% apart).
- **Heronbay** stays the clean example: its customer receipts went from INR 96 lakh to INR 97.5 lakh a month (and its supplier payments by the same amount, so the balances are unchanged). The seed script and the live application were both changed. Its turnover figures are now 0.3% to 0.8% apart.
- No outcome changed because of the name match.

**Tests.** Test figures written for the old tolerances now sit within 1% where a check is meant to pass, and the expected tolerance text reads 1% or 2% (`tests/test_crosschecks.py`, `_areas`, `_tax_turnover`, `test_xv.py`, `test_xv_cards_numbers.py`, `test_xv_highlights.py`). The complete fixture case's bank credits moved within 1% of its GST (`tests/fixtures/build_fixtures.py`; one ingest fixture regenerated, no PDF changed).

Results:
- **Python:** 624 passed, 2 skipped (the full suite less the known Windows-only `test_f05` cases).
- **Screen tests:** 119 of 120 passed; the one failure is the known Windows-only `e2e/tc16-query-list.spec.ts`.
