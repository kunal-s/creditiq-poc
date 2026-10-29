# CreditIQ — RBL Bank (Business Banking Group) PoC

CreditIQ prepares a Business Banking credit file: it creates the case from
the RM's sourcing message, reads and classifies every document, checks the
file against RBL's checklist, extracts key fields with page-level evidence,
cross-checks the sources, and drafts the spread, CAM and PD note for credit.

**What to build, and in what order:
[docs/functional-requirements.md](docs/functional-requirements.md).** Every
feature there traces to the PoC test plan (TC-01 to TC-31, criteria C1 to
C9). Working rules for this repository are in [CLAUDE.md](CLAUDE.md).

## Current state

The repository is a clean base (FRD §C.5): the application shell, sign-in,
the workbench case list, the configuration store (validate, publish,
version, diff), the checklist deriver, identifier validators and the
excluded-terms sweep. Everything else is built feature by feature from the
FRD.

## Requirements

| Tool | Version | Note |
|---|---|---|
| Node | >= 22.12 | A system Node is usually too old or too new; use the nvm install (`nvm use 22`). npm only, there is no bun. |
| Python | 3.12 exactly | Both lock files are compiled for 3.12 with hashes. `python3` on this machine may be newer, so call `python3.12` explicitly. |
| poppler-utils, Tesseract 5 | — | Already installed; needed only for scanned documents. |

## One-time setup

Run every command from the repository root, inside WSL, as the repository
owner. Each block is independent, so a failed step can be repeated on its own.

**1. Frontend dependencies**

```sh
source ~/.nvm/nvm.sh && nvm use 22
npm install
```

**2. The engine's virtual environment**

```sh
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip pip-tools
.venv/bin/pip-sync requirements.txt
```

**3. The document-processing service's own virtual environment**

```sh
python3.12 -m venv services/ingestion/.venv
services/ingestion/.venv/bin/pip install -r services/ingestion/requirements.txt
```

Scanned documents additionally need the OCR extras (a large download, skip it
until you need them):

```sh
services/ingestion/.venv/bin/pip install -r services/ingestion/requirements-ocr.txt
```

**4. The local workflow area**

`workflow/` is git-ignored and holds the data root, the audit ledger and the
private term list, so a fresh clone has to create it (CLAUDE.md rule 3).

```sh
mkdir -p workflow/data/cases workflow/data/audit workflow/private
chmod 700 workflow/data/cases workflow/private
```

`npm run check:terms` reads `workflow/private/stakeholder-names.txt` and fails
if the file is absent. Create it, one term per line; `#` starts a comment. An
empty list makes the sweep pass trivially, so paste the real list in before
relying on it:

```sh
printf '# Private excluded-terms list: one term per line.\n' > workflow/private/stakeholder-names.txt
chmod 600 workflow/private/stakeholder-names.txt
```

**5. Publish the authored configuration**

Once, and again after every change under `config/`. Nothing works before this:
both services read published configuration only.

```sh
npm run config:publish -- "<your name>"
```

**6. A browser for the screen tests** (only if you will run `npm run test:e2e`)

```sh
npx playwright install chromium
```

## Running the app

Three processes. Give each one its own terminal, and `source ~/.nvm/nvm.sh &&
nvm use 22` in the one that runs npm.

**Terminal 1 — the document-processing service, on :3102**

`CREDITIQ_DATA_ROOT` is required here: this service's own default is `./data`
relative to its own folder, which would put its database outside the shared
data root.

```sh
cd services/ingestion
CREDITIQ_DATA_ROOT="$PWD/../../workflow/data" PYTHONPATH=. .venv/bin/python -m ingestion.cli serve
```

**Terminal 2 — the engine service, on :8010**

```sh
npm run dev:api
```

That reloads on changes under `engine/` and `config/`. The data root defaults
to `workflow/data` and the service address to `http://127.0.0.1:3102`
(`config/app.yaml`), so no variables are needed. The explicit form:

```sh
CREDITIQ_DATA_ROOT="$PWD/workflow/data" \
CREDITIQ_INGEST_URL=http://127.0.0.1:3102 \
.venv/bin/uvicorn engine.api:app --reload --reload-dir engine --reload-dir config --port 8010
```

**Terminal 3 — the frontend, on :4173**

```sh
VITE_API_BASE_URL=http://localhost:8010 npm run dev -- --port 4173 --strictPort
```

Then open <http://localhost:4173> and **sign in** with any user in
`config/roles.yaml` and the password at `auth.demoPassword` in that file. One
user per role:

| Role | Email |
|---|---|
| Relationship Manager | `arjun.deshpande@rblbank.com` |
| Credit Analyst | `ananya.krishnan@rblbank.com` |
| Credit Manager | `meenal.kulkarni@rblbank.com` |

**Check the backends are up** before blaming the screens:

```sh
curl http://127.0.0.1:3102/v1/health   # {"ok":true,...,"model_mode":"replay","versions":["<hash>"]}
curl http://localhost:8010/api/health  # {"status":"ok","config_version":"<hash>"}
```

Both must report the same configuration hash that `npm run config:publish`
printed. An empty `versions` list means step 5 has not been run.

