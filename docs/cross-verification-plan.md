# Cross-verification: build plan for the nine document types

| | |
|---|---|
| Status | P1 and P2 implemented 7 October 2026; OB-01 and three document types added 8 October (see "Implementation status" at the end); P3 open |
| Date | 7 October 2026 |
| Governs | Stage 4 of the case workspace, the **Cross-verification** tab (`/appraisals/$caseId/cross-verification`) |
| FRD features | F-18 fact alignment, F-19 cross-checks; uses F-16 (evidence), F-17 (review), F-14 (query list), F-23/F-24 (CAM, PD note) |
| Tests served | TC-22 identity, TC-23 turnover, TC-24 bank accounts, TC-25 obligations; criteria C4, C5, C7 |
| Document scope | The nine types below, plus the case record (the RM's sourcing message). Extended on 8 October with the declaration of existing facilities, the sanction letter and the commercial bureau report |

---

## Contents

1. Scope
2. Where we start
3. Gaps found
4. Target rule catalogue
5. Engine work
6. Configuration work
7. Contract changes
8. Screen work
9. Tests
10. Build order and milestones
11. Decisions needed
12. Risks
13. Traceability
- Appendix A: what each document contributes
- Appendix B: rule cards

---

## 1. Scope

**In scope: these nine document types** (ids as in [config/document_types.yaml](../config/document_types.yaml)):

| # | Document | Type id |
|---|---|---|
| 1 | Certificate of Incorporation | `certificate_of_incorporation` |
| 2 | Memorandum and Articles of Association | `memorandum_articles_of_association` |
| 3 | Company PAN | `company_pan` |
| 4 | Director KYC: ID and address proof | `director_kyc` |
| 5 | Board Resolution for Borrowing | `board_resolution_borrowing` |
| 6 | Audited Financial Statements | `audited_financial_statements` |
| 7 | Income Tax Return, with computation and acknowledgement | `income_tax_return` |
| 8 | GST Return, GSTR-3B | `gstr_3b` |
| 9 | Bank Statement, last 12 months | `bank_statement` |

The **case record** is also a source. It holds what the RM declared in the sourcing message (F-04): PAN, GSTIN, CIN, promoters, declared turnover, existing banking, amount and constitution. It is the "declared" side of several checks. It is labelled "Sourcing message" on screen.

**Out of scope for this plan:**
- Rules that need a document type outside the nine: bureau report, declaration of existing facilities, sanction letters, GST registration certificate, GSTR-1, partner GST and bank-analysis reports, and provisional statements. FRD rule **OB-01** is the only minimum rule affected. It was **deferred** (§4.7), then built on 8 October once the declaration, sanction-letter and bureau types were added (see "Implementation status").
- Per-document validation, such as a checksum, a date in order or a balance-sheet total. That is F-15 and F-17, done in the document-processing service ([config/ingestion/validators.yaml](../config/ingestion/validators.yaml)).
- Checklist sufficiency, such as the number of returns, statement months or document age. That is F-13 ([engine/completeness.py](../engine/completeness.py)).

Cross-verification compares **one document's values with another's**, or with the case record.

---

## 2. Where we start

A working first cut already exists end to end. This plan extends it rather than replacing it.

| Layer | What exists | Where |
|---|---|---|
| Fact alignment (F-18) | Identities by document (PAN, GSTIN, legal name); promoter sets by source; turnover by financial year from financials, GST, cleansed bank credits and the message; credit cleansing with every exclusion kept; inferred EMI obligations; the account set | [engine/facts.py](../engine/facts.py), contracts in [engine/contracts/facts.py](../engine/contracts/facts.py) |
| Rules (F-19) | ID-01 to ID-04 and TO-01 to TO-04 configured and evaluated. Outcomes are pass, fail, incomplete or not applicable. Findings record both sides with evidence, reliance on a person's entry, tolerance, explanation and query | [config/crosschecks.yaml](../config/crosschecks.yaml), [engine/crosschecks.py](../engine/crosschecks.py) |
| Variables declared, no rule or evaluator | `declared_accounts_with_statements`, `evidenced_accounts_declared`, `facilities_reconcile`, `emis_to_declared_lenders` | [engine/configstore/schema.py](../engine/configstore/schema.py) `CrossCheckVariable` |
| Tolerances | Turnover 10%, declared turnover 20%, name similarity 0.85, EMI amount 5%, EMI occurrences 3 (all provisional) | [config/tolerances.yaml](../config/tolerances.yaml) |
| Alignment rules | Financial-year start, credit exclusions, EMI cues, name noise words | [config/alignment.yaml](../config/alignment.yaml) |
| Running | Every document change and every review decision calls `refresh_case`, which re-runs the checks and replaces the findings. Stable finding ids; open review items withdrawn when a finding stops failing | [engine/pipeline.py](../engine/pipeline.py) `refresh_case`, [engine/review.py](../engine/review.py) |
| Downstream | A failure raises a `finding` review item (confirm as valid or waive with a reason); a failure with a `query` joins the pre-login query list until waived; PD questions; CAM cross-verification section; stage progress | [engine/queries.py](../engine/queries.py), [engine/pd_note.py](../engine/pd_note.py), [engine/cam.py](../engine/cam.py), [engine/progress.py](../engine/progress.py) |
| API | `GET /api/cases/{id}/facts`, `GET /api/cases/{id}/findings` | [engine/api.py](../engine/api.py) |
| Screen | Findings panel filtered by outcome, with the sides, evidence links, the manual-entry flag and a valid / not-valid decision; facts panels for turnover, credits, obligations and accounts | [src/components/case/CrossVerification.tsx](../src/components/case/CrossVerification.tsx), [src/routes/appraisals.$caseId.cross-verification.tsx](../src/routes/appraisals.$caseId.cross-verification.tsx) |
| Tests | 15 cross-check tests (TC-22, TC-23, F-19.4 to F-19.6), 8 fact tests, e2e workspace checks | [tests/test_crosschecks.py](../tests/test_crosschecks.py), [tests/test_facts.py](../tests/test_facts.py), [e2e/workspace.spec.ts](../e2e/workspace.spec.ts) |

---

## 3. Gaps found

Each gap was found by reading the code and the nine extraction schemas ([config/ingestion/document_types.json](../config/ingestion/document_types.json)).

| # | Gap | Effect | Fix in |
|---|---|---|---|
| G-1 | **Unreviewed values feed findings.** `facts.load_documents` reads field values in status `in_review`. F-17.2 requires a low-confidence key field to be reviewed *before* triangulation uses it | A finding can rest on a value nobody has confirmed | E-1 |
| G-2 | **ID-01 lists a source that cannot contribute.** Audited financial statements have no `pan` field. GSTR-3B has no PAN field, but every GSTIN carries the PAN in characters 3 to 12, and that is not used | ID-01 compares only the PAN card, the ITR and the message | R-ID-01 |
| G-3 | **No CIN check.** CIN is extracted from the Certificate of Incorporation and the MOA, and the case record holds one. Nothing compares them | A TC-22 identifier mismatch goes unflagged | R-ID-05 |
| G-4 | **The board resolution's authorised persons are treated as the promoter set.** `party_list` on `board_resolution_borrowing` is `authorized_persons` with role `director`, so ID-04 demands set equality between signatories and directors | A false finding when only some directors are authorised, or when a non-director signs | R-ID-04, R-BR-02 |
| G-5 | **The MOA names subscribers and first directors,** not necessarily today's board. ID-04 holds it equal to the KYC received | False findings on older companies | Decision D-3 |
| G-6 | **DINs are extracted but never compared** (MOA `directors[].din`, KYC `din`) | A KYC for the wrong person with a similar name passes | R-ID-06 |
| G-7 | **Board-resolution content is not checked against the case:** borrowing limit against the amount requested, lender named, signatories, date | The most common sanction-stage document defect is missed | R-BR-01 to R-BR-04 |
| G-8 | **Turnover rules compare whole financial years only.** The file usually holds the latest 12 months of statements and returns, for example September to August, so TO-01 and TO-02 mostly end **incomplete** | TC-23 shows little beyond "incomplete" on a typical file | R-TO-05 |
| G-9 | **GST turnover is table 3.1 row (a) only** (taxable supplies). Zero-rated and nil-rated or exempt supplies are excluded | Exporters and mixed suppliers show false variances | Decision D-8 |
| G-10 | **The ITR is used for identity only.** `assessment_year`, `total_income` and the `income_computation` table are extracted but not compared with the audited statements | Tax-versus-books differences go unflagged | R-TX-01 to R-TX-03 |
| G-11 | **Audited statements are not compared with each other.** The previous-year column of FY N is never checked against the FY N−1 statements | Restated or substituted accounts go unflagged | R-FS-01 |
| G-12 | **BA and OB rules have variables but no evaluator.** `CaseFacts.facilities` is always empty, and `declaration_received` is always false | TC-24 and TC-25 are not demonstrable | R-BA-01, R-BA-02, R-OB-02, R-OB-03 |
| G-13 | **The year-end bank balance is not compared with the audited cash-and-bank figure** | An undisclosed account is caught only through transfer narrations | R-FS-02 |
| G-14 | **"Not applicable" is used where "incomplete" is meant.** `_exact` returns not applicable when fewer than two sources state a value, even when the checklist expects the missing document | F-19.3 wants the missing coverage named | E-2 |
| G-15 | **The evaluator is hard-coded per variable** (`evaluate` dispatch, `TURNOVER_PAIRS`). Containment and presence are not implemented generically | Each new rule needs new code, not just configuration (F-19.1) | E-3 |
| G-16 | **The screen lists findings by outcome only.** It has no grouping by area, no side-by-side evidence (F-16.2 is in [backlog.md](backlog.md)) and no identity or people panels | Reviewers cannot see one area at a time or both sources at once | §8 |

---

## 4. Target rule catalogue

**Priority:**
- **P1:** needed for TC-22 to TC-25 with these nine types. The FRD minimum, adapted to the nine types.
- **P2:** high value, needs only the nine types.
- **P3:** later.

**Status:**
- **Exists:** keep as is.
- **Change:** adjust config or code.
- **New:** build.
- **Deferred:** needs a type outside the nine.

Severity and blocking are proposals for D-7. Field names are the extraction schema's. Full rule cards are in Appendix B.

### 4.1 Identity (TC-22)

| ID | Check | Sources and fields | Comparison | Severity | Status | Priority |
|---|---|---|---|---|---|---|
| ID-01 | Entity PAN consistent | `company_pan.pan`; `income_tax_return.pan`; PAN inside each `gstr_3b.gstin` (characters 3 to 12); case PAN | exact | serious, blocks | Change: add the GSTIN-derived PAN, drop financials from `sources` (G-2) | P1 |
| ID-02 | GSTIN consistent | `gstr_3b.gstin` on every return; case GSTIN | exact | serious, blocks | Exists | P1 |
| ID-03 | Legal name consistent | `company_name` (CoI, MOA, PAN, board resolution, financials); `income_tax_return.taxpayer_name`; `gstr_3b.legal_name`; `bank_statement.account_holder_name` | normalised match at least `name_match` | moderate | Change: accept a bank's truncated holder name when it is a prefix of the legal name; never read the GST `trade_name` | P1 |
| ID-04 | Promoter set consistent | `director_kyc.person_name` (KYC received); case promoters; MOA `directors[].name` per D-3 | set equality | serious, blocks | Change: remove board-resolution signatories from the set (G-4) | P1 |
| ID-05 | CIN consistent | `certificate_of_incorporation.cin`; `memorandum_articles_of_association.cin`; case CIN; optionally `cin` on the financials and board resolution (D-6) | exact | serious, blocks | New | P1 |
| ID-06 | Director identifiers agree | Per person, matched by name: MOA `directors[].din` against `director_kyc.din`; `director_kyc.pan` is an individual PAN (fourth character P) and is not the entity PAN | exact, per person | moderate | New | P2 |
| ID-07 | Incorporation particulars agree | CIN parts (year, `PTC`/`PLC`/`OPC` class, listed `L` or unlisted `U`) against `certificate_of_incorporation.date_of_incorporation` and `company_type` and the case constitution | exact | mild | New | P2 |
| ID-08 | Memorandum directors accounted for | MOA `directors[]` contained in the KYC received plus the case promoters (only if D-3 takes MOA out of ID-04) | containment | mild | New | P2 |
| ID-09 | State of registration | State in the CoI `registered_address` against the GSTIN state code (configured code table) | exact | mild, informational | New | P3 |

### 4.2 Borrowing authority (board resolution)

| ID | Check | Sources and fields | Comparison | Severity | Status | Priority |
|---|---|---|---|---|---|---|
| BR-01 | Resolution covers the amount requested | `board_resolution_borrowing.borrowing_limit` at least the case `amount_inr` | bound (D-4) | serious, blocks | New | P2 |
| BR-02 | Signatories are directors | `authorized_signatories` and `authorized_persons` contained in the KYC received plus MOA directors | containment | moderate | New | P2 |
| BR-03 | Resolution is in favour of this bank | `lender_name` matches a configured own-bank name | normalised match | moderate | New | P2 |
| BR-04 | Resolution dated within the company's life | `date_of_incorporation` (CoI) on or before `resolution_date`, on or before the case `as_of` (never the wall clock) | order | mild | New | P2 |

### 4.3 Turnover (TC-23)

| ID | Check | Sources and fields | Comparison | Severity | Status | Priority |
|---|---|---|---|---|---|---|
| TO-01 | Audited turnover against GST, same financial year | Revenue from operations ([config/statements.yaml](../config/statements.yaml)); sum of GSTR-3B 3.1 values for the year | tolerance `turnover_variance` | moderate | Change: which 3.1 rows count (D-8) | P1 |
| TO-02 | GST against cleansed bank credits, same financial year | As today | tolerance | moderate | Exists | P1 |
| TO-03 | Audited turnover against cleansed bank credits | As today | tolerance | moderate | Exists | P1 |
| TO-04 | RM-declared against evidenced turnover | As today | tolerance `declared_turnover_variance` | mild | Exists | P1 |
| TO-05 | GST against cleansed bank credits, **months both cover** | Months present in both GST returns and statements, in any financial year; the total over the window plus a month-by-month list | tolerance `turnover_variance` | moderate | New (G-8) | P1 |

### 4.4 Tax (ITR against the books)

| ID | Check | Sources and fields | Comparison | Severity | Status | Priority |
|---|---|---|---|---|---|---|
| TX-01 | Each audited year has its return | Financial years of the audited statements contained in `income_tax_return.assessment_year` minus one | containment | mild | New | P2 |
| TX-02 | Profit in the return agrees with the books | Profit before tax (financials) against the ITR computation row "profit before tax as per profit and loss account" (configured pattern) | tolerance `profit_variance` | moderate | New | P2 |
| TX-03 | Turnover in the return agrees with the books | Revenue from operations against the ITR computation's turnover or gross-receipts row, where printed | tolerance `turnover_variance` | moderate | New | P3 |

### 4.5 Financial statements against each other and the bank

| ID | Check | Sources and fields | Comparison | Severity | Status | Priority |
|---|---|---|---|---|---|---|
| FS-01 | Comparatives agree with the previous year's statements | `previous_period` of FY N against `current_period` of FY N−1, for revenue, PAT, net worth and total borrowings | tolerance `comparatives_variance` | moderate | New | P2 |
| FS-02 | Year-end bank balances within the audited figure | Sum of statement balances on the last day of the financial year, across accounts, at most the audited `cash_and_bank_balances` (which also includes cash and deposits) | bound + tolerance | mild | New | P2 |

### 4.6 Bank accounts (TC-24)

| ID | Check | Sources and fields | Comparison | Severity | Status | Priority |
|---|---|---|---|---|---|---|
| BA-01 | Declared accounts have statements | Accounts named in the case `existing_banking`, contained in the `bank_statement` accounts (last four digits plus bank) | containment | moderate | New: variable exists, no rule (D-5) | P1 |
| BA-02 | Accounts on file are declared | Every account in the account set (F-18.5): one seen only in transfers, and one with a statement once any account was declared, must be declared | containment | moderate | New; widened 8 October | P1 |
| BA-03 | GST paid in cash appears in the bank | GSTR-3B `tax_payment` cash amounts against GST debits in the statements in the filing window | tolerance | mild | New | P3 |

### 4.7 Obligations (TC-25)

| ID | Check | Sources and fields | Comparison | Severity | Status | Priority |
|---|---|---|---|---|---|---|
| OB-01 | Declared facilities reconcile with sanction letters and bureau | Each facility, by lender, in the declaration of existing facilities (or the sourcing message), the sanction letters and the bureau report; sanctioned amounts within `facility_amount_match` | set equality | serious | Built 8 October, with the three document types | P1 |
| OB-02 | EMIs go to declared lenders | Inferred obligations (F-18.4), contained in the lenders named in the case `existing_banking` | containment | serious | New (D-5) | P1 |
| OB-03 | Borrowings in the books are serviced in the bank | Financials `total_borrowings` and `finance_costs` above zero, with no inferred obligation (or the reverse: EMIs with no borrowings in the latest audited year) | presence, both ways | moderate | New | P2 |

**Totals:** P1 has 13 rules (8 exist or change, 5 new). P2 has 11 new rules. P3 has 3. One rule is deferred.

---

## 5. Engine work

### E-1. Review gating before triangulation (G-1, F-17.2)

- **Change:** carry each field value's status into `facts.Value`. A value with status `in_review` is **not yet usable**.
- **Effect on a rule:** a rule that would use the value returns `incomplete`, with the note "waiting for review of {field} on {document}". The side links to the field so it can be confirmed in place. A confirmed or corrected value re-runs the case through the existing `refresh_case` path.
- **Alternative:** see D-2.
- **Tests:** a low-confidence PAN does not produce an ID-01 failure until it is confirmed; after correction, the finding uses the corrected value and says it relies on a person's entry (F-19.4).

### E-2. Outcome semantics (G-14, F-19.3)

- **pass:** at least two sources, all within tolerance.
- **fail:** at least two sources disagree.
- **incomplete:** at least one expected source is missing, partial (months short) or awaiting review. The note names it.
- **not applicable:** the rule cannot apply to this case. Examples: a constitution with no CIN, or no turnover declared.
- **Expected sources** come from the case's derived checklist ([engine/checklist.py](../engine/checklist.py)). If the checklist requires a source type and it is absent, the outcome is incomplete, not not applicable.
- The incomplete note links to the Completeness tab's query list entry for the missing document.

### E-3. A generic rule evaluator (G-15, F-19.1)

- Split evaluation into two parts:
  - **Fact selectors:** a variable maps to a function that returns sides.
  - **Comparators:** one per comparison type.
- Comparators: `exact`, `tolerance`, `set_equal`, `set_contains`, `presence`, plus `bound` (at least or at most, with optional tolerance) and `order` (dates in sequence) if D-4 agrees.
- **Scope:** a rule may run once, or once per financial year, person, account or month window. Finding ids stay `stable_id(case, rule, scope)`, so decisions survive re-runs.
- **Files:** keep [engine/crosschecks.py](../engine/crosschecks.py) as the entry point (`run`, `evaluate`). If selectors move to a new module, for example `engine/crosscheck_selectors.py`, add it to the runtime packages in [.importlinter](../.importlinter) (CLAUDE.md rule 4).
- `TURNOVER_PAIRS` becomes data in the selector table. The behaviour of the existing ID and TO rules must not change. Their tests pass unmodified.

### E-4. Facts to add (F-18)

All additive to `CaseFacts`, each keeping `field_ids` and evidence (F-18.6):

| Fact | Built from | Used by |
|---|---|---|
| `identities.cin` | CoI, MOA (and the financials and board resolution if D-6), case | ID-05, ID-07 |
| `identities.entity_pan` from GSTIN | Characters 3 to 12 of each GSTR-3B GSTIN, labelled "GSTIN {gstin}" | ID-01 |
| `incorporation` | CoI `date_of_incorporation`, `company_type`, `registered_address`; CIN parts decoded with [engine/identifiers.py](../engine/identifiers.py) | ID-07, ID-09, BR-04 |
| `persons` as structured entries | Per source, each person with name, DIN, PAN and role. Today it is a list of names only | ID-04, ID-06, ID-08, BR-02 |
| `authority` | Board resolution: `borrowing_limit`, `lender_name`, signatories, `resolution_date` | BR-01 to BR-04 |
| `tax_years` | Per ITR: assessment year, financial year, configured computation lines (profit before tax, turnover), `total_income` | TX-01 to TX-03 |
| `financials_by_year` | Per audited year, both columns of the configured lines (`current_period`, `previous_period`) | FS-01, FS-02, OB-03 |
| `gst_by_month` and `bank_credits_by_month` | Already computed inside `_turnover` and `_cleanse`; expose them per month | TO-05 |
| `balances_at` | Per account, the running balance on a date (financial-year end), from the transactions table | FS-02 |
| `declared_accounts`, `declared_lenders` | Parsed from the case `existing_banking` (today only account numbers are parsed, in `_accounts`) | BA-01, OB-02 |
| `gst_payments` | GSTR-3B `tax_payment` by period, and GST-cue debits in the statements | BA-03 |

### E-5. Finding area and scope

- Add `area` to `Finding`: one of `identity`, `authority`, `turnover`, `tax`, `financials`, `accounts`, `obligations`. It is taken from the rule's configuration, for grouping on screen and in the CAM.
- Add `scope` (for example "FY 2025-26", a director's name, or an account such as "·1234"), so the screen can show it without parsing the title.

### E-6. Downstream (already wired; extend through configuration)

| Consumer | What to do |
|---|---|
| Query list (F-14, F-19.5) | Give each new rule that needs the customer's explanation a `query` template. Waiving keeps today's behaviour |
| Checklist (F-19.5) | Blocking failures already show on the Completeness summary. Confirm that new blocking rules (D-7) appear there |
| Review queue (F-17.4) | No change: failures raise `finding` items; confirm or waive |
| PD note (F-24) | Give each new rule a `pd_question` |
| CAM (F-23) | Group the cross-verification section by `area`, failures first, with citations (today it is one flat list) |
| Policy (F-20) | No change. FR-03 already uses inferred obligations; OB-03 must not double-count them |

### E-7. Determinism and order

- No wall clock (FRD principle 8): BR-04 and FS-02 use `as_of` and financial-year end dates only.
- Order independence (FRD §5): add a test that one-by-one upload in shuffled order gives the same findings as bulk upload.
- Every finding keeps the configuration version that produced it (exists).

---

## 6. Configuration work

Configuration is published as a new immutable version (FRD principle 3). Every case is then re-run.

| File | Change |
|---|---|
| [config/crosschecks.yaml](../config/crosschecks.yaml) | Add the P1 and P2 rules from §4 with `area`, `sources`, `comparison`, `tolerance`, `severity`, `blocking`, `explanation`, `query` and `pd_question`. Correct the ID-01 sources (G-2) and ID-04 sources (G-4) |
| [engine/configstore/schema.py](../engine/configstore/schema.py) | Extend `CrossCheckVariable` with the new variables; add `area` and `scope` to `CrossCheckRule`; add `bound` and `order` to `comparison` (D-4). This is a schema change, so the configuration catalogue tests ([tests/test_config_catalogue.py](../tests/test_config_catalogue.py)) must be updated |
| [config/tolerances.yaml](../config/tolerances.yaml) | Add `profit_variance` (proposed 10%), `comparatives_variance` (1%) and `balance_variance` (1%), all `source: provisional` until RBL confirms (D-1) |
| [config/alignment.yaml](../config/alignment.yaml) | Add: `own_bank_names` for BR-03; `gst_payment_narration_any` for BA-03; `bank_holder_prefix_match: true` for ID-03; a GST state-code table for ID-09; lender words for parsing `existing_banking` |
| [config/statements.yaml](../config/statements.yaml) | Add `itr_lines` (profit before tax, turnover or gross receipts patterns in `income_computation`); make `gst_outward` a list of 3.1 rows (D-8) |
| [config/ingestion/document_types.json](../config/ingestion/document_types.json) and `fields.yaml` | Only if D-6 agrees: add an optional `cin` to `audited_financial_statements` and `board_resolution_borrowing`. **Changing a schema changes the extraction prompt, so recorded model answers miss and must be re-recorded** (CLAUDE.md rule 6) |
| [terminology/rbl.yaml](../terminology/rbl.yaml) | Area names, new panel titles, the "waiting for review" and side-by-side labels. Every label goes through `t()`. Run `npm run check:terms` |

---

## 7. Contract changes

All additive. The order is the one in [backlog.md](backlog.md): change [engine/contracts](../engine/contracts), run `npm run gen:api`, then confirm with `npm run check:contracts`.

| Model | Addition |
|---|---|
| `Finding` | `area`, `scope` |
| `FindingSide` | `awaiting_review: bool`, `field_ids: list[str]` (for in-place confirmation), `rows: list[...]` (optional detail lines: months for TO-05, people for ID-04, ID-06 and BR-02) |
| `CaseFacts` | `identities.cin`, structured `persons`, `incorporation`, `authority`, `tax_years`, `financials_by_year`, `balances`, `declared_accounts`, `declared_lenders` |

The document-processing service's contract does not change unless D-6 adds fields.

---

## 8. Screen work: the Cross-verification tab

Roles: Credit Analyst and Credit Manager. Desktop only (FRD §6). Mock of the target:

```text
┌ Cross-checks · 24 rules · 4 findings · 3 incomplete · 15 passed ─────────────────┐
│ [Findings 4] [Incomplete 3] [Passed 15] [Not applicable 2]                       │
│                                                                                  │
│ Identity (1)                                                                     │
│  ● Serious · blocks   CIN differs between documents                       ID-05  │
│      Certificate of Incorporation  U28990MH2015PTC123456          → p1           │
│      Memorandum and Articles       U28990MH2015PTC123465          → p2           │
│      [Compare side by side]   [Valid] [Not valid…]                               │
│ Borrowing authority (1)                                                          │
│  ● Serious · blocks   Resolution covers the amount requested              BR-01  │
│      Board resolution limit INR 2.00 cr  ·  Amount requested INR 3.50 cr         │
│ Turnover (2)                                                                     │
│  ● Moderate   GST vs bank credits · Sep 2025 – Aug 2026                   TO-05  │
│      GST INR 11.76 cr (12 returns)   Bank INR 9.48 cr (·1234)   19.4% vs 10%     │
│      ▸ Month by month                                                            │
│ Bank accounts · Obligations · Tax · Financial statements  (nothing failed)       │
└──────────────────────────────────────────────────────────────────────────────────┘
┌ Facts behind the checks ─────────────────────────────────────────────────────────┐
│ [Identity] [People] [Authority] [Turnover] [Credits] [Obligations] [Accounts]    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

| # | Work | Notes |
|---|---|---|
| S-1 | Group findings by `area` within the outcome filter, with a count per area | Keep the filter on fail by default, as today |
| S-2 | **Side-by-side evidence (F-16.2)**: "Compare side by side" opens the viewer with both sides' source pages | In [backlog.md](backlog.md) under Screens; extend [src/components/docviewer/DocViewer.tsx](../src/components/docviewer/DocViewer.tsx) |
| S-3 | Detail rows on a side: month-by-month (TO-05), person by source (ID-04, ID-06, BR-02), years (FS-01, TX-01) | From `FindingSide.rows` |
| S-4 | "Waiting for review" state: a side with `awaiting_review` links to the field and confirms it in place, reusing [src/components/review/FieldDecision.tsx](../src/components/review/FieldDecision.tsx) | E-1 |
| S-5 | Incomplete rows name the missing source and link to the Completeness tab or the upload | E-2 |
| S-6 | New facts panels. **Identity:** a document × PAN, GSTIN, CIN and name matrix, with differing cells marked. **People:** person × source, with DIN and PAN. **Authority:** the board resolution's terms against the case. **Tax:** ITR years against audited years | Existing turnover, credits, obligations and accounts panels stay |
| S-7 | Manual-entry and correction flag on every side that uses one (exists; keep it for new rules) | F-19.4 |
| S-8 | Overview and stage progress counts include the new rules (no code change expected; verify) | [src/components/case/StageProgress.tsx](../src/components/case/StageProgress.tsx) |
| S-9 | The tab says what it is waiting for when nothing has run (exists: `crossCheck.emptyDescription`) | FRD §6 |

---

## 9. Tests

| Layer | What | Where |
|---|---|---|
| Engine, per rule | For each rule: pass, fail (values and evidence on both sides), incomplete (missing source named), not applicable. Use the helpers in [tests/triangulation.py](../tests/triangulation.py) | `tests/test_crosschecks.py` (split by area if it grows past ~600 lines) |
| Engine, facts | Each new fact keeps its `field_ids` and evidence; the GSTIN-derived PAN; structured persons; balance on a date; month windows | `tests/test_facts.py` |
| Engine, gating | E-1: no finding from an `in_review` value; correction flows through | new tests |
| Engine, F-19.6 | Changing each new tolerance changes exactly the findings that use it | extend `test_changing_one_tolerance_changes_exactly_its_findings` |
| Engine, order | Bulk upload against shuffled one-by-one upload gives identical findings | new test |
| Fixtures | Extend [tests/fixtures/build_fixtures.py](../tests/fixtures/build_fixtures.py) with planted discrepancies: CIN digits swapped, board-resolution limit below the request, a signatory who is not a director, restated comparatives, ITR profit off by 15%, a transfer to an account with no statement, an EMI to an undeclared lender. **Fictional names only; no real company or lender** (CLAUDE.md rule 8). Regenerate the stub ingest results in `tests/fixtures/ingest/` | |
| Config | The catalogue accepts the new comparison types and variables, and rejects an unknown one | `tests/test_config_catalogue.py` |
| Contracts | `npm run check:contracts` clean after `gen:api` | |
| Screens | e2e mocks ([e2e/fixtures/data.ts](../e2e/fixtures/data.ts), [e2e/support/api.ts](../e2e/support/api.ts)) gain areas, rows and `awaiting_review`. Tests: area grouping, side-by-side viewer opens two pages, the evidence click test samples finding sides (TC-21) | `e2e/workspace.spec.ts` or a new `e2e/tc22-tc25-cross-verification.spec.ts` |
| Service | Only if D-6: schema tests plus re-recorded answers | `services/ingestion/tests` |
| Gate | `npm run check` passes before each milestone is handed back | |

---

## 10. Build order and milestones

Stop for sign-off at each milestone (CLAUDE.md, "work feature by feature … stop for the user's sign-off").

| Milestone | Delivers | Acceptance |
|---|---|---|
| **M0. Decisions** | Answers to D-1 to D-8 | Recorded in this file (§11) and, where the FRD changes, in FRD C.4 |
| **M1. Foundations** | E-1 gating, E-2 outcome semantics, E-3 generic evaluator, E-5 `area` and `scope`, schema and contract additions | The existing 15 cross-check tests pass unchanged; new gating and outcome tests pass; `check:contracts` clean |
| **M2. Identity** | ID-01 change, ID-03 change, ID-04 change, ID-05 (P1); ID-06, ID-07, ID-08 (P2) | TC-22: PAN, GSTIN, CIN, name and promoter mismatches flagged with their sources; no false finding from board-resolution signatories |
| **M3. Borrowing authority** | BR-01 to BR-04 | A limit below the request blocks; a non-director signatory is flagged; dates use `as_of` |
| **M4. Turnover, tax, statements** | TO-05; TO-01 GST rows (D-8); TX-01, TX-02; FS-01 | TC-23 on a typical non-aligned 12-month file shows a compared window, not only "incomplete"; restated comparatives flagged |
| **M5. Accounts and obligations** | BA-01, BA-02, OB-02 (P1); FS-02, OB-03 (P2) | TC-24: accounts without statements and undeclared accounts identified. TC-25 (partial, OB-01 deferred): EMIs to undeclared lenders identified |
| **M6. Screen** | S-1 to S-9, terminology | Analyst can review each area, open both sources side by side, confirm a waiting value in place; `check:terms` clean |
| **M7. Hardening** | Fixtures, e2e, order-independence test, CAM grouping, configuration published as a new version, all cases re-run | `npm run check` passes; findings on the fixture cases match the planted discrepancies one for one (C4, C5 readiness) |

P3 rules (ID-09, TX-03, BA-03) follow M7 if time allows.

---

## 11. Decisions needed

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D-1 | Tolerances (test plan open point 3) | RBL's working values, or the provisional ones | Keep provisional values (§6) marked `source: provisional`; replace them when RBL supplies its own, then re-run |
| D-2 | What a rule does with a value awaiting review (F-17.2) | (a) Outcome incomplete, "waiting for review", as in E-1; (b) evaluate, and mark the side provisional | (a): it is what F-17.2 says, and it keeps findings trustworthy for C5 |
| D-3 | Which source is the current board | MOA directors are subscribers or first directors; none of the nine types is a current director list | ID-04 = KYC received against case promoters (set equality, blocking). MOA directors checked by ID-08 (containment, mild), so an MOA-only name becomes a question, not a blocking failure |
| D-4 | Add `bound` and `order` comparison types | F-19.1 lists five types | Add both and record the FRD amendment in C.4; BR-01, BR-04 and FS-02 need them |
| D-5 | Is the sourcing message the "declaration" for BA-01 and OB-02 until a declaration type exists? | Yes, or defer both rules | Yes, labelled "Sourcing message". If the message names no accounts or lenders: BA-01 not applicable; OB-02 incomplete, listing the inferred lenders "to confirm" |
| D-6 | Extract `cin` from the audited statements and the board resolution | Adds an ID-05 source; costs a re-recording | Defer to after M2; ID-05 works from the CoI, MOA and case |
| D-7 | Which rules block credit review | — | ID-01, ID-02, ID-04, ID-05 and BR-01 block; all others do not |
| D-8 | GSTR-3B 3.1 rows that count as turnover | (a) only (today); (a)+(b)+(c) | (a) taxable + (b) zero-rated + (c) nil-rated and exempt; exclude (d) inward reverse charge and (e) non-GST |

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Recorded model answers are keyed on the prompt, so any extraction schema change (D-6) causes replay misses | Keep D-6 out of the critical path; re-record in one batch with the live key |
| GST and statement windows rarely align with the financial year | TO-05 compares the months both cover; TO-01 to TO-03 stay for audited years |
| Bank holder names are truncated or abbreviated | Prefix allowance (ID-03 change) and name-noise words; tests with truncated names |
| Narration-based inference (transfers, EMIs) is noisy across banks | Every inference keeps its transactions as evidence; reviewers waive with a reason; noise rules are configuration |
| Inferred EMIs from NBFCs or individuals named loosely in narrations | OB-02 is containment with name resolution (F-18.3); unmatched lenders become a query, and severity is reviewed after the first RBL case |
| Many incompletes on partial files make the tab look broken | E-2 names exactly what is missing and links to the query list; incompletes are a separate filter |
| `facts.compute` runs several times per refresh (checks, CAM, policy) | Acceptable at PoC volumes; cache per refresh only if timing shows a problem |

---

## 13. Traceability

| Test / criterion | Rules |
|---|---|
| TC-22 identity | ID-01 to ID-09; the bureau report is a source of ID-01, ID-02, ID-03, ID-04 and ID-05 |
| TC-23 turnover | TO-01 to TO-05, TX-03, supported by FS-01 |
| TC-24 bank accounts | BA-01, BA-02 (FS-02 compares balances; it does not identify an account) |
| TC-25 obligations | OB-01, OB-02, OB-03 |
| C4: at least 85% of RBL's evidenced discrepancies found | All rules; measured by the scorecard (F-26) |
| C5: at least 85% of flags accepted as valid | E-1 gating, D-3, D-5 and the valid / not-valid decision on every finding |
| C7: evidence links | Every side carries evidence; side-by-side viewer (S-2); click test |

---

## Implementation status

Built on 7 October 2026, on the recommendations in §11 (D-1 to D-8 taken as recommended; D-6 deferred).

| Item | State | Where |
|---|---|---|
| P1 rules: ID-01 (GSTIN-derived PAN), ID-02, ID-03 (truncated bank names), ID-04 (KYC against the sourcing message), ID-05, TO-01 to TO-05, BA-01, BA-02, OB-02 | Done | [config/crosschecks.yaml](../config/crosschecks.yaml), [engine/crosschecks.py](../engine/crosschecks.py) |
| P2 rules: ID-06, ID-07, ID-08, BR-01 to BR-04, TX-01, TX-02, FS-01, FS-02, OB-03 | Done | same |
| OB-01, and BA-02 widened to statement accounts that were not declared | Done 8 October | [config/crosschecks.yaml](../config/crosschecks.yaml), [engine/crosschecks.py](../engine/crosschecks.py) |
| Document types: declaration of existing facilities, sanction letter, commercial bureau report, each with signals, read rules and a schema; no checklist item (the cross-checks reconcile them, and the bureau report is obtained by the bank) | Done 8 October | [config/document_types.yaml](../config/document_types.yaml), [config/ingestion/](../config/ingestion/) |
| P3 rules: ID-09, TX-03, BA-03 | Open | — |
| E-1 review gating, E-2 outcome semantics, E-3 one evaluator per variable, E-4 facts, E-5 area and scope | Done | [engine/facts.py](../engine/facts.py), [engine/crosschecks.py](../engine/crosschecks.py), [engine/contracts](../engine/contracts) |
| Contracts: `Finding.area`, `scope`, `detail`, `missing`; `FindingSide.awaiting_review`, `differs`, `field_ids`; new facts | Done (migration 5 adds the finding columns) | [engine/db.py](../engine/db.py) |
| Configuration: `area`, `bound` and `order` comparisons; tolerances `turnover_window_min_months`, `itr_due_days`, `profit_variance`, `comparatives_variance`, `balance_variance`; `own_bank_names`; GST rows (a), (b) and (c); `itr_lines` | Done (provisional values) | [config/](../config/) |
| Screen: outcome tiles, area cards that filter, findings grouped by area, sources table with the differing value highlighted, line-by-line detail, "not on file" chips, review in place, side-by-side viewer (F-16.2), identity, people, board-resolution and tax panels | Done | [src/components/case/CrossVerification.tsx](../src/components/case/CrossVerification.tsx), [src/components/docviewer/DocViewer.tsx](../src/components/docviewer/DocViewer.tsx) |
| CAM cross-verification section grouped by area | Done | [engine/cam.py](../engine/cam.py) |
| Tests | Done | [tests/test_crosschecks_areas.py](../tests/test_crosschecks_areas.py), [tests/test_crosschecks.py](../tests/test_crosschecks.py), [tests/test_crosschecks_facilities.py](../tests/test_crosschecks_facilities.py), [services/ingestion/tests/test_facility_types.py](../services/ingestion/tests/test_facility_types.py), [e2e/cross-verification.spec.ts](../e2e/cross-verification.spec.ts) |

Differences from the plan:

- **The stage starts on a comparison.** The Cross-verification stage starts once a check has compared two sources. A check waiting only for a document counts towards the total but does not start the stage ([engine/progress.py](../engine/progress.py)).
- **ITR due date.** TX-01 expects a return only once it is due (`itr_due_days`, 214 days after the year end, proposed). A later year shows as "not yet due".
- **Fixture data corrected.** The complete fixture case's FY 2024-25 statements now agree with the FY 2025-26 comparative column, and its bank statement carries monthly supplier payments. Both were real disagreements that FS-01 and FS-02 found in the synthetic data ([tests/fixtures/build_fixtures.py](../tests/fixtures/build_fixtures.py)).
- **The nil-facilities declaration is now a document type.** The reference sample `Southgate_Nil_Facilities_Declaration.pdf` was outside the closed list; it now classifies as a declaration of existing facilities that declares none, and OB-02 holds the statements' instalments against it.
- **Recorded classification answers.** Adding types changes the classification prompt, so the four recorded classification answers in `services/ingestion/tests/fixtures/recordings/reference.sqlite3` (for the reference samples outside the list) no longer replay. No automated test uses them; re-record with `scripts/record_reference.py` and the live key. Extraction recordings are unaffected.
- **FS-02 and cash-credit accounts.** FS-02 sums statement balances as printed. A cash-credit or overdraft statement printing its debit balance as a positive number would overstate the total. The rule is mild, non-blocking and asks the customer nothing; review it on RBL's first cash-credit statement.

## Appendix A: what each document contributes

| Document | Fields used | Feeds |
|---|---|---|
| Certificate of Incorporation | `company_name`, `cin`, `date_of_incorporation`, `company_type`, `registered_address` | ID-03, ID-05, ID-07, ID-09, BR-04 |
| Memorandum and Articles | `company_name`, `cin`, `directors[].name`, `directors[].din` | ID-03, ID-05, ID-06, ID-08 (or ID-04, per D-3), BR-02 |
| Company PAN | `company_name`, `pan` | ID-01, ID-03 |
| Director KYC | `person_name`, `din`, `pan`, `designation` | ID-04, ID-06, ID-08, BR-02 (party attribution, F-10, already uses it) |
| Board Resolution | `company_name`, `borrowing_limit`, `lender_name`, `authorized_signatories`, `authorized_persons`, `resolution_date` | ID-03, BR-01 to BR-04 |
| Audited Financial Statements | `company_name`, `financial_year`; P&L and balance-sheet lines, both columns (revenue, PBT, PAT, net worth, borrowings, finance costs, cash and bank) | ID-03, TO-01, TO-03, TO-04, TX-01 to TX-03, FS-01, FS-02, OB-03 |
| Income Tax Return | `pan`, `taxpayer_name`, `assessment_year`, `total_income`, `income_computation` rows | ID-01, ID-03, TX-01 to TX-03 |
| GSTR-3B | `gstin`, `legal_name`, `tax_period`, `outward_supplies` (3.1), `tax_payment` | ID-01 (derived PAN), ID-02, ID-03, TO-01, TO-02, TO-05, BA-03 |
| Bank Statement | `account_holder_name`, `account_number`, `bank_name`, statement period, `transactions` (date, description, debit, credit, balance) | ID-03, TO-02, TO-03, TO-05, BA-01 to BA-03, FS-02, OB-02, OB-03 |
| Case record (sourcing message) | PAN, GSTIN, CIN, promoters, declared turnover, existing banking, amount, constitution | ID-01, ID-02, ID-04, ID-05, ID-07, TO-04, BR-01, BA-01, OB-02 |

## Appendix B: rule cards

The configuration entry each new rule needs. The wording is a proposal; on-screen text is reviewed against FRD principle 11.

| ID | Explanation template | Query to the customer | PD question |
|---|---|---|---|
| ID-05 | "The CIN differs between documents: {items}." | "Please confirm the company's CIN; the documents show {items}." | "{explanation} Which CIN is correct?" |
| ID-06 | "{person}: the DIN on the KYC ({right}) differs from the memorandum ({left})." | "Please confirm {person}'s DIN." | — |
| ID-07 | "The CIN shows {left}, but the certificate of incorporation shows {right}." | — | "{explanation} Has the company's class or status changed?" |
| ID-08 | "{items} named in the memorandum but no KYC was received." | "Please confirm whether {items} is still a director, and provide KYC if so." | "Is {items} still on the board?" |
| BR-01 | "The board resolution authorises borrowing up to {left}; the amount requested is {right}." | "Please provide a board resolution covering borrowing of {right}." | — |
| BR-02 | "{items} is authorised to sign but is not among the directors on file." | "Please confirm {items}'s position and provide KYC." | — |
| BR-03 | "The board resolution names {left} as the lender." | "Please provide a board resolution in favour of this bank." | — |
| BR-04 | "The resolution is dated {left}, outside the company's life on file ({right})." | "Please provide a correctly dated board resolution." | — |
| TO-05 | "{period}: GST outward supplies {left} against business credits {right}, a variance of {variance} (tolerance {tolerance})." | "Please explain the difference between GST outward supplies and bank credits for {period}." | "{explanation} Are sales received in accounts not shown to us, or in cash?" |
| TX-01 | "No income tax return on file for {items}." | "Please provide the income tax return for {items}." | — |
| TX-02 | "{period}: profit before tax {left} in the statements against {right} in the return, a variance of {variance}." | "Please explain the difference between book profit and the profit in the return for {period}." | "{explanation} What adjustments explain it?" |
| FS-01 | "The {period} comparatives differ from the previous year's audited statements: {items}." | "Please confirm whether the {period} accounts were restated, and why." | "{explanation} Were the accounts restated?" |
| FS-02 | "Bank balances on {period} total {left}, more than the audited cash and bank balance of {right}." | — | "{explanation} Which accounts make up the audited balance?" |
| BA-01 | "No statement for the declared account {items}." | "Please provide 12 months' statements for {items}." | — |
| BA-02 | "Account {items} appears in transfers but has no statement." | "Please provide 12 months' statements for {items}, or confirm whose account it is." | "Whose account is {items}, and what is it used for?" |
| OB-02 | "Monthly instalments of {left} to {items} are not among the lenders declared." | "Please give details of the facility with {items}: amount, outstanding and EMI." | "{explanation} What is this facility, and why was it not declared?" |
| OB-03 | "The audited statements show borrowings of {left}, but no instalments appear in the bank statements." (or the reverse) | "Please confirm how the borrowings are repaid, and from which account." | "{explanation} Where are these loans serviced?" |
