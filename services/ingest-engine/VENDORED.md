# Vendored: ingest-engine

| | |
|---|---|
| Source | `github.com/ashok-j2w/onegrc`, `packages/ingest-engine` |
| Commit | see `.vendored-from` (vendored 29 September 2026 from `main`) |
| Runs as | A sidecar service the CreditIQ engine calls over HTTP (FRD AD-2) |
| Owns | FRD F-07 to F-11 and F-15: page reading, quality grade, splitting, classification, field extraction |

## Local modifications

Every change from upstream is listed here, newest last.

1. `tests/engine.test.ts`: fixture names in the review-queue test replaced with neutral values (repository excluded-terms rule).

## Planned changes (FRD Phase 2)

These are listed in the order they are expected to land. The vendoring review is summarised in the FRD's architecture decisions.

- **Remove what conflicts with the PoC:**
  - runtime learning: `feedback.ts`, `review.ts`, `PUT /v1/types`, catalogue hot-reload;
  - metrics state;
  - caller `rules` and inline profiles;
  - e-mail and URL intake;
  - the `sections` strategy;
  - the OneGRC type packs.
- **Page index:** a per-page word index with positions (pdf.js text items) and OCR word boxes and confidence (tesseract.js `blocks`). Also a page-aware text layout, so table columns do not merge.
- **Quality and splitting:**
  - quality grade A/B/C/U per page, with reason codes;
  - splitting merged PDFs and grouping image pages.
- **Classification:** against CreditIQ's closed document-type list plus `none_of_these`, with required, supporting and contrary signals, the top 3 candidates, several types per document, and the exit tier recorded.
- **Extraction:**
  - every field returns `{value, raw, page}`, and the value is verified on its page;
  - windows are aligned to pages;
  - deterministic extractors run first;
  - bank-statement rows are checked against the running balance.
- **Model layer:**
  - provider interface with native Anthropic and Gemini, plus a stub provider;
  - record and replay keyed by a hash of the request;
  - no sampling parameters are sent.
- **Egress:** the OCR traineddata is vendored locally (`langPath`), so no calls go to a CDN.

The configuration it reads (document types, dictionaries, thresholds) is published by the CreditIQ config store. This package holds no catalogue of its own for the PoC.
