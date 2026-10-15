# CreditIQ (RBL BBG PoC) — end-to-end test report

**Date of run:** 13 October 2026
**Application:** `creditiq-poc` — React/TanStack front end, FastAPI engine, SQLite
**Front end under test:** `http://localhost:4174` (`VITE_API_BASE_URL=http://localhost:8011`)
**Engine under test:** `http://localhost:8011` (`CREDITIQ_INGEST=stub`, data root `workflow/data-e2e`)
**Frozen case date (`as_of`):** `2026-09-29` for every case the suite builds

---

## Mandatory caveat on what this proves

**Stub ingest replays recorded results keyed by file hash.** This report verifies the
plumbing around extraction — that documents are registered, that fields, checks, norms and
outputs reach the screens, and that the screens read correctly for each role. **It does not
verify extraction accuracy, OCR, or classification quality.** No model ran during this test;
every document's reading came from `tests/fixtures/ingest/`.

---

## Summary

| Suite | What it drives | Tests | Passed | Failed |
| --- | --- | --- | --- | --- |
| `test:e2e:integration` | The real engine, real pipeline, real SQLite | **82** | **82** | **0** |
| `test:e2e` | The screens with the engine answered in the browser | **120** | **120** | **0** |
| **Total** | | **202** | **202** | **0** |

Run time: 2 min 55 s (integration, one worker) and 1 min 25 s (screens).
After the integration run the data root held **0 cases** — every spec cleaned up after itself.

