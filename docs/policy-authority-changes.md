# Policy norms and approving authority: change register

| | |
|---|---|
| Date | 9 October 2026, updated 12 October 2026 (section 10) |
| Branch | `cross-validation-abhishek` (not yet committed) |
| Test plan rows | TC-24 Policy norms and deviations (FRD TC-26, F-20); TC-25 Approving authority (FRD TC-27, F-21) |
| Also built | F-25 for the deviations and approving-authority areas: RBL's reference record, the comparison and adjudication |
| Decision | FRD C.4-9: the approving authority is built on a provisional matrix until RBL supplies its own |
| Logic | [policy-norms-logic.md](policy-norms-logic.md): every norm, its figures and the approving authority, end to end |

---

## 1. Where the two test rows stand

| Row | Condition | Expected | Pass rule | Status |
|---|---|---|---|---|
| TC-24 | RBL's key Business Banking policy norms | Each norm assessed; deviations listed with the norm, the actual value and the source | Agrees with RBL's deviation record | **Ready to run.** Every configured norm is assessed with its source figures. The comparison with RBL's deviation record runs as soon as the record is imported and confirmed. Agreement is indicative while the norms themselves are interim proposals |
| TC-25 | RBL's approval matrix, if provided, and the case parameters | Authority required identified and compared with the recorded approval | Agrees with the matrix; included only where RBL provides the matrix | **Demonstrable, not scored.** The required authority and the rule that set it are shown, and compared with the recorded approval. The matrix is a delivery-team proposal, so TC-25 is reported as "not scored" until RBL's matrix is published |

What RBL still has to supply: its policy norms, its approval and delegation matrix, and the case set with each case's credit record (FRD C.3).

## 2. What users see

| Where | What changed |
|---|---|
| Policy tab, top | A notice that the norms are interim proposals until RBL's norms are supplied |
| Policy tab, each norm | Why a norm could not be assessed, in words: a missing figure, a zero denominator, a figure still waiting for review. A ratio over a zero or negative net worth is a deviation with no meaningful value ("unbounded"), never a pass. Negative amounts keep their sign (INR -4.00 cr). Figures without a document page say where they come from: the case header, the open blocking checklist items (a link to Completeness), the bank statements, or "no term loan requested". The details show the formula evaluated, the ratio's definition and its note |
| Policy tab, security cover | A line saying no security-cover norm can be evaluated until a valuation report is among the document types |
| Policy tab, new panel **Approving authority** | The authority required and its level, the amount and products it rests on, and each rule applied (amount band per product, then each deviation category), with the deciding rule marked. When norms could not be assessed, it says whether they could raise the authority. Marked "Provisional matrix". If no matrix is published, it says so and the norms still show |
| Comparison tab (Credit Manager only) | Replaces the "not built yet" placeholder: RBL's record beside CreditIQ's deviations and authority, each item marked Agree, Differ, New or Missed, with notes and the evidence; confirm the record; decide Valid or Not valid with a reason; area scores |
| Outputs, draft CAM | The summary lists norms that could not be assessed ("Norms not assessed"), and the policy section says how many norms passed, deviated or could not be assessed, and that the norms are interim |
| Outputs, PD note | Each question links to the tab the engine names for it (a bureau or tax cross-check no longer opens the Policy tab) |
| New appraisal | A field for the proposed monthly instalment on the term loan, used by the debt-service norm |

The analyst never sees RBL's recorded approval: it appears on the Comparison tab only.

## 3. Policy norms (F-20): what was fixed

