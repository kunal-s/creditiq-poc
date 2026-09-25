# CreditIQ — RBL Bank (Business Banking Group) instance

CreditIQ is an identifier-to-CAM (Credit Appraisal Memorandum) automation
workbench for a bank's credit team. This repository is the RBL Bank instance:
RBL's terminology, policy and process as versioned configuration, in front of
a real document-processing pipeline, proven first on fictional sample cases
with known correct answers before any real case file is loaded.

## Running the app

The app is two processes: the React frontend and the Python engine service
behind it (sign-in, cases). Both must be running — the frontend calls the
engine over HTTP and shows nothing useful without it.

After the one-time setup below, `./scripts/start.sh` starts both in one
terminal (engine in the background, frontend in the foreground; Ctrl+C stops
both). The steps below are the equivalent two-terminal version, useful when
you want the engine's logs on their own.

**1. One-time setup**

```sh
npm install

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Start the engine service** (terminal 1)

```sh
npm run dev:api
```

Serves on `http://localhost:8000`. Reads `CREDITIQ_DATA_ROOT`, which defaults
to `workflow/data` inside this repository (a git-ignored local folder);
override it if your case store lives elsewhere:

```sh
CREDITIQ_DATA_ROOT=/path/to/data npm run dev:api
```

**3. Start the frontend** (terminal 2)

```sh
npm run dev
```

Vite prints the local URL (defaults to `http://localhost:5173`; port 4173 is
also pre-approved for the engine's CORS if you pin it with `--port 4173`).
The frontend expects the engine at `http://localhost:8000` by default; point
it elsewhere with `VITE_API_BASE_URL` if needed.

**4. Sign in**

Use any account from `config/roles.yaml`'s `users` list (e.g.
`ananya.krishnan@rblbank.com`) with the shared password in that file's
`auth.demoPassword` — also shown on the sign-in screen itself. No case data
exists until Stage B's sample generator has run, so most screens will show
their empty state; that's expected.

**Building for production**

```sh
npm run build
npm run preview
```

## Structure

- `src/` — the React frontend (TanStack Start/Router, Tailwind, shadcn/ui).
- `terminology/rbl.yaml` — RBL's vocabulary for the frontend, read through
  `src/config/terminology.ts`'s `t()` / `useTerms()`.
- `engine/` — the Python service, CLI and processing pipeline.
- `config/` — policy, checklist, rules and other versioned configuration
  authored here and published as immutable versions to the data root.
- `scripts/docgen/` — the sample-document generator.
- `workflow/` — local only, never committed: `docs/` (plan, handoff, reference
  reports, architecture, reviews), `private/`, `captures/`, and `data/` (the
  default data root: sample and real cases, config store, audit ledger).
  Never run `git clean -x` or `-X`: git would delete it.
