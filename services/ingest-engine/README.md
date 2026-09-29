# ingest-engine: CreditIQ document-processing sidecar

The CreditIQ engine sends a case's files here and stores what comes back. This service reads every page, grades it, splits merged files into logical documents, classifies each by content, and extracts its dictionary's fields with page evidence (FRD F-07 to F-09, F-11, F-15; decision AD-2). It holds no configuration of its own: document types, dictionaries and thresholds come from the published CreditIQ configuration version named in each request. Provenance and local changes: `VENDORED.md`.

## API

| | |
|---|---|
| `GET /v1/health` | Liveness, engine version, model provider and mode |
| `POST /v1/process` | `multipart/form-data`: a part `request` (IngestRequest JSON, `contracts/ingest-request.schema.json`) and one part per file named by its `file_id`. Answers IngestResult (`contracts/ingest-result.schema.json`). An unknown `config_version` is a 409 |

## Running

```bash
npm install
CREDITIQ_DATA_ROOT=/tmp/ciq-ingest INGEST_PORT=3102 npm start
```

| Variable | Default | Meaning |
|---|---|---|
| `CREDITIQ_DATA_ROOT` | (required) | Holds `config_store/versions/<v>/` (published configuration) and `recordings/` (model calls) |
| `INGEST_PORT` | 3102 | Port |
| `INGEST_HOST` | 127.0.0.1 | Interface. Anything other than loopback requires `INGEST_API_KEY` |
| `INGEST_API_KEY` | empty | When set, callers send it as `x-api-key` or `Authorization: Bearer`. When empty, only loopback callers are served |
| `INGEST_MODEL_PROVIDER` | stub | `stub`, `anthropic` or `gemini` |
| `INGEST_MODEL_MODE` | replay | `replay` (recordings only; a miss is an explicit error), `record`, `live` |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | | Anthropic Messages API |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | | Gemini generateContent |
| `OCR_WORKERS` | 2 | tesseract.js workers |

Model calls are recorded and replayed by the hash of their canonical request, and no sampling parameters are sent (FRD principle 6). Without a key the stub provider serves recordings; a missing recording leaves the document unclassified or the field missing, and says so on the file outcome.

## Tests

```bash
npm test          # node:test: contract test over every fixture, plus unit tests
npm run fixtures  # regenerate tests/fixtures/TC-xx/ (deterministic)
npx tsx tests/fixtures/record.ts   # rewrite the stub recordings from tests/fixtures/model-answers.ts
```

The contract test posts every fixture to `/v1/process`, validates the answer against `contracts/ingest-result.schema.json`, compares it with the fixture's `expected.json` and prints the C1 and C3 accuracy per test case.
