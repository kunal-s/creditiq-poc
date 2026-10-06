# ingestion: CreditIQ document-processing service

Reads every page of a case's files, grades it, classifies each file from its content, groups pages
into instances, extracts the fields and tables of the document type's schema with page evidence,
validates them and scores confidence. FRD F-07 to F-09, F-11, F-15 (decision AD-2a).

```
upload → 1 quality gate → 2 read + route → 3 classify → 3b instances → 4 extract → 5 validate → 6 confidence
```

| Stage | What it does | Configured by |
|---|---|---|
| 1 Quality gate | size, type by content, encrypted, corrupt, page cap; reject with a plain re-scan request | `quality.yaml` |
| 2 Read + route | text layer (pdfplumber), OCR for scans and photos (PaddleOCR), cells for spreadsheets; word index with boxes; grade A/B/C/U per page | `routing.yaml`, `quality.yaml` |
| 3 Classify | tier 1 signals; tier 2 the model chooses from the closed list or `none_of_these`; the file name is never read | `signals.yaml`, `llm.yaml` |
| 3b Instances | a file may hold several of one type (two directors, eight returns); a page matching `start` opens one | `signals.yaml` |
| 4 Extract | identifier, label alias, pattern; the model fills only what is left, and every value is verified on its cited lines; tables from word positions | `fields.yaml`, `document_types.json`, `llm.yaml` |
| 5 Validate | format and checksum, cross-field and table rules; reports, never edits | `validators.yaml`, `fields.yaml` |
| 6 Confidence | `min(caps) × Σ weight × component`; decision `auto_accept` / `human_review` / `reject` | `confidence.yaml`, `decision.yaml` |

State is SQLite (`jsonb()`), one database under the data root. Stage outputs and the extracted text
are JSONB, queryable in SQL.

## Run

```bash
cd services/ingestion
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt     # + requirements-ocr.txt for scans
CREDITIQ_DATA_ROOT=../../workflow/data INGEST_CONFIG_DIR=../../config/ingestion .venv/bin/python -m ingestion.cli serve
```

| Variable | Default | Meaning |
|---|---|---|
| `CREDITIQ_DATA_ROOT` | `./data` | holds `ingestion/ingestion.sqlite3` and `config_store/ingestion/versions/` |
| `INGEST_CONFIG_DIR` | | a configuration directory served as version `dev` (development) |
| `INGEST_PORT`, `INGEST_HOST` | 3102, 127.0.0.1 | anything but loopback needs `INGEST_API_KEY` |
| `INGEST_API_KEY` | | `x-api-key` or `Authorization: Bearer`; empty means loopback callers only |
| `INGEST_MODEL_MODE` | `replay` | `replay` (recordings only, a miss is an error), `record`, `live` |
| `OPENAI_API_KEY` | | the variable named by `llm.yaml: api_key_env` |

```bash
python -m ingestion.cli config-validate ../../config/ingestion
# publishing is the engine's: `creditiq config publish` (one version covers both)
python -m ingestion.cli ingest file.pdf --config-dir ../../config/ingestion --mode replay --no-ocr
```

## API

| | |
|---|---|
| `POST /v1/ingest` | multipart: `request` (JSON: `case_ref`, `config_version`, `files[{file_id, sha256, original_name, content_type}]`) and one part per `file_id`. Answers `IngestResult` (`contracts/ingest-result.v2.schema.json`). An unknown version is a 409 |
| `POST /v1/ingest/stream` | the same, as Server-Sent Events: one `stage` event per stage, then `result` |
| `POST /v1/parse` | stages 1 and 2 only: what the extractor will read |
| `GET /v1/types` | the resolved document types (read-only) |
| `GET /v1/runs?case_ref=`, `/v1/runs/{id}`, `/stages`, `/pages/{n}` | what a run stored: stage trace, page text, words and boxes for the evidence viewer |
| `GET /v1/health` | engine, contract, model mode, published versions |

## Tests

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests -q
PYTHONPATH=. .venv/bin/lint-imports        # runtime code cannot import the configuration writer
```

The tests read the fixture documents from `workflow/docs/reference/fixtures/` (git-ignored), or
`INGEST_FIXTURE_DOCS`. The model is replaced by `tests/model_answers.py`, which writes recordings
marked `origin='fixture'`: those tests show the pipeline's behaviour, not a real model's accuracy.
The OCR path is tested with an engine that returns the page's own words.

## Boundaries

- The service cannot import the engine, whose config store holds the only writer
  (`.importlinter`). The service reads published configuration and has no code that writes it. Nothing learns at runtime.
- The only sampling parameters sent to a model are the ones `llm.yaml` names (`temperature: 0`, `seed: 1`); `assert_sampling` refuses any other. Temperature 0 narrows the variation but does not guarantee identical output: determinism comes from replaying a recording.
- No clock in the result: a re-run on the same bytes and configuration is byte-identical.
- Licences: permissive only (pdfplumber/pdfminer MIT, pypdfium2 Apache/BSD, openpyxl MIT,
  PaddleOCR Apache-2.0). No PyMuPDF.
