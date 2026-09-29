# Backlog after Wave 1

Open items from the Wave 1 streams, mapped to FRD features. Pick them up in
the wave that owns the feature; contract items (C) are additive changes to
`engine/contracts` followed by `npm run gen:api`.

## Contract additions (C)

| # | Change | Why | Feature |
|---|---|---|---|
| C1 | `IngestDocument.members: list[{file_id, page_from, page_to}]` | Several image files forming one document (F-08.4 is blocked without it) | F-08.4 |
| C2 | `QualitySection`: `blur_sharpness_min`, `skew_degrees_max`, `shadow_spread_max` | Blur, skew and shadow thresholds are code constants in the sidecar today | F-07.2 |
| C3 | `FieldDef.aliases: list[str]` | Printed caption variants are code (`services/ingest-engine/src/extract/aliases.ts`) instead of config | F-15 |
| C4 | `ReviewItem`: `system_value`, `decided_value`, `candidates` | Screens look values up by `ref` today | F-17.5 |
| C5 | `ChecklistItemState`: `coverage`, `request` | Screens look them up in the taxonomy by item id | F-13 |
| C6 | `Meta.uploads` (limits) and `accepted_formats` | The drop zone cannot show the configured limits | F-05.1 |
| C7 | `FileRecord.page_count`; document `ProposedField.value` formats (ids for constitution and facilities) | Viewer paging across a file; unambiguous proposal values | F-16, F-04 |

## Engine

- Send `x-api-key` to the sidecar from configuration for any non-loopback deployment (F-03, AD-2).
- Party set editing and constitution change after creation (F-10.2, F-12.3).
- A whole-file exception (encrypted or corrupt at upload) superseded automatically by a better copy (F-05.7).
- Quarterly GST filers; bank statements covering part months (F-13.2).
- LLP and public limited constitutions, if the case set has them (FRD C.4 decision 2).
- Rename the ITR checklist item: it requires two assessment years (F-12).
- Case reset and purge (F-01.5).

## Sidecar

- Spot-check a trusted text layer against the rendered page (F-07.1).
- Model tier for uncertain split boundaries (F-08.1); prefer the executed copy over a draft (F-08.5).
- Document defects `unsigned`, `unstamped`, `plain_paper` (F-13.2).
- Party attribution of identifiers beyond caption anchoring (F-15.5).
- Replace or confirm the licence of `buffers@0.1.1` (via exceljs; no licence declared).
- Recordings are keyed on page text: a different Tesseract build can cause replay misses; re-record when the OCR build changes.

## Screens

- Evidence viewer side-by-side mode (F-16.2), needed by cross-verification in Wave 2.

## Measured so far (synthetic fixtures only)

Sidecar fixtures, 44 documents across TC-03 to TC-20: classification 44/44;
key fields 204/204 digital and 70/70 scanned; all fields 379/379 digital,
139/141 scanned. These are our own documents; accuracy on RBL's documents is
measured by the scorecard (F-26).
