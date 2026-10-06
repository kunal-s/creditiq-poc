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

## Document-processing service (`services/ingestion`)

- Run the OpenAI adapter against the live API and confirm the model id (`config/ingestion/llm.yaml`); record the answers for the reference set.
- Measure scanned and photographed documents and spreadsheets from RBL; the OCR and sheet paths are tested with constructed inputs only.
- Near-duplicate detection (F-08.5): the service does not compare documents; the engine only drops a file with the same hash.
- Document defects `unstamped` and `plain_paper` (F-13.2): `unsigned` is a validator; the others need a rule.
- Cross-check of the number of GSTR-3B returns against the cover page's own table.
- Spot-check a trusted text layer against the rendered page (F-07.1).
- Party attribution of identifiers beyond caption anchoring (F-15.5).
- Recordings of model calls are keyed on the page text and the prompt: a prompt edit or a different OCR build causes replay misses; re-record.
- OCR speed on CPU: 10 to 70 s a page with PaddleOCR; cache by page image is in place; consider a smaller model or a worker pool.
- Add the document types the earlier catalogue had, as the PoC needs them (each is configuration plus a fixture).

## Screens

- Evidence viewer side-by-side mode (F-16.2), needed by cross-verification.
- The e2e mocks still use illustrative type names (`e2e/fixtures/data.ts`); align them with the nine types.

## Measured so far (the reference documents, digital only)

14 documents, 63 pages (one fictional company; read from `workflow/docs/reference/fixtures/`):
classification 10/10 in scope, 4/4 outside the closed list left unassigned; scalar fields 69/69 correct
(`services/ingestion/tests/test_extraction.py`). These are our own documents; accuracy on RBL's documents is
measured by the scorecard (F-26).
