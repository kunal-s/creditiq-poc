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

## Running the app

Three processes: the document-processing service (port 3102), the Python engine service (port 8010) and the React frontend.

**One-time setup** (inside WSL, as the repository owner)

```sh
# Node 22 from nvm (the system Node is too old)
source ~/.nvm/nvm.sh && nvm use 22
npm install

python3 -m venv .venv
.venv/bin/pip install pip-tools
.venv/bin/pip-sync requirements.txt

# The document-processing service has its own Python 3.12 environment
(cd services/ingestion && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt)
# (scanned documents also need: .venv/bin/pip install -r requirements-ocr.txt)

# Publish the authored configuration, the engine's and the service's, into the data root
# (once, and after every change under config/)
npm run config:publish -- "<your name>"
```

**Start both**

```sh
./scripts/start.sh        # service and engine in the background, frontend on :4173
```

or in separate terminals: the service (`cd services/ingestion && PYTHONPATH=. .venv/bin/python -m ingestion.cli serve`), `npm run dev:api` and `npm run dev`. The service answers from recorded model calls unless `INGEST_MODEL_MODE` is `record` or `live`. A document nobody has processed before has no recording, so its model steps fail in the default mode. `INGEST_MODEL_MODE=record ./scripts/start.sh` calls the model once for such a document, stores the answer and replays it afterwards. It needs `OPENAI_API_KEY`, from the environment, `.env.local` or `workflow/private/openai.env`, and stops with a message if neither has a value. The model is only a fallback: most documents are read by the rules alone.

**Sign in** with any user in `config/roles.yaml` (one per role: RM, Credit
Analyst, Credit Manager) and the shared password in that file.

## Checks

```sh
npm run check     # contracts, typecheck, eslint, pytest (engine and service), import contracts, excluded terms, build, e2e
```

Individually: `npm run typecheck`, `npm run lint`, `npm run test:py`,
`npm run lint:imports`, `npm run check:terms`, `npm run build`.

## Structure

| Path | What it holds |
|---|---|
| `docs/` | The functional requirements (committed) |
| `src/` | React frontend (TanStack Start and Router, Tailwind, shadcn/ui) |
| `terminology/rbl.yaml` | Every on-screen label, read through `t()` |
| `engine/` | Python service (FastAPI), CLI, config store, checklist, identifiers |
| `services/ingestion/` | The document-processing service (FastAPI, Python 3.12, SQLite): reads, classifies and extracts; see its README and GUIDE |
| `config/` | Authored configuration, published as immutable versions to the data root; `config/ingestion/` is the document-processing service's |
| `tests/` | Python tests |
| `workflow/` | Local only, never committed: private notes, keys and the data root (`workflow/data`: `cases/` at mode 700, `config_store/`, `audit/`). Never run `git clean -x` or `-X` |

`CREDITIQ_DATA_ROOT` overrides the data root; `VITE_API_BASE_URL` points the
frontend at a different engine address.