Eleven defects were found and fixed while building this suite. All eleven were in the test
harness and the specs, not in the application; they are listed in
[Failures found during this exercise](#failures-found-during-this-exercise), because the
harness had never been executed against the UI before and several of its helpers did not work.

---

## Results by page and by function

Every row below was exercised against the real engine unless marked *(screens)*, which means
it is covered only by the browser-answered suite.

### Sign-in — `/sign-in`

| Function | Result |
| --- | --- |
| The form asks for an email and a password | Passed |
| An unauthenticated visit to the workbench lands on sign-in | Passed |
| A wrong password is refused, with an error, and no session opens | Passed |
| An unknown email is refused | Passed |
| Relationship Manager signs in, is named with their role, signs out | Passed |
| Credit Analyst signs in, is named with their role, signs out | Passed |
| Credit Manager signs in, is named with their role, signs out | Passed |
| The RM's menu holds neither Governance nor Administration | Passed |
| The analyst's menu holds Governance and Administration, not the Scorecard | Passed |
| The manager's menu holds the Scorecard and offers no way to create | Passed |
| Sign in at 375 px *(screens)* | Passed |

### Workbench — `/`

| Function | Result |
| --- | --- |
| A new appraisal appears in the list and the in-flight counter rises by one | Passed |
| The three counters (in flight, review, ready for credit) are shown | Passed |
| The stage filter and the review filter are shown | Passed |
| The owner filter is offered only to a role that sees every appraisal | Passed |
| An RM sees only their own appraisals | Passed |
| An RM cannot open another's appraisal by its address | Passed |
| A manager sees every appraisal but is offered no way to create one | Passed |
| Nothing is counted ready for credit before a document is in | Passed |
| The "needs attention" panel *(screens)* | Passed |

### New appraisal — `/appraisals/new`

| Function | Result |
| --- | --- |
| Nothing can be read before a channel and a message are given | Passed |
| The engine proposes each field with a status, span and candidates | Passed |
| An ambiguous borrower comes back *Unclear* with its candidates and a note | Passed |
| PAN, amount and facilities are read with certainty from the message | Passed |
| A field the message did not settle blocks creation until confirmed | Passed |
| A minimum field still empty blocks creation and says what is needed | Passed |
| Choosing a candidate fills the field and settles it | Passed |
| Reading the message stores nothing | Passed |
| A second application for the same borrower is offered the existing one | Passed |
| Creating anyway is refused until a reason is given | Passed |
| A duplicate found at creation (409) is offered the same way *(screens)* | Passed |
| Discard clears the proposal and empties the screen | Passed |
| Creation lands on Files, where the documents are added next | Passed |
| A manager cannot reach the screen at all | Passed |
| Create a case and upload at 375 px *(screens)* | Passed |

### Case Overview — `/appraisals/$caseId`

| Function | Result |
| --- | --- |
| The pipeline settles with every one of the six stages reported | Passed |
| The header carries the case ID and the borrower | Passed |
| The stage bar and the current stage are shown | Passed |
| Stages that found gaps report "needs attention" | Passed |
| A complete file shows "ready for credit"; a short one shows what blocks it | Passed |
| The analyst's case menu holds seven tabs, Comparison excepted | Passed |
| The manager's case menu holds all eight tabs | Passed |
| The RM's case menu holds three tabs | Passed |
| A tab outside the role shows a designed state, not a crash | Passed |
| A case the role may not see is absent, not forbidden | Passed |
| Delete an appraisal after typing its ID and a reason | Passed |
| Overview lists what is still needed and what waits for a decision *(screens)* | Passed |
| Processing finishing refreshes the rest of the appraisal *(screens)* | Passed |

### Files — `/appraisals/$caseId/documents`

| Function | Result |
| --- | --- |
| Every uploaded file is registered (14 uploads + the sourcing message = 15 files) | Passed |
| The files are read into 27 documents | Passed |
| The short file set is registered and read into 14 documents | Passed |
| A document row opens its own checks and its type | Passed |
| A manager is offered no upload zone | Passed |
| A ZIP shows as a tree with its folders and members *(screens)* | Passed |
| Duplicate, ignored and rejected files each end in a visible state *(screens)* | Passed |
| A label mismatch is reported on the row and in the checks *(screens)* | Passed |
| An unclassified document offers its top candidates *(screens)* | Passed |
| A type is assigned from the row, and from the review queue *(screens)* | Passed |
| An RM sees the flag but not the decision *(screens)* | Passed |

> The recorded fixture set is clean — all 27 documents came back grade A and accepted, with no
> label mismatch and nothing unidentified. The duplicate, rejected, mismatched and unclassified
> states therefore have **no real-engine coverage**; they are proven only against the screens.

### Extracted data — `/appraisals/$caseId/extraction`

| Function | Result |
| --- | --- |
| The field tables are drawn from the documents (583 fields on the complete file) | Passed |
| The three people the documents name are listed as parties | Passed |
| A value opens the page it was read from, in the evidence viewer | Passed |
| Escape closes the viewer | Passed |
| The data is grouped by kind of document *(screens)* | Passed |
| Every field carries a confidence and a page link *(screens)* | Passed |
| A value in review is confirmed from its row *(screens)* | Passed |
| A correction is made beside the source page, with a reason *(screens)* | Passed |

### Completeness — `/appraisals/$caseId/completeness`

| Function | Result |
| --- | --- |
| A complete file shows all ten requirements satisfied | Passed |
| A complete file is 100 % ready and marked ready for credit | Passed |
| A short file shows 4 missing, 4 insufficient, 2 satisfied | Passed |
| A short file fails the gate and names its blocking gaps | Passed |
| An insufficient requirement states exactly what is short about it | Passed |
| A missing requirement says it was never received | Passed |
| The blocking filter leaves only the blocking gaps (8 of 10) | Passed |
| The satisfied filter leaves only what is satisfied | Passed |
| A requirement opens to show why it is asked for and what satisfies it | Passed |
| The linked documents behind a requirement are shown | Passed |
| The query list is on the same tab | Passed |
| A complete file's ten requests are all shown resolved | Passed |
| A short file's query list holds 15 requests, 6 resolved and 9 open | Passed |
| Sections in published order with their weights *(screens)* | Passed |
| Provisional while the constitution is unknown *(screens)* | Passed |
| Copy the query list as email and as plain text *(screens)* | Passed |
| A blocking cross-check finding shows on the summary *(screens)* | Passed |

### Cross-checks — `/appraisals/$caseId/cross-verification`

| Function | Result |
| --- | --- |
| All four areas (identity, turnover, accounts, obligations) are reported | Passed |
| A complete file still fails one check: TO-04, declared against evidenced turnover | Passed |
| That finding is mild and raises no blocking banner | Passed |
| The other three areas show nothing in discrepancy | Passed |
| A short file puts three findings on the board: ID-07, TO-04, OB-03 | Passed |
| Checks that could not run are reported, not dropped | Passed |
| The board opens the engine's top finding as it loads | Passed |
| A finding is accepted only once a comment is given | Passed |
| The decision survives a reload and the card is marked adjudicated | Passed |
| A finding is dismissed with a comment | Passed |
| The failed cross-check reaches the review queue | Passed |
| Escalation to the Credit Manager, and read-only until decided *(screens)* | Passed |
| Trace to source, evidence rows, side-by-side pages *(screens)* | Passed |
| The engine's refusal shows on the card *(screens)* | Passed |
| Area cards, ranking, key figures, layout at three widths *(screens)* | Passed |

### Policy — `/appraisals/$caseId/policy`

| Function | Result |
| --- | --- |
| All thirteen norms are listed with their required and actual values | Passed |
| A complete file: 11 pass, 1 deviation (FR-06 working-capital cycle), 1 unevaluable (FR-03 DSCR) | Passed |
| A short file: 8 pass, 3 deviations, 2 unevaluable | Passed |
| A norm that cannot be evaluated says so rather than being left out | Passed |
| A norm's figure opens the page it was read from | Passed |
| The approving authority is worked out from the ask | Passed |
| It is shown as a lower bound while a norm is unevaluated | Passed |
| The authority may rise once the unassessed norms are known *(screens)* | Passed |
| Without a published matrix the norms still show *(screens)* | Passed |
| An authority that cannot be determined says why *(screens)* | Passed |

### Outputs — `/appraisals/$caseId/outputs`

| Function | Result |
| --- | --- |
| The spread holds all 28 rows | Passed |
| Two audited years on file give two columns of figures | Passed |
| One audited year gives one, and the spread says it is interim | Passed |
| A figure is traceable to the page it was read from | Passed |
| The working-capital verdict is shown | Passed |
| The draft CAM has all ten sections | Passed |
| The CAM cites its figures (40 citations on the complete file) | Passed |
| The CAM summary lists the deviation and the norm not assessed | Passed |
| The PD note asks 7 questions on a complete file, 20 on a short one | Passed |
| Each PD question links to the tab that raised it | Passed |
| Switching between spread, CAM and PD views | Passed |

### Comparison — `/appraisals/$caseId/comparison`

| Function | Result |
| --- | --- |
| The tab is absent from the analyst's case menu | Passed |
| It is closed to the analyst even by its own address | Passed |
| It is present for the Credit Manager | Passed |
| With no record imported, the comparison waits for it *(screens)* | Passed |
| The reviewer confirms an imported record before adjudicating *(screens)* | Passed |
| The person who imported the record cannot confirm it *(screens)* | Passed |
| Deviations and the authority compared with RBL's record *(screens)* | Passed |
| A new deviation is adjudicated with a reason *(screens)* | Passed |
| A decision on an item that changed since is shown stale *(screens)* | Passed |

> The adjudication flow has **no real-engine coverage**: it needs an imported RBL record, and
> no endpoint to import one was exercised. Against the real engine only the access rules were
> proven.

### Review queue — `/review`

| Function | Result |
| --- | --- |
| The queue's kind filters (type, field, finding, …) are shown | Passed |
| A complete file's one failed cross-check is queued, open | Passed |
| A short file's three findings are queued, each decidable | Passed |
| The queue is closed to an RM | Passed |
| A type is assigned from the decision dialog *(screens)* | Passed |
| A decision needs its choice and reason *(screens)* | Passed |

### Scorecard — `/scorecard`

| Function | Result |
| --- | --- |
| Shows a designed placeholder (feature F-26), with no console error | Passed |
| Absent from the analyst's menu | Passed |

### Audit trail — `/audit`

| Function | Result |
| --- | --- |
| Activity is listed, and never as a raw event key | Passed |
| The person who acted is named | Passed |
| The actor and action filters are built from what is on the trail | Passed |
| Closed to an RM | Passed |
| Escalations and query additions read in words *(screens)* | Passed |

### Administration — `/admin` and its four screens

| Function | Result |
| --- | --- |
| Administration names the published configuration version | Passed |
| Policy norms lists all thirteen by family | Passed |
| The checklist configuration lists its gates and items | Passed |
| The document types are the closed published list | Passed |
| The three people and their roles are listed | Passed |
| Every Administration screen is reachable from the menu | Passed |
| Open to the Credit Manager as well as the analyst | Passed |
| Closed to an RM | Passed |
| The publish history, with section names in words *(screens)* | Passed |

### Help — `/help`

| Function | Result |
| --- | --- |
| Each of the six steps is explained | Passed |
| Open to every role | Passed |

### Addresses and error states

| Function | Result |
| --- | --- |
| All thirteen earlier addresses redirect to their place in the workspace | Passed |
| `/appraisals/new` is not swallowed by the case routes | Passed |
| An address that is not a screen says so without crashing | Passed |
| A 501 from an endpoint reads as "not available yet" *(screens)* | Passed |
| A 403 reads as "not part of your role" *(screens)* | Passed |

### Invariants

| Invariant | Result | Evidence |
| --- | --- | --- |
| Age rules read the case's frozen `as_of`, never the wall clock | **Passed** | The same documents at `as_of` 2026-09-29 give 10/10 satisfied and ready for credit; at `as_of` 2027-09-29 they give 5 satisfied, 4 insufficient, 1 missing and not ready. |
| An age deficiency is measured from the case's date | **Passed** | The board-resolution deficiency reads "permitted age 365 days from 29 Sep 2027". Today's date appears nowhere in it. |
| Nothing downstream of the pipeline moves a case's `as_of` | **Passed** | Read back from the database after the full pipeline and after decisions. |
| A review decision never changes the published configuration version | **Passed** | The version on `/admin` is byte-identical before and after a finding is dismissed. |
| A case-scoped screen the role may not see answers 404, not 403 | **Passed** | An RM opening the analyst's case gets "No application &lt;id&gt;", with no refusal state. |
| A role without a permission on a case it *can* see is refused | **Passed** | The analyst on `/comparison` gets 403 → "Not part of your role". Correct: a permission gap, not a visibility gap. |

---

## Failures found during this exercise

The suite ends green, but it did not start that way. Nine runs were needed. Every defect below
was in the harness or in the specs — **no application defect was found**. They are reported
because the harness had never been run against the UI, and three of its helpers were broken in
ways that silently did nothing.

### Harness defects (fixed)

| # | Defect | Effect | Fix |
| --- | --- | --- | --- |
| 1 | `deleteCaseViaUi` counted the `delete-case` control immediately after `page.goto`, found zero, and returned silently | **No case was ever deleted.** Leaked cases then matched the duplicate-borrower check and left the Create button permanently disabled in later specs — the cause of five cascading failures | Wait for `case-header` and for the control before acting |
| 2 | `deleteCaseViaUi` scoped the confirmation to `getByRole("dialog")` | The dialog is a shadcn `AlertDialog`, so its role is `alertdialog`; the helper timed out once it got that far | Use `getByRole("alertdialog")` |
| 3 | `createCaseViaUi` expected to land on `/appraisals/<id>` after creating | With no attachment the screen goes to `/appraisals/<id>/documents`, so the helper timed out | Accept either landing place; the spec asserts the Files landing explicitly |
| 4 | `createCaseViaUi` had no duplicate-override path | A borrower already on file left Create disabled with nothing to clear it | Give a reason when the warning appears |
| 5 | `stageStatusMap` and `checklistStatuses` read the DOM immediately after `page.goto` | Returned all-nulls and empty arrays before React had drawn | Wait for the stage bar / checklist panel first |
| 6 | Two sign-in specs typed into the form before it was live | The email field was cleared by hydration, the form never submitted, and no error toast appeared — which looked like a missing error message | Wait for the submit button to be enabled first, as the project's own `signIn` helper does |
| 7 | `cases-table` compared with `innerText` against `toHaveText` | `toHaveText` normalises whitespace, so identical content differed | Compare row counts; same fix applied to the configuration-version check |
| 8 | The duplicate spec used an unscoped "Open it" link | Strict-mode violation once more than one duplicate was offered | Scope the link to the case by its `href` |
| 9 | A decision spec toggled the first card open | The board already opens the engine's top finding, so the click **closed** it | Assert the documented default instead of toggling |
| 10 | A decision spec held a `[data-adjudicated="false"]` locator across the save | The card stops matching the moment it is decided, so the locator silently moved to another card | Capture the rule first, then locate by rule |
| 11 | `case-create.spec.ts` expected the borrower to come back *Found* | The engine correctly returns *Unclear*: the message names a second business ("Pvt Ltd or maybe LLP"). The spec had been written against the mock, not the engine | Assert the designed behaviour — unclear, two candidates, a note, and creation blocked. This is a stronger assertion, not a weaker one |

### Application behaviours discovered

Not defects, but each contradicted a reasonable expectation and is now pinned by a test.

1. **A complete file still raises one cross-check finding.** A case created through the screens
   carries the header the RM confirmed, including the turnover declared in the sourcing message.
   TO-04 then compares that declared turnover against what the documents evidence, and it fails
   (mild, non-blocking), producing one review-queue item. A case created straight over the API
   with an empty header does not raise it, because there is nothing to compare. So
   "complete file ⇒ clean board" is false, and the suite asserts the one finding.
2. **A run of digits inside a borrower name defeats the name pass.** `Workbench Metals
   1760328123456 Pvt Ltd` comes back `borrower: not_found`. Harmless for real names, but it
   means a spec cannot rely on the engine reading a uniquified test name; the suite types the
   borrower on the proposal instead.
3. **`xv-recorded-decision` is not in the DOM while its card is collapsed.** The decision does
   persist — the card carries `data-adjudicated="true"` on the board — but the recorded decision
   itself renders only in the open card body.
4. **The engine's `counts` on the cross-check board are narrower than the cards drawn.** The
   board draws a card per finding whose outcome is `fail`; `counts.total` counted 0 where one
   card was drawn. Assert against the cards, or against `fail` outcomes, not `counts`.

---

## Not covered

Stated plainly, so the green result is not read for more than it is worth.

- **Extraction accuracy, OCR and classification quality.** Excluded by design under stub ingest.
- **Document edge cases against the real engine.** The recorded set is clean (27/27 grade A), so
  the blurred ITR, the photographed GST return, the scanned page and the Apr–Mar bank statement
  were uploaded but never produced a degraded state to assert. Duplicate, ignored, rejected,
  label-mismatched and unclassified files are proven only against the screens.
- **Comparison adjudication against the real engine.** It needs an imported RBL record; no
  import was exercised. Only the access rules were proven.
- **Corrections through the evidence viewer against the real engine** (`field-correct` → save).
- **Escalation to the Credit Manager against the real engine.**
- **The query list's copy-as-email and copy-as-text against the real engine.**
- **Phone and tablet widths against the real engine.** Covered at 375 px against the screens.
- **The Scorecard's behaviour.** F-26 is an unbuilt placeholder; only the placeholder is checked.
- **Concurrency.** The integration suite must run with one worker: the specs share one SQLite
  data root and one duplicate-borrower namespace, so parallel workers interfere with each other.

---

## How to reproduce

Both services must already be up, and the engine's CORS allow-list is hard-coded to ports
4173 and 5173, so `CREDITIQ_FRONTEND_ORIGINS` is **mandatory** — without it sign-in fails
silently with no error anywhere.

```bash
cd /home/balaji/projects/j2w/RBL/RBL_POC/creditiq-poc

# Engine: stub ingest, isolated data root, the test front end's origin allowed.
CREDITIQ_DATA_ROOT="$PWD/workflow/data-e2e" CREDITIQ_INGEST=stub \
CREDITIQ_FRONTEND_ORIGINS="http://localhost:4174,http://127.0.0.1:4174" \
  .venv/bin/uvicorn engine.api:app --port 8011 &

# Front end.
source ~/.nvm/nvm.sh && nvm use 22
VITE_API_BASE_URL=http://localhost:8011 npx vite dev --port 4174 --strictPort &

# The screens, with the engine answered in the browser (120 tests).
E2E_PORT=5399 npx playwright test --project=chromium

# The real engine (82 tests). One worker is required.
E2E_PORT=5399 npx playwright test --project=integration --workers=1
```

`E2E_PORT=5399` is needed because port 5173 is held by an unrelated project and Playwright
would otherwise reuse it and test the wrong application.

### The specs

| File | Covers |
| --- | --- |
| `e2e/integration/01-sign-in.spec.ts` | Sign-in, sessions, the menu each role gets |
| `e2e/integration/02-workbench.spec.ts` | The workbench, its counters and filters, what each role sees |
| `e2e/integration/03-case-complete.spec.ts` | Every tab of a complete file (Kestrel, 14 documents) |
| `e2e/integration/04-case-partial.spec.ts` | Every tab of a short file (Heronbay, 6 documents) |
| `e2e/integration/05-access.spec.ts` | Tabs per role, 404 against 403, what each role cannot do |
| `e2e/integration/06-governance.spec.ts` | Review queue, audit trail, scorecard, Help, unknown addresses |
| `e2e/integration/07-admin.spec.ts` | Administration and its four screens |
| `e2e/integration/08-redirects.spec.ts` | The thirteen earlier addresses |
| `e2e/integration/09-invariants.spec.ts` | The frozen `as_of` invariants |
| `e2e/integration/case-create.spec.ts` | The New appraisal screen |
| `e2e/support/integration.ts` | Case creation through the screens, `as_of` pinning, settled readers |

Each spec builds its own case through the screens and deletes it afterwards. Nothing is set up
over the API. The only action taken behind the UI is pinning a case's `as_of`, for which no
endpoint exists; it mirrors `tests/conftest.py::set_as_of` and is done before any document is
uploaded, because every age and window rule reads it.