| Norm or area | Before | After |
|---|---|---|
| Leverage over negative or zero net worth (FR-02 TOL/TNW, FR-05 debt/equity) | Passed at a negative ratio | A deviation, shown "unbounded", with the reason |
| A zero denominator (for example interest coverage with no finance costs) | "Finance costs is zero not on file" | "Cannot evaluate: Finance costs is zero", and its own PD question |
| Debt service (FR-03) | Ignored the proposed term loan; counted interest twice; ignored declared EMIs; assumed zero instalments | Existing instalments (declared, sanctioned and inferred from bank statements) plus the proposed term loan's instalment. Each facility is counted once: a renewed sanction letter or a second copy of the declaration is not counted again, and lenders are matched on their full name ("Indian Bank" and "Indian Overseas Bank" are two lenders; a narration such as "TIDEWATER FIN" is the declared lender only when the instalment agrees). Zero only when enough months of statements show none, and then cited. An instalment the RM typed cites the case, not the sourcing message |
| Total request against turnover (EL-05) | Applied above the turnover-method limit | Applies under the turnover method only; its threshold is checked against the working-capital percentages |
| Business vintage (EL-01) | Rounded up before the comparison (2.95 years passed 3) | Completed months; display truncates; applies to companies only |
| Bureau rank (EL-02) | Not assessed | Assessed from the latest commercial bureau report; a missing report is not asked of the promoter |
| Figures waiting for review | Used as if confirmed | The norm waits: "Cannot evaluate until … is reviewed" |
| Sources | The amount requested and open checklist items had none | Every input has a page or a named basis |
| Configuration checks | A malformed norm could publish | The publish check reports unsupported expressions (including true/false constants), missing sources, impossible settings and a wrong turnover threshold. A norm the evaluator cannot read is "cannot evaluate", never an error page |
| Wording of a deviation | "20.0% against at most 20%" for a value just over the norm | Decimals are added until the value reads differently from the norm: "20.04% against at most 20%" |
| Spread ratios | (unchanged module) | A ratio with a zero denominator is blank in the spread and the memo's table, as the norm says "cannot evaluate", never 0.00 |

Each assessment records the configuration version it used.

## 4. Approving authority (F-21)

**The matrix** (`config/approval_matrix.yaml`, every row provisional):

| | Working capital | Term loan | Non-fund based |
|---|---|---|---|
| Credit Officer (level 1) | up to INR 2 cr | up to INR 1 cr | up to INR 3 cr |
| Regional Credit Head (2) | up to INR 5 cr | up to INR 3 cr | up to INR 7.5 cr |
| Zonal Credit Committee (3) | up to INR 15 cr | up to INR 10 cr | up to INR 20 cr |
| Head Office Credit Committee (4) | up to INR 50 cr | up to INR 35 cr | up to INR 60 cr |
| Management Credit Committee (5) | above | above | above |

Deviation rules: each category needs one level above the amount authority; eligibility at least the Regional Credit Head; security at least the Zonal Credit Committee. Rules never add up. Authorities are roles and committees, never people.

**How the authority is set:** for each product requested, the band the amount falls in (upper bounds inclusive); the highest of those is the base. Each category with a deviation then asks for its levels above the base, at least its floor, capped at the highest authority. The case needs the highest any one step asks for; the first such step "decides". If some norms could not be assessed, the authority is a lower bound, and the panel says what it would be if they were deviations.

Worked examples (all tested): cash credit INR 1.5 cr with no deviation needs the Credit Officer; exactly INR 2 cr still the Credit Officer, one rupee more the Regional Credit Head; cash credit and term loan of INR 6.5 cr with a financial deviation needs the Head Office Credit Committee; cash credit INR 60 cr with a deviation stays at the Management Credit Committee, the deviation step marked "capped".

RBL's own matrix replaces the file as a whole: `creditiq config publish --private-config workflow/private/config` publishes it from a git-ignored directory, so it never enters the repository.

## 5. RBL's record and the comparison (F-25, two areas)