**Terminal 4 (optional) — the case assistant service, on :8020**

```sh
COPILOT_HOST_URL=http://localhost:8010 npm run dev:copilot
```

It reads `CREDITIQ_DATA_ROOT` (default `workflow/data`) and keeps its sessions,
audit trace and recorded model answers in `<data root>/copilot/`. Its behaviour
is the configuration in `services/copilot/config/`; see
`services/copilot/README.md`. `curl http://127.0.0.1:8020/health` reports its
configuration hash and model mode.

`./scripts/start.sh` runs all four at once; the commands above are what it
does, one process at a time, which is what you want when one of them fails.

### Model calls

The document-processing service answers from recorded model calls
(`INGEST_MODEL_MODE=replay`, the default). A document nobody has processed
before has no recording, so its model steps fail in that mode. To call the
model once, store the answer and replay it afterwards:

```sh
cd services/ingestion
INGEST_MODEL_MODE=record CREDITIQ_DATA_ROOT="$PWD/../../workflow/data" \
  PYTHONPATH=. .venv/bin/python -m ingestion.cli serve
```

That needs `OPENAI_API_KEY`, from the environment, `.env.local` or
`workflow/private/openai.env`. `live` calls without storing. The model is only
a fallback: most documents are read by the rules alone.

The case assistant has its own switch, `COPILOT_MODEL_MODE` (`replay`,
`record`, `live`), with the same key lookup. In `replay` it can only repeat
answers already in its store, so use `record` to try it by hand.

### Environment variables

| Variable | Default | What it does |
|---|---|---|
| `CREDITIQ_DATA_ROOT` | `<repo>/workflow/data` | The data root. **Pass it to the document-processing service explicitly** (see above). |
| `VITE_API_BASE_URL` | `http://localhost:8010` | Where the frontend looks for the engine. |
| `CREDITIQ_INGEST_URL` | `http://127.0.0.1:3102` | Where the engine looks for the document-processing service. |
| `INGEST_PORT` | `3102` | The document-processing service's port. |
| `INGEST_MODEL_MODE` | `replay` | `replay`, `record` or `live`. |
| `COPILOT_PORT` | `8020` | The case assistant service's port. |
| `COPILOT_HOST_URL` | `http://localhost:8010` | Where the case assistant looks for the engine (set by `start.sh`; overrides `host.yaml`). |
| `COPILOT_MODEL_MODE` | `replay` | `replay`, `record` or `live`. |
| `VITE_COPILOT_URL` | `http://localhost:8020` | Where the frontend looks for the case assistant. |
| `E2E_ASSISTANT_PORT` | `8021` | The case assistant service the integration screen tests start (answers from recordings). |
| `E2E_PORT` | `5173` | The dev-server port Playwright uses. |

## Checks

```sh
npm run check
```

That is contracts, typecheck, eslint, pytest (engine and service), import
contracts, the excluded-terms sweep, the production build and the screen
tests, in that order. Individually:

```sh
npm run check:contracts    # regenerate the OpenAPI contract and fail on a diff
npm run typecheck          # tsc --noEmit
npm run lint               # eslint (7 warnings are expected, 0 errors)
npm run test:py            # engine tests
npm run test:ingestion     # document-processing service tests
npm run lint:imports       # the engine's import contracts
npm run lint:ingestion     # the service's import contracts, and its config
npm run check:terms        # the excluded-terms sweep
npm run build              # production build
npm run test:e2e           # Playwright screen tests
```

A green run on a fresh clone is **633 passed, 1 skipped** (engine), **99
passed, 98 skipped** (service) and **120 passed** (screens).

Two things to know about that:

- **The 98 skipped service tests** need the reference document corpus at
  `workflow/docs/reference/fixtures/southgate` (or `INGEST_FIXTURE_DOCS`).
  It is git-ignored source material and is not in a fresh clone, so those
  tests skip. Supply the corpus and they run.
- **`npm run test:e2e` wants port 5173** and reuses whatever is already
  listening on it, so another project's dev server there would silently be
  tested instead. If 5173 is taken, pick another port:

  ```sh
  E2E_PORT=5399 npm run test:e2e
  ```

## Structure

| Path | What it holds |
|---|---|
| `docs/` | The functional requirements (committed) |
| `src/` | React frontend (TanStack Start and Router, Tailwind, shadcn/ui) |
| `terminology/rbl.yaml` | Every on-screen label, read through `t()` |
| `engine/` | Python service (FastAPI), CLI, config store, checklist, identifiers |
| `services/ingestion/` | The document-processing service (FastAPI, Python 3.12, SQLite): reads, classifies and extracts; see its README and GUIDE |
| `services/copilot/` | The case assistant service (FastAPI, Python 3.12, SQLite, Pydantic AI): routes a question to a configured use case and answers from typed lookups; see its README |
| `config/` | Authored configuration, published as immutable versions to the data root; `config/ingestion/` is the document-processing service's |
| `tests/` | Python tests |
| `workflow/` | Local only, never committed: private notes, keys and the data root (`workflow/data`: `cases/` at mode 700, `config_store/`, `audit/`). Never run `git clean -x` or `-X` |
