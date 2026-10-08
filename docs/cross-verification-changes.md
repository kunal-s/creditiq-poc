# Cross-verification: change register

| | |
|---|---|
| Date | 7 October 2026, updated 8 October 2026 (section 10) |
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

## 2. What users see

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