| Step | How |
|---|---|
| Template | `creditiq reference template --out baseline.xlsx`: sheets Case, Deviations, Approving authority, Lists (norm ids, categories, authorities from the published version), and header-only sheets for the five areas not compared yet |
| Import | `creditiq reference import <case id> <file.xlsx or .json> --author <user id>`. All or nothing: any error (unknown norm, category or authority; a duplicate norm row; no "Where in the record"; two approval rows; the wrong case; "none" with rows; a bad date) refuses the import and names the sheet, row and column. A different borrower name or template version only warns |
| Confirm | The Credit Manager confirms the record on the Comparison tab. The person who imported it cannot |
| Compare | Deviations by norm: Agree (values equal at the record's precision; crore and lakh understood), Differ, New (CreditIQ only), Missed (record only, with why: passed, could not be assessed, not applicable, or no norm covers it). The authority: Agree, or Differ (lower, higher, not in the matrix), with the rule applied and the authority the matrix gives on RBL's own deviations |
| Adjudicate | Valid or Not valid with a reason (at least 3 characters), on Differ and New items of a confirmed record. A decision on an item that has since changed is shown stale and not counted |
| Scores | Deviations found in the record, and CreditIQ deviations upheld, for the scorecard (F-26). The authority is scored only on an active matrix |

Decisions never change the output: no processing module can read the record or the decisions (import-linter contract 2), and deciding refreshes only the comparison. Every import, confirmation and decision is in the audit trail. Deleting a case deletes its record, decisions and stored workbook.

The workbook is read with the standard library only, refusing DTDs, oversized or over-compressed files and sheets over 2,000 rows.

## 6. Engine, configuration and data

| Area | Change |
|---|---|
| New modules | `engine/approval.py`, `engine/reference.py`, `engine/comparison.py`, `engine/xlsx.py` |
| Changed | `engine/policy.py` (rewritten), `facts.py`, `cam.py`, `pd_note.py`, `proposal.py`, `crosschecks.py`, `configstore/*`, `cli.py`, `api.py`, `db.py` |
| Configuration | New section `approval_matrix`; `policy.yaml` norm changes (EL-01, EL-02 restored, EL-05, FR-02, FR-03, FR-05, new PD questions); `--private-config` for RBL's own files |
| Database | Migration 6: `reference_records`, `reference_items`, `comparison_adjudications` |
| Endpoints | `GET /api/cases/{id}/approving-authority`, `GET /api/config/approval-matrix`, `GET /api/cases/{id}/comparison`, `POST /api/cases/{id}/reference/confirm`, `PUT /api/cases/{id}/comparison/{area}/{key}/adjudication` |
| Contracts | New `ApprovingAuthority`, `CaseComparison` and related models; `NormInput` and `NormResult` gain the basis, review flag, reason, wording, definition and source; `PdQuestion.target`; `CaseFacts.proposed_emi` |
| Permissions | None new: the comparison uses `comparison.adjudicate` (Credit Manager) |

## 7. Independent review

Before hand-over, five reviewers (policy engine, approving authority, reference record and comparison, screens, tests) went through the work independently, each finding checked by a second reviewer trying to refute it. 27 distinct defects were confirmed and fixed, each with a test; a second round re-checked every fix. The main ones:

| Area | Defect | Fixed by |
|---|---|---|
| FR-03 | Lenders sharing a first word merged, so a second lender's instalments were dropped; a renewed sanction letter counted twice | Matching on the full name; each facility once (section 3) |
| F-20 wording | A deviation just over an integer norm read the same as the norm | Section 3 |
| Spread | Zero denominators showed 0.00 after the norm change | Section 3 |
| Audit trail | The analyst could read RBL's record and the reviewer's decisions in the activity details | The details of record and comparison entries are shown to the reviewer only; others see that the import or decision happened |
| Workbook reader | A small hostile file could exhaust memory (far-off columns, a sheet repeated) or crash the import (bad row numbers, corrupt or encrypted members); a UTF-16 part slipped past the DTD refusal | Column, sheet and order limits; every unreadable part is a refusal naming it; DTDs refused in any encoding |
| Import | Two JSON rows with the same number crashed and left the file behind; JSON dates were not checked; some problems named the wrong row | Refused with the row; nothing stored on any failure; dates checked on both paths; rows as parsed |
| Comparison | "33.9%" typed into the workbook read as 0.339; "Rs 0.40 Crs" read as rupees; a rounding tie and "CMR-7" read as differences; a matrix key renamed later read as "lower" | Percent formats read; the template's free-text columns are Text; crore and lakh abbreviations; half-unit tolerance; codes are not minus signs; unknown keys are "not in the matrix" |
| Approval | A matrix whose levels had gaps escalated by position | Levels must be consecutive from 1 |
| Screens | The Policy tab scrolled sideways at phone width for a negative net worth; the comparison header and filter counts disagreed; the authority score used deviation wording | "Unbounded" with the reason below; header labelled "Deviations"; own wording |
| Tests | Several checks could not fail (the analyst-blind check, the refresh check, the source of each TC-24 deviation, the record-side authority) | Rewritten to fail on the regression they name |

## 8. Tests

| Suite | Result |
|---|---|
| Engine (pytest) | 599 passed, 2 skipped; one Windows-only failure (folder permissions) (12 October 2026) |
| Document-processing service | 141 passed |
| Screens (Playwright, port 5391) | 118 of 119 passed; one Windows-only failure (clipboard line endings) (12 October 2026) |
| Type check, lint, build, import contracts | Pass (12 October 2026) |

New engine tests: `test_approval.py` (26), `test_comparison.py` (20), `test_reference.py` (23), `test_xlsx.py` (9), `test_e2e_fixtures.py` (3); `test_policy.py` rewritten (41). New screen tests: `tc26-tc27-policy-authority.spec.ts`, `tc30-comparison.spec.ts`.

## 9. Deferred

Listed in [backlog.md](backlog.md) under Engine: security-cover norms, business vintage for firms, TNW and TOL composition, the working-capital cycle on cost of sales, per-facility amounts, an MPBF norm above INR 5 cr, RBL's DSCR definition, disagreeing copies of a year, the other five comparison areas, and the F-26 scorecard.

## 10. Changes on 12 October 2026

Policy development resumed, concentrating on TC-24 and TC-25.

### 10.1 The Policy tab as a dashboard

| Part | What it shows |
|---|---|
| Header | "Appraisal <case> · Policy checks", the title "Policy norms and approving authority", a summary line (deviations, norms that cannot be evaluated, passed, not applicable, the financial year, provisional norms) and the interim-norms notice |
| Overview | One card per family of norms (Eligibility, Financial ratios, Documentation, Security cover): its deviations large, its other counts, and up to three key norms with actual against required ("90 days · at most 75 days", the deviating value in red; for a norm that cannot be evaluated, what is missing). An **Approving authority** card: the authority and level, "at least" with whether unassessed norms could raise it, the amount authority and the deviation steps, "Provisional matrix" |
| Details | One section per family with its norms (required and actual, the figures with their pages, why a norm could not be assessed, how it was decided), then the authority's steps |

The engine builds the overview (`PolicyAssessment.counts` and `.groups`: each family's counts, status and the norms to show first); the screen counts nothing. Screen files: `src/components/case/policy/` (new), `src/domain/policy.ts` (new); `PolicyNorms.tsx` removed.

### 10.2 Fixes

Found by testing TC-24 and TC-25 end to end against the test applications and with probes.

| Area | Before | After |
|---|---|---|
| Unit wording | "1 years", "1 days", "-0.0%" | "1 year", "1 day", never "-0" |
| A deviation just over its norm | 75.0000001 days read "75.000000 days", the same as the norm | Decimals are added up to the precision the outcome is decided at |
| A recorded loss in RBL's record | "(14.00) cr", "(-) 40 lakh", "Net loss of Rs 40 lakh" and the − sign read as positive, so an agreeing loss showed Differ | Read as negative for amounts; brackets that are not a negative amount (a rank, a profit label) stay positive |
| The record's JSON form | Refused "not_in_matrix", which the workbook accepts | Accepted, as the workbook does |
| The workbook reader | Phonetic guides were added to cell text; ISO date cells were refused | Only the text is read; ISO dates are read |
| Adjudication | A reason of three spaces was accepted by the server | The reason is trimmed before it is checked (422 under three characters) and kept trimmed |

### 10.3 Sample RBL records

So that TC-24 and TC-25 can be shown end to end, a fictional RBL record is stored for two test applications by `workflow/seed_policy_reference.py` (git-ignored; `create`, `report`, `delete`), imported through the same validation as `creditiq reference import` and confirmed by the Credit Manager:

| Application | Deviations | Approving authority |
|---|---|---|
| Kestrel (BBG-2026-000004) | FR-06 Agree; DOC-01 Differ (3 against 6 items); FR-03 Missed (a DSCR CreditIQ could not assess) | Agree: Head Office Credit Committee |
| Marigold (BBG-2026-000006) | EL-05, FR-06, DOC-02 Agree; DOC-01 New | Differ: RBL's record says Regional Credit Head, the matrix requires Zonal Credit Committee |

They are test data, removed with `delete` (and with the test applications) before merging.

### 10.4 Tests

New engine tests: unit wording and the one-year case through the API, CAM and PD note; deviations just over a norm; negative amounts in the record however written; `not_in_matrix` in JSON; phonetic guides and ISO dates in workbooks; every band of every product inclusive; the families' counts, statuses and highlights; reasons trimmed. The Policy tab's screen tests (`e2e/tc26-tc27-policy-authority.spec.ts`) were rewritten for the dashboard.

### 10.5 Noted, not changed

- FR-03 is not applicable for a working-capital case with nothing on file about existing loans (by design; a test pins it).
- DOC-02 with no audited statements has no source to show (needs a new input basis in the contract).
- Area scores are computed for an unconfirmed record; the F-26 scorecard must count confirmed records only.
- Instalments inferred from bank debits never wait for review (transactions carry no review flag).
- The recorded value is read from its first number ("FY26: 92 days" reads 26); the delivery team fills that column.
