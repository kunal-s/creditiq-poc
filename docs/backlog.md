# Backlog

Open items, mapped to FRD features. Contract items (C) are additive changes to
`engine/contracts` and `services/ingestion/ingestion/contracts.py` together, followed by
`npm run gen:api` and `services/ingestion/scripts/export_contracts.py`.

## Contract additions (C)

| # | Change | Why | Feature |
|---|---|---|---|
| C1 | A file-level grouping of several image files into one document | Several image files forming one document (F-08.4 is blocked without it) | F-08.4 |
| C4 | `ReviewItem`: `system_value`, `decided_value`, `candidates` | Screens look values up by `ref` today | F-17.5 |
| C5 | `ChecklistItemState`: `coverage`, `request` | Screens look them up in the taxonomy by item id | F-13 |
| C6 | `Meta.uploads` (limits) and `accepted_formats` | The drop zone cannot show the configured limits | F-05.1 |
| C7 | `FileRecord.page_count`; document `ProposedField.value` formats (ids for constitution and facilities) | Viewer paging across a file; unambiguous proposal values | F-16, F-04 |

Done with the move to the Python service (C2, C3): blur, skew and shadow thresholds, and printed caption
variants, are configuration (`config/ingestion/quality.yaml`, `fields.yaml`).

## Engine

- Party set editing and constitution change after creation (F-10.2, F-12.3).
- A whole-file exception (encrypted or corrupt at upload) superseded automatically by a better copy (F-05.7).
- Stage timings from the service (F-02.4): the engine records `ingest` and `store`; the service keeps per-stage timings at `GET /v1/runs/{id}/stages`.
- Constitutions other than a private limited company have no company documents on the checklist (the nine types do not read a partnership deed or a proprietor's declaration).
- Quarterly GST filers; bank statements covering part months (F-13.2).
- Case reset and purge (F-01.5).
- Whether RBL wants the declaration of existing facilities and the sanction letters on the checklist when existing facilities are declared: the `existing_facilities_declared` attribute exists but is never set. Today the cross-checks reconcile them (OB-01) without asking for them.

Policy norms, approving authority and the comparison (F-20, F-21, F-25), deferred on 8 October 2026:

- Security-cover norms (F-20.1): need valuation-report and stock-statement document types. Until then the Policy tab says no security-cover norm can be evaluated, and a test pins that state.
- Business vintage for partnerships and proprietorships: a registration-date source (Udyam or GST registration). EL-01 applies to companies only today.
- TNW and TOL composition: intangibles, deferred tax, other non-current liabilities, and a configurable deferred-tax treatment, once RBL defines its TNW.
- The working-capital cycle on a cost-of-sales basis (FR-06 uses revenue; its note says so on screen).
- Per-facility amounts on the case, for EL-05, the spread and the approval matrix (both use the total requested today).
- An MPBF norm for requests above INR 5 cr (EL-05 applies under the turnover method only).
- RBL's DSCR definition, for example adding back interest on term debt (FR-03 uses a conservative interim expression).
- Disagreeing copies of the same year's statements (F-08.5): a finding rather than the first copy read.
- A proposed norm on overdue facilities in the bureau report.
- A snapshot of the deviations for each processing run (the assessment, authority and comparison carry the configuration version today).
- The other five F-25.1 areas: classification, key fields, discrepancies, queries and decision (their sheets are accepted and reported as not compared yet).
- The F-26 scorecard and test log (the comparison already returns the area scores it needs).
- RBL's approval and delegation matrix and policy norms: publish them with `creditiq config publish --private-config workflow/private/config`, re-run every case, and score TC-27.
- OB-02 (undeclared instalments) still matches a bank narration to a declared lender on the first significant word, so debits to "Indian Overseas Bank" pass as the declared "Indian Bank". FR-03 now matches on the resolved name, or on an abbreviation only when the instalment agrees (`engine/policy.py` `_pays`); give OB-02 the same rule.
- `creditiq config diff` lists the published document-processing sections as removed, because it compares the engine's authored sections only.

The cross-verification board (F-19.7 to F-19.9), deferred on 11 October 2026:

- Policy references for each rule (`policy_ref` in `config/crosschecks.yaml`) from RBL's credit policy; the card and the banner show them once set.
- An assigned analyst per case, so a card's owner is the case's analyst rather than whoever decided or escalated it ("not yet assigned" until then).
- The Copilot panel beside the board; the layout leaves room for it.
- Periods for documents whose period extraction could not read, so two documents of one type show their years on a card rather than "· 1 of 2".
- The GST rows' heading derived from the configured rows of table 3.1 (worded today, "3.1(a)+(b)+(c) outward supplies"; a test ties the wording to the configuration).
- The switched-off rules (BR-01 to BR-04, TX-01, TX-02, FS-01, FS-02): switch them back on if RBL wants them, and decide which board area shows them.

## Document-processing service (`services/ingestion`)

- Run the OpenAI adapter against the live API and confirm the model id (`config/ingestion/llm.yaml`); record the answers for the reference set.
- Measure scanned and photographed documents and spreadsheets from RBL; the OCR and sheet paths are tested with constructed inputs only.
- Near-duplicate detection (F-08.5): the service does not compare documents; the engine only drops a file with the same hash.
- Document defects (F-13.2): `unsigned`, `unstamped` and `plain_paper` are validators (marker-based: a blank stamp or signature block, a missing letterhead line); the fixtures print none of the markers, so they are tested with constructed pages. Tune the label lists on RBL's documents.
- Cross-check of the number of GSTR-3B returns against the cover page's own table.
- Spot-check a trusted text layer against the rendered page (F-07.1).
- Party attribution of identifiers beyond caption anchoring (F-15.5).
- Recordings of model calls are keyed on the page text and the prompt: a prompt edit or a different OCR build causes replay misses; re-record.
- OCR speed on CPU: 10 to 70 s a page with PaddleOCR; cache by page image is in place; consider a smaller model or a worker pool.
- Add further document types from the earlier catalogue as the PoC needs them (each is configuration plus a fixture). The declaration of existing facilities, the sanction letter and the commercial bureau report were added on 8 October 2026.
- Re-record the four classification answers in `tests/fixtures/recordings/reference.sqlite3`: the classification prompt now lists twelve types, so they no longer replay (`scripts/record_reference.py`, live key).

## Screens

- The e2e mocks still use illustrative type names (`e2e/fixtures/data.ts`); align them with the nine types.

## Measured so far (the reference documents, digital only)

14 documents, 63 pages (one fictional company; read from `workflow/docs/reference/fixtures/`):
classification 11/11 in scope (the nil-facilities declaration is in scope since 8 October 2026), 3/3 outside the closed
list left unassigned; scalar fields 74/74 correct
(`services/ingestion/tests/test_extraction.py`). These are our own documents; accuracy on RBL's documents is
measured by the scorecard (F-26).
