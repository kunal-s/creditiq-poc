# Vendored: ingest-engine

| | |
|---|---|
| Source | The OneGRC monorepo, `packages/ingest-engine` (repository URL in the private handoff note) |
| Commit | see `.vendored-from` (vendored 29 September 2026 from `main`) |
| Runs as | A sidecar service the CreditIQ engine calls over HTTP (FRD AD-2) |
| Owns | FRD F-07 to F-09, F-11 and F-15: page reading, quality grade, splitting, classification, field extraction (including partner reports). Case-level work (register, party attribution F-10, checklist, review) stays in the CreditIQ engine |

Little of the upstream code remains: the HTTP shell (Hono), the pdf.js and tesseract.js integration points and the canvas factory. Everything else was replaced for the PoC, as listed below.

## Local modifications

Every change from upstream is listed here, newest last.

1. `tests/engine.test.ts`: fixture names in the review-queue test replaced with neutral values (repository excluded-terms rule). (The file was later removed, item 2.)
2. **Removed what conflicts with the PoC:** runtime learning (`feedback.ts`, `review.ts`, `PUT /v1/types`, the catalogue and its hot reload), metrics state (`metrics.ts`), caller `rules` and inline profiles (`profiles.ts`), the `sections` pipeline (`pipeline.ts`, `sections.ts`), e-mail and URL intake (`mailparser`, `fetchSource`: an SSRF risk), the extraction cache, the OneGRC type packs under `types/`, OpenAI price tables and the OpenAI-compatible client, `start.sh`, the OneGRC guide. Dependencies `mammoth`, `html-to-text`, `mailparser`, `zod`, `dotenv` dropped.
3. **Contract:** one endpoint, `POST /v1/process` (multipart: `request` + one part per `file_id`), answering `IngestResult` exactly per `contracts/ingest-result.schema.json`; `GET /v1/health` (no base URLs). The sha256 of every part is checked. Person type assignments (`IngestRequest.assignments`) are honoured: exit tier `person`.
4. **Configuration:** read from the published CreditIQ config store, `$CREDITIQ_DATA_ROOT/config_store/versions/<version>/<section>.json` (`document_types`, `dictionary.<id>`, `quality`, `confidence`). Loaded per version, frozen, never reloaded; an unknown version is a 409, the version used is echoed.
5. **Page index (F-07.1):** `src/read/`. Text layer through pdf.js `getTextContent` with a box per word; OCR through tesseract.js `blocks` output with word boxes and confidence, rendered near the scan's own resolution; spreadsheets cell by cell (exceljs; CSV). Lines are rebuilt from word positions, and wide gaps become column breaks so table columns never glue together. English OCR data comes from the npm package `@tesseract.js-data/eng` (`langPath`), so nothing is fetched from a CDN.
6. **Quality (F-07.2 to F-07.4):** `src/quality.ts`. Grade per page from `config/quality.yaml`; reason codes resolution, blur, skew, shadow, ocr_floor, blank, corrupt, encrypted. Blur, skew and shadow are measured on the page image (Laplacian variance, text-line angle, background spread); their thresholds are code constants because the quality section has none (see the proposal in the handoff report).
7. **Splitting (F-08):** `src/split.ts`. Boundaries from a change of anchored type, page numbering restarting, a new instance of the same type (period, year, account, person) and a change of issuer identifiers; weak boundaries are `split_uncertain`. Near-duplicates by word-shingle containment (`duplicate_of_key`).
8. **Classification (F-09):** `src/classify.ts`. Tier 1 configured signals per page and per document (required, supporting, contrary, `tier1_margin`, `classify_threshold`); tier 2 table layout against the type's dictionary columns; tier 3 the model over the closed list or `none_of_these`. Several types per document; top three candidates; the file name and label hint are never read.
9. **Extraction (F-15):** `src/extract/`. Deterministic first (identifiers with the GSTIN checksum and PAN/CIN/Udyam/IFSC formats ported from `engine/identifiers.py`, caption-anchored values, tables from word positions, statements by current-year column, bank rows against the running balance with arithmetic single-cell repair); the model only names where a remaining value is printed, and the value is read from the page. Every raw text is verified on its page's word index, otherwise the value is missing (`not_found_on_page`). Confidence components per `config/confidence.yaml` keys.
10. **Model layer (AD-5):** `src/llm/`. Providers `stub`, `anthropic` (native Messages API, structured output) and `gemini` (native generateContent, response schema). Record and replay keyed by sha256 of `{provider, model, body}` under `$CREDITIQ_DATA_ROOT/recordings/`; no sampling parameters (guarded); refusals and errors never recorded.
11. **Security:** the API key is compared in constant time. Without `INGEST_API_KEY` the service binds to 127.0.0.1 and refuses non-loopback callers; `main.ts` refuses to start on another interface without a key.
12. **Tests (AD-6):** `tests/` with generated fixtures `tests/fixtures/TC-xx/`, stub recordings, the contract test (schema validation of real output, C1/C3 summary) and unit tests.

## Licence audit (runtime dependencies)

Audited 29 September 2026 over the production tree (`npm ls --omit=dev --all`, 104 packages). No AGPL, GPL or LGPL runtime dependency (CLAUDE.md rule 10).

| Licence | Packages |
|---|---|
| MIT (incl. MIT/X11) | 78, among them hono, @hono/node-server, unpdf (bundles pdf.js, Apache-2.0), @napi-rs/canvas, exceljs, @tesseract.js-data/eng |
| ISC | 13 |
| Apache-2.0 | 6: tesseract.js, tesseract.js-core, crc-32, readdir-glob, idb-keyval, wasm-feature-detect |
| BSD-3-Clause / BSD-2-Clause | 3: duplexer2, ieee754, webidl-conversions |
| Unlicense | 1: big-integer |
| MIT AND Zlib | 1: pako |
| MIT OR GPL-3.0-or-later | 1: jszip (via exceljs). **We elect MIT.** |
| none declared | 1: buffers@0.1.1 (via exceljs, unzipper, binary). The package declares no licence; its upstream repository is by the same author as other MIT/X11 packages here. To be confirmed, or removed with exceljs's streaming reader. |

`mailsplit` and `mailparser` are no longer dependencies. Development-only packages (ajv, pdf-lib, yaml, tsx, typescript, @types/node) are MIT, ISC or Apache-2.0 and are not shipped.
